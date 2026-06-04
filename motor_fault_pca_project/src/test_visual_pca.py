from __future__ import annotations

import argparse

from pca_detector import PCAFaultDetector
from utils import (
    build_result_frame,
    compute_metrics,
    print_metrics,
    project_root,
    read_feature_csv,
    save_csv,
    split_features_and_label,
    split_holdout_by_group,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the visual PCA model on a non-leaky holdout split."
    )
    parser.add_argument("--csv-path", default="features/visual_motion_features.csv")
    parser.add_argument("--model-path", default="models/visual_pca_model.pkl")
    parser.add_argument("--result-path", default="results/visual_pca_results.csv")
    parser.add_argument(
        "--group-column",
        help="Override the holdout group column. Defaults to the value stored in the model.",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.25,
        help="Fallback holdout ratio if the model does not contain split metadata.",
    )
    args = parser.parse_args()

    root = project_root()
    csv_path = root / args.csv_path
    model_path = root / args.model_path
    result_path = root / args.result_path

    detector = PCAFaultDetector.load(model_path)
    df = read_feature_csv(csv_path)
    test_df, resolved_group, test_groups = _resolve_test_split(
        df=df,
        detector=detector,
        group_column=args.group_column,
        test_ratio=args.test_ratio,
    )
    features, labels, _ = split_features_and_label(test_df, detector.feature_columns_)

    output = detector.predict(features)
    result = build_result_frame(test_df, output.scores, output.threshold, output.predictions)
    save_csv(result, result_path)

    print(f"Saved visual PCA results: {result_path}")
    print(
        f"Evaluated holdout split: {len(test_df)} windows across "
        f"{len(test_groups)} {resolved_group} values"
    )
    print_metrics(compute_metrics(labels, output.predictions, output.scores))


def _resolve_test_split(
    df,
    detector: PCAFaultDetector,
    group_column: str | None,
    test_ratio: float,
):
    resolved_group = group_column or getattr(detector, "group_column_", None)
    stored_groups = getattr(detector, "test_groups_", None)
    if resolved_group and stored_groups:
        if resolved_group not in df.columns:
            raise ValueError(f"Group column not found in evaluation CSV: {resolved_group}")
        normalized_groups = {str(value) for value in stored_groups}
        test_df = df.loc[df[resolved_group].astype(str).isin(normalized_groups)].copy()
        if test_df.empty:
            raise ValueError(
                f"No rows matched the model holdout groups for `{resolved_group}`. "
                "Collect data again or retrain the model against the current CSV."
            )
        return test_df, resolved_group, sorted(normalized_groups)

    _train_df, test_df, fallback_group, _train_groups, test_groups = split_holdout_by_group(
        df,
        group_column=resolved_group,
        test_ratio=test_ratio,
    )
    return test_df, fallback_group, [str(value) for value in test_groups]


if __name__ == "__main__":
    main()
