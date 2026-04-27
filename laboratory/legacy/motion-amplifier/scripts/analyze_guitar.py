from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track feature motion in a video and estimate its dominant vibration frequency."
    )
    parser.add_argument("video", type=Path, help="Path to the input video.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/guitar"),
        help="Directory for plots and preview images.",
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
        default=None,
        help="ROI rectangle in pixels. Defaults to the full frame.",
    )
    parser.add_argument(
        "--max-corners",
        type=int,
        default=150,
        help="Maximum number of Shi-Tomasi corners to track.",
    )
    parser.add_argument(
        "--min-frequency",
        type=float,
        default=1.0,
        help="Ignore spectral peaks below this frequency in Hz.",
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(gray)
        if max_frames is not None and len(frames) >= max_frames:
            break
    cap.release()

    if len(frames) < 2:
        raise RuntimeError(f"Not enough frames in video: {video_path}")
    return frames, fps


def roi_bounds(frame_shape: tuple[int, int], roi: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
    height, width = frame_shape
    if roi is None:
        return 0, 0, width, height

    x, y, w, h = roi
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(f"ROI {roi} is outside frame bounds {(width, height)}")
    return x, y, w, h


def track_motion(
    frames: list[np.ndarray], roi: tuple[int, int, int, int] | None, max_corners: int
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
    median_x = np.median(x_trace, axis=1)
    median_y = np.median(y_trace, axis=1)
    return signal.detrend(median_x), signal.detrend(median_y)


def dominant_frequency(samples: np.ndarray, fps: float, min_frequency: float) -> tuple[np.ndarray, np.ndarray, float]:
    if len(samples) < 8:
        raise RuntimeError("Too few samples to compute a spectrum.")

    nperseg = min(256, len(samples))
    freqs, psd = signal.welch(samples, fs=fps, nperseg=nperseg, scaling="spectrum")
    valid = freqs >= min_frequency
    if not np.any(valid):
        raise RuntimeError("No spectral bins remain after min-frequency filtering.")
    peak_idx = np.argmax(psd[valid])
    dominant = freqs[valid][peak_idx]
    return freqs, psd, float(dominant)


def save_outputs(
    output_dir: Path,
    video_name: str,
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    points: np.ndarray,
    time_axis: np.ndarray,
    x_signal: np.ndarray,
    y_signal: np.ndarray,
    freqs_x: np.ndarray,
    psd_x: np.ndarray,
    freqs_y: np.ndarray,
    psd_y: np.ndarray,
    dom_x: float,
    dom_y: float,
    fps: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    x, y, w, h = roi

    preview = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 1)
    for px, py in points:
        cv2.circle(preview, (int(round(px)), int(round(py))), 2, (0, 0, 255), -1)
    cv2.imwrite(str(output_dir / f"{video_name}_preview.png"), preview)

    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    axes[0].plot(time_axis, x_signal, label="dx")
    axes[0].plot(time_axis, y_signal, label="dy")
    axes[0].set_title(f"Tracked median displacement ({video_name})")
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Displacement (pixels)")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].semilogy(freqs_x, psd_x, label=f"dx peak={dom_x:.2f} Hz")
    axes[1].semilogy(freqs_y, psd_y, label=f"dy peak={dom_y:.2f} Hz")
    axes[1].set_title(f"Welch spectrum (analysis fps={fps:.2f})")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Power")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / f"{video_name}_analysis.png", dpi=160)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    frames, metadata_fps = load_video_frames(args.video, args.max_frames)
    analysis_fps = args.fps_override or metadata_fps
    roi = roi_bounds(frames[0].shape, tuple(args.roi) if args.roi else None)

    points, x_trace, y_trace = track_motion(frames, tuple(args.roi) if args.roi else None, args.max_corners)
    x_signal, y_signal = robust_motion_signal(x_trace, y_trace)
    freqs_x, psd_x, dom_x = dominant_frequency(x_signal, analysis_fps, args.min_frequency)
    freqs_y, psd_y, dom_y = dominant_frequency(y_signal, analysis_fps, args.min_frequency)

    time_axis = np.arange(len(x_signal)) / analysis_fps
    video_name = args.video.stem
    save_outputs(
        output_dir=args.output_dir,
        video_name=video_name,
        frame=frames[0],
        roi=roi,
        points=points,
        time_axis=time_axis,
        x_signal=x_signal,
        y_signal=y_signal,
        freqs_x=freqs_x,
        psd_x=psd_x,
        freqs_y=freqs_y,
        psd_y=psd_y,
        dom_x=dom_x,
        dom_y=dom_y,
        fps=analysis_fps,
    )

    print(f"Video: {args.video}")
    print(f"Metadata FPS: {metadata_fps:.4f}")
    if args.fps_override is not None:
        print(f"Override FPS: {analysis_fps:.4f}")
    print(f"Frames processed: {len(frames)}")
    print(f"Valid tracked points: {len(points)}")
    print(f"ROI: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")
    print(f"Dominant dx frequency: {dom_x:.4f} Hz")
    print(f"Dominant dy frequency: {dom_y:.4f} Hz")
    print(f"Preview image: {args.output_dir / f'{video_name}_preview.png'}")
    print(f"Analysis plot: {args.output_dir / f'{video_name}_analysis.png'}")


if __name__ == "__main__":
    main()
