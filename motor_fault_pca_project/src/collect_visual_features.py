from __future__ import annotations

import argparse
import time

from realtime_features import (
    append_feature_row,
    visual_motion_window_from_camera,
    visual_vibration_window_from_camera,
)
from utils import project_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect visual motion PCA training features.")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=400)
    parser.add_argument("--fourcc", default="YUYV")
    parser.add_argument("--method", choices=["lk", "motion"], default="lk")
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    parser.add_argument(
        "--search-roi",
        type=int,
        nargs=4,
        metavar=("X", "Y", "W", "H"),
        help="Limit automatic target search to this region before LK tracking.",
    )
    parser.add_argument(
        "--auto-roi",
        action="store_true",
        help="Infer a target ROI from foreground motion before LK tracking.",
    )
    parser.add_argument(
        "--auto-object",
        action="store_true",
        help="Infer a whole vibrating-object mask before LK tracking.",
    )
    parser.add_argument("--max-corners", type=int, default=80)
    parser.add_argument("--min-frequency", type=float, default=1.0)
    parser.add_argument("--max-frequency", type=float)
    parser.add_argument("--label", choices=["normal", "fault"], required=True)
    parser.add_argument("--run-id", help="Group windows from one capture session under the same run id.")
    parser.add_argument("--windows", type=int, default=30)
    parser.add_argument("--window-seconds", type=float, default=2.0)
    parser.add_argument("--output", default="features/visual_motion_features.csv")
    args = parser.parse_args()

    root = project_root()
    output = root / args.output
    run_id = args.run_id or f"visual_{args.label}_{time.strftime('%Y%m%d-%H%M%S')}"
    auto_object = args.auto_object or (
        args.method == "lk"
        and args.roi is None
        and not args.auto_roi
    )

    for window_id in range(args.windows):
        if args.method == "lk":
            record = visual_vibration_window_from_camera(
                camera_index=args.camera_index,
                window_seconds=args.window_seconds,
                width=args.width,
                height=args.height,
                fps=args.fps,
                fourcc=args.fourcc,
                roi=tuple(args.roi) if args.roi else None,
                search_roi=tuple(args.search_roi) if args.search_roi else None,
                max_corners=args.max_corners,
                min_frequency=args.min_frequency,
                max_frequency=args.max_frequency,
                auto_roi=args.auto_roi,
                auto_object=auto_object,
            )
        else:
            record = visual_motion_window_from_camera(
                camera_index=args.camera_index,
                window_seconds=args.window_seconds,
                width=args.width,
                height=args.height,
                fps=args.fps,
                fourcc=args.fourcc,
            )
        row = {
            "sample_id": f"{run_id}_{window_id:04d}",
            "run_id": run_id,
            "window_id": window_id,
            "start_time": record.start_time,
            "end_time": record.end_time,
            "label": args.label,
            **record.features,
        }
        append_feature_row(output, row)
        print(f"Saved visual window {window_id + 1}/{args.windows}: {args.label}")


if __name__ == "__main__":
    main()
