from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class PointTracks:
    points: np.ndarray
    dx: np.ndarray
    dy: np.ndarray
    roi: tuple[int, int, int, int]
    search_roi: tuple[int, int, int, int]
    mode: str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Track points on a visual ROI and estimate vibration frequency."
    )
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--fourcc", default="")
    parser.add_argument(
        "--backend",
        choices=["default", "dshow", "msmf"],
        default="default",
        help="OpenCV capture backend. Use dshow for many high-FPS YUYV USB cameras on Windows.",
    )
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    parser.add_argument(
        "--search-roi",
        type=int,
        nargs=4,
        metavar=("X", "Y", "W", "H"),
        help="Limit auto object search to this region. Defaults to --roi, then full frame.",
    )
    parser.add_argument(
        "--auto-object",
        action="store_true",
        help="Automatically select the strongest vibration-consistent point cluster.",
    )
    parser.add_argument(
        "--foreground-mask",
        choices=["none", "dark", "rembg"],
        default="none",
        help="Optional full-frame foreground mask before vibration-point search.",
    )
    parser.add_argument("--max-corners", type=int, default=220)
    parser.add_argument("--seed-corners", type=int, default=650)
    parser.add_argument("--min-tracks", type=int, default=5)
    parser.add_argument(
        "--cluster-radius",
        type=int,
        default=28,
        help="Pixel radius for the compact vibration-point cluster used by --auto-object.",
    )
    parser.add_argument(
        "--box-padding",
        type=int,
        default=3,
        help="Padding around the final red-point bounding box.",
    )
    parser.add_argument("--min-frequency", type=float, default=1.0)
    parser.add_argument("--max-frequency", type=float)
    parser.add_argument("--output-dir", default="results/visual_frequency_probe")
    args = parser.parse_args()

    frames, timestamps = capture_camera_frames(
        camera_index=args.camera_index,
        width=args.width,
        height=args.height,
        fps=args.fps,
        fourcc=args.fourcc,
        backend=args.backend,
        seconds=args.seconds,
    )
    if len(frames) < 12:
        raise RuntimeError(f"Not enough frames captured: {len(frames)}")

    gray_frames = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames]
    if args.auto_object:
        search_roi_arg = args.search_roi or args.roi
        search_roi = validate_roi(
            gray_frames[0].shape,
            tuple(search_roi_arg) if search_roi_arg else None,
        )
        foreground_mask = build_foreground_mask(frames[0], args.foreground_mask)
        tracks = track_auto_vibrating_points(
            gray_frames=gray_frames,
            timestamps=timestamps,
            search_roi=search_roi,
            foreground_mask=foreground_mask,
            seed_corners=args.seed_corners,
            min_tracks=args.min_tracks,
            cluster_radius=args.cluster_radius,
            box_padding=args.box_padding,
            min_frequency=args.min_frequency,
            max_frequency=args.max_frequency,
        )
    else:
        roi = validate_roi(gray_frames[0].shape, tuple(args.roi) if args.roi else None)
        points, dx_trace, dy_trace = track_roi_points(gray_frames, roi, args.max_corners)
        tracks = PointTracks(
            points=points,
            dx=dx_trace,
            dy=dy_trace,
            roi=roi,
            search_roi=roi,
            mode="manual_roi",
        )

    dx = detrend(np.median(tracks.dx, axis=1))
    dy = detrend(np.median(tracks.dy, axis=1))
    analysis_fps = effective_fps(timestamps[: len(dx)])
    fx, px, dx_peak = spectrum_peak(
        dx,
        analysis_fps,
        min_frequency=args.min_frequency,
        max_frequency=args.max_frequency,
    )
    fy, py, dy_peak = spectrum_peak(
        dy,
        analysis_fps,
        min_frequency=args.min_frequency,
        max_frequency=args.max_frequency,
    )
    consensus_peak, consensus_support = point_frequency_consensus(
        tracks.dx,
        tracks.dy,
        analysis_fps,
        min_frequency=args.min_frequency,
        max_frequency=args.max_frequency,
    )

    output_dir = project_root() / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    preview_path = output_dir / f"visual_frequency_{stamp}_preview.jpg"
    plot_path = output_dir / f"visual_frequency_{stamp}_analysis.jpg"
    csv_path = output_dir / f"visual_frequency_{stamp}.csv"

    save_preview(preview_path, frames[0], tracks)
    save_analysis_plot(
        plot_path=plot_path,
        dx=dx,
        dy=dy,
        fx=fx,
        px=px,
        fy=fy,
        py=py,
        fps=analysis_fps,
        dx_peak=dx_peak,
        dy_peak=dy_peak,
    )
    save_csv(csv_path, dx, dy, analysis_fps)

    print(f"frames={len(frames)}")
    print(f"analysis_fps={analysis_fps:.3f}")
    print(f"target_mode={tracks.mode}")
    print(f"tracked_points={len(tracks.points)}")
    print(f"search_roi={tracks.search_roi[0]},{tracks.search_roi[1]},{tracks.search_roi[2]},{tracks.search_roi[3]}")
    print(f"roi={tracks.roi[0]},{tracks.roi[1]},{tracks.roi[2]},{tracks.roi[3]}")
    print(f"dx_peak_hz={dx_peak:.3f}")
    print(f"dy_peak_hz={dy_peak:.3f}")
    print(f"point_consensus_peak_hz={consensus_peak:.3f}")
    print(f"point_consensus_support={consensus_support}")
    print(f"preview={preview_path}")
    print(f"analysis={plot_path}")
    print(f"csv={csv_path}")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def capture_camera_frames(
    camera_index: int,
    width: int,
    height: int,
    fps: int,
    fourcc: str,
    backend: str,
    seconds: float,
) -> tuple[list[np.ndarray], list[float]]:
    backend_id = {
        "default": 0,
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
    }[backend]
    cap = cv2.VideoCapture(camera_index, backend_id) if backend_id else cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {camera_index}.")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))

    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    start = time.time()
    try:
        while time.time() - start < seconds:
            ok, frame = cap.read()
            if not ok:
                continue
            frames.append(frame)
            timestamps.append(time.time())
    finally:
        cap.release()
    return frames, timestamps


def validate_roi(
    frame_shape: tuple[int, int],
    roi: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int]:
    height, width = frame_shape
    if roi is None:
        return 0, 0, width, height
    x, y, w, h = roi
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(f"ROI {roi} is outside frame bounds {(width, height)}.")
    return x, y, w, h


def track_roi_points(
    gray_frames: list[np.ndarray],
    roi: tuple[int, int, int, int],
    max_corners: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, y, w, h = roi
    first = equalize(gray_frames[0])
    mask = np.zeros_like(first)
    mask[y : y + h, x : x + w] = 255

    corners = cv2.goodFeaturesToTrack(
        first,
        maxCorners=max_corners,
        qualityLevel=0.008,
        minDistance=4,
        blockSize=7,
        mask=mask,
    )
    if corners is None or len(corners) < 5:
        raise RuntimeError("Not enough trackable points in the selected ROI.")

    initial = corners.reshape(-1, 2)
    current = corners
    valid = np.ones(len(initial), dtype=bool)
    dx_traces = [np.zeros(len(initial), dtype=np.float64)]
    dy_traces = [np.zeros(len(initial), dtype=np.float64)]
    prev = first
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    for frame in gray_frames[1:]:
        current_frame = equalize(frame)
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev,
            current_frame,
            current,
            None,
            **lk_params,
        )
        if next_pts is None or status is None:
            break
        valid &= status.reshape(-1).astype(bool)
        displacement = next_pts.reshape(-1, 2) - initial
        dx_traces.append(displacement[:, 0])
        dy_traces.append(displacement[:, 1])
        current = next_pts
        prev = current_frame

    dx = np.asarray(dx_traces, dtype=np.float64)[:, valid]
    dy = np.asarray(dy_traces, dtype=np.float64)[:, valid]
    points = initial[valid]
    if dx.shape[1] < 5:
        raise RuntimeError("Too few valid tracks remained after optical flow tracking.")
    return points, dx, dy


def track_auto_vibrating_points(
    gray_frames: list[np.ndarray],
    timestamps: list[float],
    search_roi: tuple[int, int, int, int],
    foreground_mask: np.ndarray | None,
    seed_corners: int,
    min_tracks: int,
    cluster_radius: int,
    box_padding: int,
    min_frequency: float,
    max_frequency: float | None,
) -> PointTracks:
    x, y, w, h = search_roi
    first = equalize(gray_frames[0])
    mask = np.zeros_like(first)
    mask[y : y + h, x : x + w] = 255
    if foreground_mask is not None:
        if foreground_mask.shape != first.shape:
            raise RuntimeError(
                f"Foreground mask shape {foreground_mask.shape} does not match frame {first.shape}."
            )
        mask &= foreground_mask
    corners = cv2.goodFeaturesToTrack(
        first,
        maxCorners=seed_corners,
        qualityLevel=0.004,
        minDistance=3,
        blockSize=5,
        mask=mask,
    )
    if corners is None or len(corners) < min_tracks:
        raise RuntimeError("Auto object failed: not enough feature points in the search area.")

    points, x_tracks, y_tracks = track_sparse_positions(gray_frames, corners)
    if x_tracks.shape[1] < min_tracks:
        raise RuntimeError("Auto object failed: too few valid tracked points.")

    fps = effective_fps(timestamps[: x_tracks.shape[0]])
    selected = select_vibrating_cluster(
        points=points,
        x_tracks=x_tracks,
        y_tracks=y_tracks,
        gray_frame=first,
        foreground_mask=foreground_mask,
        fps=fps,
        min_tracks=min_tracks,
        cluster_radius=cluster_radius,
        min_frequency=min_frequency,
        max_frequency=max_frequency,
    )
    if int(selected.sum()) < min_tracks:
        raise RuntimeError("Auto object failed: no stable vibration cluster found.")

    selected_points = points[selected]
    dx = x_tracks[:, selected] - selected_points[:, 0]
    dy = y_tracks[:, selected] - selected_points[:, 1]
    target_roi = bbox_from_points(
        selected_points,
        frame_shape=gray_frames[0].shape,
        padding=max(0, box_padding),
    )
    return PointTracks(
        points=selected_points,
        dx=dx,
        dy=dy,
        roi=target_roi,
        search_roi=search_roi,
        mode="auto_vibrating_points",
    )


def track_sparse_positions(
    gray_frames: list[np.ndarray],
    corners: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    initial = corners.reshape(-1, 2)
    current = corners
    valid = np.ones(len(initial), dtype=bool)
    tracks_x = [initial[:, 0].copy()]
    tracks_y = [initial[:, 1].copy()]
    prev = equalize(gray_frames[0])
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    for frame in gray_frames[1:]:
        current_frame = equalize(frame)
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev,
            current_frame,
            current,
            None,
            **lk_params,
        )
        if next_pts is None or status is None:
            break
        valid &= status.reshape(-1).astype(bool)
        flat = next_pts.reshape(-1, 2)
        tracks_x.append(flat[:, 0].copy())
        tracks_y.append(flat[:, 1].copy())
        current = next_pts
        prev = current_frame

    return (
        initial[valid],
        np.asarray(tracks_x, dtype=np.float64)[:, valid],
        np.asarray(tracks_y, dtype=np.float64)[:, valid],
    )


def select_vibrating_cluster(
    points: np.ndarray,
    x_tracks: np.ndarray,
    y_tracks: np.ndarray,
    gray_frame: np.ndarray,
    foreground_mask: np.ndarray | None,
    fps: float,
    min_tracks: int,
    cluster_radius: int,
    min_frequency: float,
    max_frequency: float | None,
) -> np.ndarray:
    dx_all = x_tracks - x_tracks[0:1, :]
    dy_all = y_tracks - y_tracks[0:1, :]
    global_dx = np.median(dx_all, axis=1)
    global_dy = np.median(dy_all, axis=1)

    scores = np.zeros(x_tracks.shape[1], dtype=np.float64)
    for index in range(x_tracks.shape[1]):
        raw_dx = detrend(dx_all[:, index])
        raw_dy = detrend(dy_all[:, index])
        rel_dx = detrend(dx_all[:, index] - global_dx)
        rel_dy = detrend(dy_all[:, index] - global_dy)
        scores[index] = max(
            point_vibration_score(raw_dx, raw_dy, fps, min_frequency, max_frequency),
            1.25 * point_vibration_score(rel_dx, rel_dy, fps, min_frequency, max_frequency),
        )

    finite_scores = scores[np.isfinite(scores)]
    if len(finite_scores) == 0 or float(finite_scores.max()) <= 0:
        raise RuntimeError("Auto object failed: no vibration-like point motion found.")

    selected = scores >= max(
        float(np.percentile(finite_scores, 88)),
        float(np.median(finite_scores) + 1.5 * robust_mad(finite_scores)),
    )
    if int(selected.sum()) < min_tracks:
        selected = scores >= float(np.percentile(finite_scores, 78))
    if int(selected.sum()) < min_tracks:
        ranked = np.argsort(scores)[::-1]
        selected = np.zeros_like(scores, dtype=bool)
        selected[ranked[:min_tracks]] = True

    return keep_best_local_cluster(
        points=points,
        selected=selected,
        scores=scores,
        gray_frame=gray_frame,
        foreground_mask=foreground_mask,
        radius=cluster_radius,
        min_tracks=min_tracks,
    )


def point_vibration_score(
    dx: np.ndarray,
    dy: np.ndarray,
    fps: float,
    min_frequency: float,
    max_frequency: float | None,
) -> float:
    return max(
        axis_vibration_score(dx, fps, min_frequency, max_frequency),
        axis_vibration_score(dy, fps, min_frequency, max_frequency),
    )


def axis_vibration_score(
    values: np.ndarray,
    fps: float,
    min_frequency: float,
    max_frequency: float | None,
) -> float:
    if len(values) < 8 or fps <= 0:
        return 0.0
    signal = detrend(values)
    amplitude = float(np.percentile(signal, 95) - np.percentile(signal, 5))
    if amplitude <= 1e-4:
        return 0.0

    window = np.hanning(len(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / fps)
    power = np.abs(np.fft.rfft((signal - signal.mean()) * window)) ** 2
    upper = max_frequency if max_frequency is not None else 0.45 * fps
    valid = (freqs >= min_frequency) & (freqs <= upper)
    if not np.any(valid):
        return 0.0
    band_power = power[valid]
    peak_power = float(np.max(band_power))
    noise_floor = float(np.median(band_power)) + 1e-12
    total_power = float(np.sum(band_power)) + 1e-12
    peak_share = peak_power / total_power
    return amplitude * peak_share * np.log1p(peak_power / noise_floor)


def robust_mad(values: np.ndarray) -> float:
    median = float(np.median(values))
    return float(np.median(np.abs(values - median))) + 1e-12


def keep_best_local_cluster(
    points: np.ndarray,
    selected: np.ndarray,
    scores: np.ndarray,
    gray_frame: np.ndarray,
    foreground_mask: np.ndarray | None,
    radius: int,
    min_tracks: int,
) -> np.ndarray:
    selected_indices = np.flatnonzero(selected)
    if len(selected_indices) <= min_tracks:
        return selected

    selected_points = points[selected_indices]
    best_indices: np.ndarray | None = None
    best_score = -1.0
    radius = max(1, radius)

    for center_index in selected_indices:
        deltas = selected_points - points[center_index]
        distances = np.sqrt(np.sum(deltas * deltas, axis=1))
        local_indices = selected_indices[distances <= radius]
        if len(local_indices) < min_tracks:
            continue
        bbox_area = point_bbox_area(points[local_indices])
        score_sum = float(np.sum(scores[local_indices]))
        foreground = foreground_support_score(
            gray_frame,
            foreground_mask,
            points[local_indices],
            radius,
        )
        cluster_score = (
            score_sum
            * float(len(local_indices) ** 0.35)
            * (0.15 + foreground) ** 2.0
            / float(max(1.0, bbox_area) ** 0.30)
        )
        if cluster_score > best_score:
            best_score = cluster_score
            best_indices = local_indices

    if best_indices is None:
        ranked = selected_indices[np.argsort(scores[selected_indices])[::-1]]
        center = ranked[0]
        deltas = selected_points - points[center]
        distances = np.sqrt(np.sum(deltas * deltas, axis=1))
        nearest_order = np.argsort(distances)
        best_indices = selected_indices[nearest_order[:min_tracks]]

    clustered = np.zeros_like(selected)
    clustered[best_indices] = True
    return clustered


def foreground_support_score(
    gray_frame: np.ndarray,
    foreground_mask: np.ndarray | None,
    points: np.ndarray,
    radius: int,
) -> float:
    x, y, w, h = bbox_from_points(
        points,
        frame_shape=gray_frame.shape,
        padding=max(6, radius // 2),
    )
    patch = gray_frame[y : y + h, x : x + w]
    if patch.size == 0:
        return 0.0

    if foreground_mask is not None:
        foreground = foreground_mask[y : y + h, x : x + w] > 0
    else:
        threshold = min(190.0, float(np.percentile(gray_frame, 55)))
        foreground = patch < threshold
    foreground_fraction = float(np.mean(foreground))

    seed_mask = np.zeros_like(patch, dtype=np.uint8)
    for px, py in points:
        cv2.circle(
            seed_mask,
            (int(round(px)) - x, int(round(py)) - y),
            max(2, radius // 5),
            255,
            -1,
        )
    seed_pixels = seed_mask > 0
    seed_fraction = float(np.mean(foreground[seed_pixels])) if np.any(seed_pixels) else 0.0

    return 0.65 * foreground_fraction + 0.35 * seed_fraction


def build_foreground_mask(frame: np.ndarray, mode: str) -> np.ndarray | None:
    if mode == "none":
        return None
    if mode == "dark":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _threshold, mask = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
    elif mode == "rembg":
        from PIL import Image
        from rembg import remove

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mask_image = remove(Image.fromarray(rgb), only_mask=True)
        mask = np.asarray(mask_image.convert("L"), dtype=np.uint8)
        mask = np.where(mask >= 24, 255, 0).astype(np.uint8)
    else:
        raise ValueError(f"Unsupported foreground mask mode: {mode}")

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return keep_largest_foreground_components(mask, max_components=3)


def keep_largest_foreground_components(mask: np.ndarray, max_components: int) -> np.ndarray:
    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
    if num <= 1:
        return mask
    areas = [
        (int(stats[label, cv2.CC_STAT_AREA]), label)
        for label in range(1, num)
        if int(stats[label, cv2.CC_STAT_AREA]) >= 50
    ]
    if not areas:
        return mask
    keep = {label for _area, label in sorted(areas, reverse=True)[:max_components]}
    return np.where(np.isin(labels, list(keep)), 255, 0).astype(np.uint8)


def point_bbox_area(points: np.ndarray) -> float:
    width = float(np.max(points[:, 0]) - np.min(points[:, 0]) + 1.0)
    height = float(np.max(points[:, 1]) - np.min(points[:, 1]) + 1.0)
    return width * height


def bbox_from_points(
    points: np.ndarray,
    frame_shape: tuple[int, int],
    padding: int,
) -> tuple[int, int, int, int]:
    height, width = frame_shape
    x0 = max(0, int(np.floor(points[:, 0].min())) - padding)
    y0 = max(0, int(np.floor(points[:, 1].min())) - padding)
    x1 = min(width, int(np.ceil(points[:, 0].max())) + padding)
    y1 = min(height, int(np.ceil(points[:, 1].max())) + padding)
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


def equalize(frame: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(frame)


def detrend(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    values = values - values.mean()
    if len(values) < 3:
        return values
    x = np.arange(len(values), dtype=np.float64)
    slope, intercept = np.polyfit(x, values, 1)
    return values - (slope * x + intercept)


def effective_fps(timestamps: list[float]) -> float:
    if len(timestamps) < 2:
        return 1.0
    duration = timestamps[-1] - timestamps[0]
    if duration <= 0:
        return 1.0
    return (len(timestamps) - 1) / duration


def spectrum_peak(
    samples: np.ndarray,
    fps: float,
    min_frequency: float,
    max_frequency: float | None,
) -> tuple[np.ndarray, np.ndarray, float]:
    centered = samples - samples.mean()
    window = np.hanning(len(centered))
    freqs = np.fft.rfftfreq(len(centered), d=1.0 / fps)
    power = np.abs(np.fft.rfft(centered * window)) ** 2
    valid = freqs >= min_frequency
    if max_frequency is not None:
        valid &= freqs <= max_frequency
    if not np.any(valid):
        raise RuntimeError("No spectral bins remain after frequency filtering.")
    valid_freqs = freqs[valid]
    valid_power = power[valid]
    peak = float(valid_freqs[int(np.argmax(valid_power))])
    return valid_freqs, valid_power, peak


def point_frequency_consensus(
    dx_tracks: np.ndarray,
    dy_tracks: np.ndarray,
    fps: float,
    min_frequency: float,
    max_frequency: float | None,
) -> tuple[float, int]:
    if dx_tracks.shape[0] < 8 or dx_tracks.shape[1] == 0 or fps <= 0:
        return 0.0, 0

    bin_width = max(0.5, fps / float(dx_tracks.shape[0]))
    votes: list[tuple[float, float]] = []
    for point_index in range(dx_tracks.shape[1]):
        candidates = [
            point_axis_peak(dx_tracks[:, point_index], fps, min_frequency, max_frequency),
            point_axis_peak(dy_tracks[:, point_index], fps, min_frequency, max_frequency),
        ]
        freq, weight = max(candidates, key=lambda item: item[1])
        if freq > 0 and weight > 0:
            votes.append((freq, weight))

    if not votes:
        return 0.0, 0

    bins: dict[int, float] = {}
    for freq, weight in votes:
        key = int(round(freq / bin_width))
        bins[key] = bins.get(key, 0.0) + weight
    best_key = max(bins, key=bins.get)
    selected = [
        (freq, weight)
        for freq, weight in votes
        if abs(int(round(freq / bin_width)) - best_key) <= 1
    ]
    weight_sum = sum(weight for _freq, weight in selected)
    if weight_sum <= 0:
        return 0.0, 0
    consensus = sum(freq * weight for freq, weight in selected) / weight_sum
    return float(consensus), len(selected)


def point_axis_peak(
    values: np.ndarray,
    fps: float,
    min_frequency: float,
    max_frequency: float | None,
) -> tuple[float, float]:
    signal = detrend(values)
    if len(signal) < 8:
        return 0.0, 0.0
    amplitude = float(np.percentile(signal, 95) - np.percentile(signal, 5))
    if amplitude <= 1e-4:
        return 0.0, 0.0
    window = np.hanning(len(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / fps)
    power = np.abs(np.fft.rfft((signal - signal.mean()) * window)) ** 2
    upper = max_frequency if max_frequency is not None else 0.45 * fps
    valid = (freqs >= min_frequency) & (freqs <= upper)
    if not np.any(valid):
        return 0.0, 0.0
    valid_freqs = freqs[valid]
    valid_power = power[valid]
    peak_index = int(np.argmax(valid_power))
    noise_floor = float(np.median(valid_power)) + 1e-12
    peak_power = float(valid_power[peak_index])
    score = amplitude * np.log1p(peak_power / noise_floor)
    return float(valid_freqs[peak_index]), float(score)


def save_preview(
    path: Path,
    frame: np.ndarray,
    tracks: PointTracks,
) -> None:
    x, y, w, h = tracks.roi
    sx, sy, sw, sh = tracks.search_roi
    preview = frame.copy()
    if tracks.search_roi != tracks.roi:
        cv2.rectangle(preview, (sx, sy), (sx + sw, sy + sh), (0, 255, 255), 1)
    cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 1)
    for px, py in tracks.points:
        cv2.circle(preview, (int(round(px)), int(round(py))), 2, (0, 0, 255), -1)
    cv2.imwrite(str(path), preview)


def save_analysis_plot(
    plot_path: Path,
    dx: np.ndarray,
    dy: np.ndarray,
    fx: np.ndarray,
    px: np.ndarray,
    fy: np.ndarray,
    py: np.ndarray,
    fps: float,
    dx_peak: float,
    dy_peak: float,
) -> None:
    width, height = 1400, 900
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    draw_title(canvas, "Tracked median displacement", (520, 38))
    draw_line_plot(
        canvas,
        rect=(90, 65, 1250, 330),
        xs=np.arange(len(dx)) / fps,
        series=[(dx, (31, 119, 180), "dx"), (dy, (255, 127, 14), "dy")],
        x_label="Time (s)",
        y_label="Displacement (pixels)",
    )
    draw_title(canvas, f"Spectrum (analysis fps={fps:.2f})", (510, 455))
    draw_line_plot(
        canvas,
        rect=(90, 485, 1250, 330),
        xs=fx,
        series=[
            (px, (31, 119, 180), f"dx peak={dx_peak:.2f} Hz"),
            (py, (255, 127, 14), f"dy peak={dy_peak:.2f} Hz"),
        ],
        x_label="Frequency (Hz)",
        y_label="Power",
        log_y=True,
    )
    cv2.imwrite(str(plot_path), canvas)


def draw_title(canvas: np.ndarray, text: str, origin: tuple[int, int]) -> None:
    cv2.putText(
        canvas,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )


def draw_line_plot(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    xs: np.ndarray,
    series: list[tuple[np.ndarray, tuple[int, int, int], str]],
    x_label: str,
    y_label: str,
    *,
    log_y: bool = False,
    append: bool = False,
) -> None:
    x0, y0, w, h = rect
    if not append:
        cv2.rectangle(canvas, (x0, y0), (x0 + w, y0 + h), (0, 0, 0), 1)
        for i in range(1, 6):
            gx = x0 + int(w * i / 6)
            gy = y0 + int(h * i / 6)
            cv2.line(canvas, (gx, y0), (gx, y0 + h), (225, 225, 225), 1)
            cv2.line(canvas, (x0, gy), (x0 + w, gy), (225, 225, 225), 1)
        cv2.putText(canvas, x_label, (x0 + w // 2 - 60, y0 + h + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1)
        cv2.putText(canvas, y_label, (10, y0 + h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    y_values = []
    for values, _color, _label in series:
        y_values.append(np.asarray(values, dtype=np.float64))
    all_y = np.concatenate(y_values)
    if log_y:
        all_y = np.log10(np.maximum(all_y, 1e-12))
    y_min = float(np.min(all_y))
    y_max = float(np.max(all_y))
    if y_max <= y_min:
        y_max = y_min + 1.0
    x_min = float(np.min(xs))
    x_max = float(np.max(xs))
    if x_max <= x_min:
        x_max = x_min + 1.0

    legend_x = x0 + w - 260
    legend_y = y0 + 28 + (26 if append else 0)
    for values, color, label in series:
        values = np.asarray(values, dtype=np.float64)
        plot_y = np.log10(np.maximum(values, 1e-12)) if log_y else values
        points: list[tuple[int, int]] = []
        for x, y in zip(xs, plot_y):
            px = x0 + int((float(x) - x_min) / (x_max - x_min) * w)
            py = y0 + h - int((float(y) - y_min) / (y_max - y_min) * h)
            points.append((px, py))
        if len(points) >= 2:
            cv2.polylines(canvas, [np.asarray(points, dtype=np.int32)], False, color, 2)
        cv2.line(canvas, (legend_x, legend_y), (legend_x + 32, legend_y), color, 3)
        cv2.putText(canvas, label, (legend_x + 42, legend_y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 1)
        legend_y += 26


def save_csv(path: Path, dx: np.ndarray, dy: np.ndarray, fps: float) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "dx", "dy"])
        writer.writeheader()
        for index, (x_value, y_value) in enumerate(zip(dx, dy)):
            writer.writerow(
                {
                    "time_s": index / fps,
                    "dx": float(x_value),
                    "dy": float(y_value),
                }
            )


if __name__ == "__main__":
    main()
