# Global Camera Laboratory

This subproject is for smoke-testing the newly arrived global camera on Linux.

## Setup

```bash
uv sync
```

## Quick check

```bash
uv run global-camera-lab --device 0 --backend v4l2 --save-frame
```

This opens the camera, negotiates the requested settings, grabs a few frames, prints the effective camera properties, and saves one snapshot under `captures/`.

## Higher-rate example

```bash
uv run global-camera-lab \
  --device 0 \
  --backend v4l2 \
  --width 1280 \
  --height 720 \
  --fps 120 \
  --fourcc MJPG \
  --warmup-frames 10 \
  --capture-frames 60 \
  --save-frame
```

## Asset locations

- Put reusable hardware references such as datasheets, wiring notes, and calibration references under the repository root `assets/hardware/`.
- Keep temporary camera test outputs in this project under `captures/`.
