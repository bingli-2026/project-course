"""Qt-based live camera preview for the global camera laboratory project."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .camera import CameraConfig, capture_properties, open_capture, save_frame


@dataclass(frozen=True)
class PreviewRequest:
    """Requested settings for the Qt preview window."""

    config: CameraConfig
    output_dir: Path
    window_title: str
    quit_after_seconds: float | None


def parse_args() -> PreviewRequest:
    """Parse command-line arguments for the Qt preview."""

    parser = argparse.ArgumentParser(
        description="Open a live Qt preview window for a camera device."
    )
    parser.add_argument("--device", type=int, default=0, help="Camera device index.")
    parser.add_argument(
        "--backend",
        choices=("auto", "v4l2"),
        default="v4l2",
        help="VideoCapture backend on Linux.",
    )
    parser.add_argument(
        "--width", type=int, default=None, help="Requested frame width."
    )
    parser.add_argument(
        "--height", type=int, default=None, help="Requested frame height."
    )
    parser.add_argument("--fps", type=float, default=None, help="Requested camera FPS.")
    parser.add_argument(
        "--fourcc",
        type=str,
        default=None,
        help="Optional FOURCC such as MJPG or YUYV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("captures"),
        help="Directory for saved snapshots.",
    )
    parser.add_argument(
        "--window-title",
        type=str,
        default="Global Camera Preview",
        help="Window title for the preview.",
    )
    parser.add_argument(
        "--quit-after-seconds",
        type=float,
        default=None,
        help="Optional auto-close timer for smoke tests.",
    )

    args = parser.parse_args()
    if args.quit_after_seconds is not None and args.quit_after_seconds <= 0:
        raise ValueError("--quit-after-seconds must be > 0 when provided.")

    return PreviewRequest(
        config=CameraConfig(
            device=args.device,
            backend=args.backend,
            width=args.width,
            height=args.height,
            fps=args.fps,
            fourcc=args.fourcc,
        ),
        output_dir=args.output_dir,
        window_title=args.window_title,
        quit_after_seconds=args.quit_after_seconds,
    )


class CameraPreviewWindow(QMainWindow):
    """A simple live camera preview window."""

    def __init__(self, request: PreviewRequest) -> None:
        super().__init__()
        self.request = request
        self.capture = open_capture(request.config)
        self.current_frame = None
        self.last_saved_path: Path | None = None

        self.setWindowTitle(request.window_title)

        self.image_label = QLabel("Waiting for camera frames...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(960, 540)

        self.status_label = QLabel(self._status_text())
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.save_button = QPushButton("Save snapshot")
        self.save_button.clicked.connect(self.save_snapshot)

        layout = QVBoxLayout()
        layout.addWidget(self.image_label, stretch=1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.save_button)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        quit_action = QAction("Close", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Close)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

        if request.quit_after_seconds is not None:
            QTimer.singleShot(int(request.quit_after_seconds * 1000), self.close)

    def _status_text(self) -> str:
        width, height, fps = capture_properties(self.capture)
        saved = (
            str(self.last_saved_path)
            if self.last_saved_path is not None
            else "none"
        )
        return (
            f"Device {self.request.config.device} | "
            f"{width}x{height} @ {fps:.2f} fps | "
            f"FOURCC={self.request.config.fourcc or 'default'} | "
            f"Last save: {saved}"
        )

    def _render_frame(self) -> None:
        if self.current_frame is None:
            return

        rgb_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_frame.shape
        image = QImage(
            rgb_frame.data,
            width,
            height,
            width * channels,
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def update_frame(self) -> None:
        """Read the next frame and refresh the preview."""

        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.status_label.setText("Failed to read a frame from the camera.")
            return

        self.current_frame = frame.copy()
        self._render_frame()
        self.status_label.setText(self._status_text())

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Re-scale the preview pixmap when the window size changes."""

        super().resizeEvent(event)
        self._render_frame()

    def save_snapshot(self) -> None:
        """Save the most recent frame to disk."""

        if self.current_frame is None:
            self.status_label.setText("No frame available yet to save.")
            return

        self.last_saved_path = save_frame(self.current_frame, self.request.output_dir)
        self.status_label.setText(self._status_text())

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Release the camera device when the window closes."""

        self.timer.stop()
        self.capture.release()
        super().closeEvent(event)


def main() -> None:
    """Launch the Qt preview application."""

    request = parse_args()
    app = QApplication([])
    window = CameraPreviewWindow(request)
    window.show()
    app.exec()
