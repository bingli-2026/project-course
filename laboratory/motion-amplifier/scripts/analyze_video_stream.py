from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sliding-window vibration spectrum analysis for a fixed ROI."
    )
    parser.add_argument("video", type=Path, help="Path to the input video.")
    parser.add_argument(
        "--sample-id",
        type=str,
        default=None,
        help="Stable sample identifier for downstream fusion and labeling.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="unknown",
        help="Optional class label for the current sample.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/stream"),
        help="Directory for plots and structured outputs.",
    )
    parser.add_argument(
        "--fps-override",
        type=float,
        default=None,
        help="Use this acquisition frame rate instead of the container metadata.",
    )
    parser.add_argument(
        "--roi",
        type=int,
        nargs=4,
        metavar=("X", "Y", "W", "H"),
        required=True,
        help="ROI rectangle in pixels: x y w h.",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=0.25,
        help="Sliding analysis window size in seconds.",
    )
    parser.add_argument(
        "--hop-seconds",
        type=float,
        default=0.05,
        help="Hop size in seconds between windows.",
    )
    parser.add_argument(
        "--min-frequency",
        type=float,
        default=1.0,
        help="Ignore spectral peaks below this frequency in Hz.",
    )
    parser.add_argument(
        "--max-frequency",
        type=float,
        default=None,
        help="Optional upper bound when selecting spectral peaks.",
    )
    parser.add_argument(
        "--max-corners",
        type=int,
        default=150,
        help="Maximum number of Shi-Tomasi corners to track.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional cap on processed frame count.",
    )
    return parser.parse_args()


def load_video_frames(video_path: Path, max_frames: int | None) -> tuple[list[np.ndarray], float]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frames: list[np.ndarray] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        if max_frames is not None and len(frames) >= max_frames:
            break
    cap.release()

    if len(frames) < 2:
        raise RuntimeError(f"Not enough frames in video: {video_path}")
    return frames, fps


def roi_bounds(frame_shape: tuple[int, int], roi: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    height, width = frame_shape
    x, y, w, h = roi
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(f"ROI {roi} is outside frame bounds {(width, height)}")
    return x, y, w, h


def track_motion(
    frames: list[np.ndarray], roi: tuple[int, int, int, int], max_corners: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    first = frames[0]
    x, y, w, h = roi_bounds(first.shape, roi)
    mask = np.zeros_like(first)
    mask[y : y + h, x : x + w] = 255

    corners = cv2.goodFeaturesToTrack(
        first,
        maxCorners=max_corners,
        qualityLevel=0.01,
        minDistance=5,
        blockSize=7,
        mask=mask,
    )
    if corners is None or len(corners) < 5:
        raise RuntimeError("Not enough trackable corners in the selected ROI.")

    initial = corners.reshape(-1, 2)
    current = corners
    x_traces = [np.zeros(len(initial), dtype=np.float64)]
    y_traces = [np.zeros(len(initial), dtype=np.float64)]
    valid = np.ones(len(initial), dtype=bool)

    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    prev = first
    for frame in frames[1:]:
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev, frame, current, None, **lk_params)
        if next_pts is None or status is None:
            break
        status = status.reshape(-1).astype(bool)
        valid &= status
        displacement = next_pts.reshape(-1, 2) - initial
        x_traces.append(displacement[:, 0])
        y_traces.append(displacement[:, 1])
        current = next_pts
        prev = frame

    x_trace = np.asarray(x_traces)[:, valid]
    y_trace = np.asarray(y_traces)[:, valid]
    points = initial[valid]
    if x_trace.shape[1] < 5:
        raise RuntimeError("Too few valid tracks remained after optical flow tracking.")
    return points, x_trace, y_trace


def robust_motion_signal(x_trace: np.ndarray, y_trace: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return signal.detrend(np.median(x_trace, axis=1)), signal.detrend(np.median(y_trace, axis=1))


def window_spectrum(
    samples: np.ndarray,
    fps: float,
    min_frequency: float,
    max_frequency: float | None,
) -> tuple[np.ndarray, np.ndarray, float, float, float, float]:
    nperseg = min(256, len(samples))
    freqs, psd = signal.welch(samples, fs=fps, nperseg=nperseg, scaling="spectrum")
    valid = freqs >= min_frequency
    if max_frequency is not None:
        valid &= freqs <= max_frequency
    if not np.any(valid):
        raise RuntimeError("No spectral bins remain after frequency filtering.")

    f = freqs[valid]
    p = psd[valid]
    peak_idx = int(np.argmax(p))
    peak_freq = float(f[peak_idx])
    peak_power = float(p[peak_idx])
    band_power = float(np.sum(p))
    spectral_centroid = float(np.sum(f * p) / np.sum(p))
    psd_norm = p / np.sum(p)
    spectral_entropy = float(-(psd_norm * np.log(psd_norm + 1e-12)).sum())
    return f, p, peak_freq, peak_power, band_power, spectral_centroid, spectral_entropy


def sliding_windows(
    x_signal: np.ndarray,
    y_signal: np.ndarray,
    fps: float,
    window_seconds: float,
    hop_seconds: float,
    min_frequency: float,
    max_frequency: float | None,
) -> tuple[list[dict[str, float]], np.ndarray, np.ndarray, np.ndarray]:
    window_size = max(8, int(round(window_seconds * fps)))
    hop_size = max(1, int(round(hop_seconds * fps)))

    rows: list[dict[str, float | int | str]] = []
    time_axis: list[float] = []
    dx_peaks: list[float] = []
    dy_peaks: list[float] = []

    for start in range(0, len(x_signal) - window_size + 1, hop_size):
        end = start + window_size
        xw = x_signal[start:end]
        yw = y_signal[start:end]

        fx, px, x_peak, x_peak_power, x_band_power, x_centroid, x_entropy = window_spectrum(
            xw, fps, min_frequency, max_frequency
        )
        fy, py, y_peak, y_peak_power, y_band_power, y_centroid, y_entropy = window_spectrum(
            yw, fps, min_frequency, max_frequency
        )

        center_time = (start + end - 1) / 2 / fps
        time_axis.append(center_time)
        dx_peaks.append(x_peak)
        dy_peaks.append(y_peak)

        rows.append(
            {
                "window_start_frame": start,
                "window_end_frame": end - 1,
                "center_time_s": center_time,
                "dx_peak_hz": x_peak,
                "dy_peak_hz": y_peak,
                "dx_peak_power": x_peak_power,
                "dy_peak_power": y_peak_power,
                "dx_band_power": x_band_power,
                "dy_band_power": y_band_power,
                "dx_spectral_centroid_hz": x_centroid,
                "dy_spectral_centroid_hz": y_centroid,
                "dx_spectral_entropy": x_entropy,
                "dy_spectral_entropy": y_entropy,
            }
        )

    return rows, np.asarray(time_axis), np.asarray(dx_peaks), np.asarray(dy_peaks)


def save_preview(output_dir: Path, video_name: str, frame: np.ndarray, roi: tuple[int, int, int, int], points: np.ndarray) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    x, y, w, h = roi
    preview = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 2)
    for px, py in points:
        cv2.circle(preview, (int(round(px)), int(round(py))), 2, (0, 0, 255), -1)
    preview_path = output_dir / f"{video_name}_preview.png"
    cv2.imwrite(str(preview_path), preview)
    return preview_path


def save_feature_csv(output_dir: Path, video_name: str, rows: list[dict[str, float | int | str]]) -> Path:
    csv_path = output_dir / f"{video_name}_window_features.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def save_summary_json(
    output_dir: Path,
    video_name: str,
    video_path: Path,
    metadata_fps: float,
    analysis_fps: float,
    roi: tuple[int, int, int, int],
    points: np.ndarray,
    rows: list[dict[str, float | int | str]],
    sample_id: str,
    label: str,
) -> Path:
    summary = {
        "sample_id": sample_id,
        "label": label,
        "modality": "vision",
        "video": str(video_path),
        "metadata_fps": metadata_fps,
        "analysis_fps": analysis_fps,
        "roi": {"x": roi[0], "y": roi[1], "w": roi[2], "h": roi[3]},
        "tracked_points": int(len(points)),
        "window_count": len(rows),
        "vision_dx_peak_mean_hz": float(np.mean([row["vision_dx_peak_hz"] for row in rows])),
        "vision_dy_peak_mean_hz": float(np.mean([row["vision_dy_peak_hz"] for row in rows])),
        "vision_dx_peak_std_hz": float(np.std([row["vision_dx_peak_hz"] for row in rows])),
        "vision_dy_peak_std_hz": float(np.std([row["vision_dy_peak_hz"] for row in rows])),
    }
    json_path = output_dir / f"{video_name}_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return json_path


def save_plots(
    output_dir: Path,
    video_name: str,
    time_full: np.ndarray,
    x_signal: np.ndarray,
    y_signal: np.ndarray,
    peak_time: np.ndarray,
    dx_peaks: np.ndarray,
    dy_peaks: np.ndarray,
) -> tuple[Path, Path]:
    signal_path = output_dir / f"{video_name}_signal.png"
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=False)
    axes[0].plot(time_full, x_signal, label="dx")
    axes[0].plot(time_full, y_signal, label="dy")
    axes[0].set_title("Median ROI displacement")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Pixels")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(peak_time, dx_peaks, label="dx peak")
    axes[1].plot(peak_time, dy_peaks, label="dy peak")
    axes[1].set_title("Sliding-window dominant frequency")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Frequency (Hz)")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(signal_path, dpi=160)
    plt.close(fig)

    hist_path = output_dir / f"{video_name}_peak_hist.png"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(dx_peaks, bins=min(20, len(dx_peaks)), color="tab:blue", alpha=0.8)
    axes[0].set_title("dx peak histogram")
    axes[0].set_xlabel("Frequency (Hz)")
    axes[0].set_ylabel("Count")
    axes[0].grid(True, alpha=0.3)

    axes[1].hist(dy_peaks, bins=min(20, len(dy_peaks)), color="tab:orange", alpha=0.8)
    axes[1].set_title("dy peak histogram")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Count")
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(hist_path, dpi=160)
    plt.close(fig)

    return signal_path, hist_path


def main() -> None:
    args = parse_args()
    frames, metadata_fps = load_video_frames(args.video, args.max_frames)
    analysis_fps = args.fps_override or metadata_fps
    roi = roi_bounds(frames[0].shape, tuple(args.roi))

    points, x_trace, y_trace = track_motion(frames, roi, args.max_corners)
    x_signal, y_signal = robust_motion_signal(x_trace, y_trace)
    sample_id = args.sample_id or args.video.stem
    rows, peak_time, dx_peaks, dy_peaks = sliding_windows(
        x_signal=x_signal,
        y_signal=y_signal,
        fps=analysis_fps,
        window_seconds=args.window_seconds,
        hop_seconds=args.hop_seconds,
        min_frequency=args.min_frequency,
        max_frequency=args.max_frequency,
    )
    if not rows:
        raise RuntimeError("No sliding windows were produced. Increase frames or reduce window size.")

    for index, row in enumerate(rows):
        row.update(
            {
                "sample_id": sample_id,
                "label": args.label,
                "modality": "vision",
                "source_name": args.video.stem,
                "window_index": index,
                "analysis_fps": analysis_fps,
                "roi_x": roi[0],
                "roi_y": roi[1],
                "roi_w": roi[2],
                "roi_h": roi[3],
                "vision_dx_peak_hz": row.pop("dx_peak_hz"),
                "vision_dy_peak_hz": row.pop("dy_peak_hz"),
                "vision_dx_peak_power": row.pop("dx_peak_power"),
                "vision_dy_peak_power": row.pop("dy_peak_power"),
                "vision_dx_band_power": row.pop("dx_band_power"),
                "vision_dy_band_power": row.pop("dy_band_power"),
                "vision_dx_spectral_centroid_hz": row.pop("dx_spectral_centroid_hz"),
                "vision_dy_spectral_centroid_hz": row.pop("dy_spectral_centroid_hz"),
                "vision_dx_spectral_entropy": row.pop("dx_spectral_entropy"),
                "vision_dy_spectral_entropy": row.pop("dy_spectral_entropy"),
            }
        )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    video_name = args.video.stem

    preview_path = save_preview(output_dir, video_name, frames[0], roi, points)
    csv_path = save_feature_csv(output_dir, video_name, rows)
    summary_path = save_summary_json(
        output_dir, video_name, args.video, metadata_fps, analysis_fps, roi, points, rows, sample_id, args.label
    )
    signal_path, hist_path = save_plots(
        output_dir=output_dir,
        video_name=video_name,
        time_full=np.arange(len(x_signal)) / analysis_fps,
        x_signal=x_signal,
        y_signal=y_signal,
        peak_time=peak_time,
        dx_peaks=dx_peaks,
        dy_peaks=dy_peaks,
    )

    print(f"Video: {args.video}")
    print(f"Metadata FPS: {metadata_fps:.4f}")
    if args.fps_override is not None:
        print(f"Override FPS: {analysis_fps:.4f}")
    print(f"Frames processed: {len(frames)}")
    print(f"Tracked points: {len(points)}")
    print(f"ROI: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")
    print(f"Windows generated: {len(rows)}")
    print(f"Mean dx peak: {np.mean(dx_peaks):.4f} Hz")
    print(f"Mean dy peak: {np.mean(dy_peaks):.4f} Hz")
    print(f"dx peak std: {np.std(dx_peaks):.4f} Hz")
    print(f"dy peak std: {np.std(dy_peaks):.4f} Hz")
    print(f"Preview image: {preview_path}")
    print(f"Signal plot: {signal_path}")
    print(f"Peak histogram: {hist_path}")
    print(f"Window features CSV: {csv_path}")
    print(f"Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
