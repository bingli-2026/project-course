from __future__ import annotations

import argparse

from pca_detector import PCAFaultDetector
from utils import (
    normal_only,
    project_root,
    read_feature_csv,
    split_features_and_label,
    split_holdout_by_group,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the visual PCA model on non-leaky per-run groups."
    )
    parser.add_argument("--csv-path", default="features/visual_motion_features.csv")
    parser.add_argument("--model-path", default="models/visual_pca_model.pkl")
    parser.add_argument(
        "--group-column",
        help="Preferred group column for holdout splitting. Defaults to run_id, then sample_id.",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.25,
        help="Fraction of distinct groups held out for evaluation.",
    )
    args = parser.parse_args()

    root = project_root()
    csv_path = root / args.csv_path
    model_path = root / args.model_path

    df = read_feature_csv(csv_path)
    train_df, holdout_df, resolved_group, train_groups, test_groups = split_holdout_by_group(
        df,
        group_column=args.group_column,
        test_ratio=args.test_ratio,
    )
    features, labels, _ = split_features_and_label(train_df)
    normal_features = normal_only(features, labels)

    detector = PCAFaultDetector(n_components=0.99, threshold_quantile=0.95)
    detector.fit(normal_features)
    detector.group_column_ = resolved_group
    detector.train_groups_ = [str(value) for value in train_groups]
    detector.test_groups_ = [str(value) for value in test_groups]
    detector.source_csv_ = str(csv_path)
    detector.save(model_path)

    print(f"Saved visual PCA model: {model_path}")
    print(f"Features: {len(detector.feature_columns_)}")
    print(f"PCA components: {detector.pca.n_components_}")
    print(f"Threshold: {detector.threshold_}")
    print(
        f"Train split: {len(train_df)} windows across {len(train_groups)} {resolved_group} values"
    )
    print(
        f"Holdout split reserved for test: {len(holdout_df)} windows across "
        f"{len(test_groups)} {resolved_group} values"
    )


if __name__ == "__main__":
    main()
