# Copilot Instructions

## Repository scope

- The repository now has **two active development areas** plus one archived lab:
  - the root `src/project_course` package, which is the pinned Python 3.10.12 scaffold for ongoing development
  - `laboratory/global-camera`, which is the active smoke-test project for the newly arrived global camera
  - `laboratory/legacy/motion-amplifier`, which is the archived visual-vibration prototype kept for reference
- The broader project goal is still the dual-sensor hardware system described in `laboratory/legacy/motion-amplifier/context.md`: camera-based vibration features plus a future 3-axis sensor branch.

## Build, test, and lint commands

Run these from the **repository root** for the main scaffold:

```bash
uv sync --all-groups
```

Install the root environment, including dev tools.

```bash
uv run --group dev ruff check .
```

Lint the root package and tests. `laboratory/legacy/motion-amplifier` is excluded from this lint scope because it is archived legacy code.

```bash
uv run --group dev pytest
```

Run the full root test suite.

```bash
uv run --group dev pytest tests/test_main.py
```

Run a single test file.

```bash
uv build
```

Build the root package.

```bash
uv run python -m project_course
```

Run the root CLI entry point.

Run these from `laboratory/global-camera` for the active camera bring-up project:

```bash
uv sync
uv run python -m global_camera_lab --help
```

For a real device smoke test:

```bash
uv run global-camera-lab --device 0 --backend v4l2 --save-frame
```

Run these from `laboratory/legacy/motion-amplifier` for the archived vision prototype:

```bash
uv run python scripts/analyze_video_stream.py --help
uv run python scripts/analyze_guitar.py --help
```

The archived prototype does **not** have its own automated test or lint setup yet. For a single-case smoke check on local sample data:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_video_stream.py \
  'data/phase/Source and Result Videos/car_engine.avi' \
  --sample-id car_engine-demo \
  --label unknown \
  --roi 520 170 620 260 \
  --fps-override 400 \
  --output-dir outputs/stream/car_engine_demo
```

## High-level architecture

- `src/project_course/` is the root package. It is intentionally small right now and acts as the stable starting point for code that should follow the pinned Python version and root lint/test workflow.
- `tests/` is the root automated-test area. Keep new root-level tests here instead of mixing them into the laboratory projects.
- `assets/hardware/` is the canonical storage location for hardware-related repository assets. The initial structure is:
  - `datasheets/`
  - `wiring/`
  - `calibration/`
  - `reference-images/`
- `laboratory/global-camera/README.md` documents the intended hardware bring-up workflow: open the camera, negotiate settings, capture frames, and optionally save a snapshot under `captures/`.
- `laboratory/global-camera/src/global_camera_lab/main.py` is the active CLI entry point for camera smoke testing. It is meant for practical device checks rather than long-term acquisition architecture.
- `laboratory/legacy/motion-amplifier/scripts/analyze_guitar.py` is the older **single-clip analyzer**. It loads frames, converts to grayscale, tracks Shi-Tomasi corners with pyramidal Lucas-Kanade optical flow, reduces tracks with a median motion signal, then estimates dominant vibration frequency with Welch PSD and saves preview/plot outputs.
- `laboratory/legacy/motion-amplifier/scripts/analyze_video_stream.py` is the newer **sliding-window feature extractor**. It reuses the same tracking pipeline but emits windowed `vision_*` features to CSV/JSON so the output can later join with sensor features.
- `laboratory/legacy/motion-amplifier/feature_schema.md` defines the target fused dataset contract: one row per time window, shared identity fields (`sample_id`, `window_index`, `center_time_s`, etc.), `vision_*` columns for camera features, and future `sensor_*` columns for the accelerometer branch.
- `laboratory/legacy/motion-amplifier/context.md` sets the project direction: the deliverable is a dual-measurement equipment-state recognizer, not a pure motion-magnification project. Visual vibration measurement is the main path; motion magnification is treated as a supporting visualization/debugging aid.
- `laboratory/legacy/motion-amplifier/experiment_guitar.md` and `laboratory/legacy/motion-amplifier/experiment_car_engine.md` are not just notes; they encode the current working assumptions for ROI choice, frame-rate override, and expected dominant-frequency bands on reference videos.

## Key conventions

- The root project is pinned to **Python 3.10.12** via `.python-version` and `requires-python == 3.10.12`. Preserve that exact version unless the repository is intentionally migrated.
- Use **`uv`** for all Python code areas, but treat the root scaffold, `laboratory/global-camera`, and `laboratory/legacy/motion-amplifier` as separate project contexts with their own commands and environments.
- New root-level Python code should stay **PEP 8-friendly** and pass the configured Ruff checks (`E`, `W`, `F`, `I`) with an 88-character line length.
- Keep hardware-related non-code assets under `assets/hardware/` using the existing category folders instead of scattering them under `doc/` or `laboratory/`.
- Use `laboratory/global-camera/captures/` for temporary camera snapshots from smoke tests; that directory is intentionally treated as disposable working output.
- The archived experiment docs consistently set `MPLCONFIGDIR=.mplconfig` and `UV_CACHE_DIR=.uv-cache` so Matplotlib and uv caches stay inside the project instead of polluting the home directory.
- Do **not** trust container FPS blindly. Both archived scripts support `--fps-override`, and the experiment workflow derives the meaningful analysis rate from acquisition context such as `sr600` or `sr400` embedded in source/result video names.
- Tight, textured **ROI selection is mandatory** in the archived motion-analysis pipeline. The documented experiments treat full-frame tracking as invalid for vibration measurement because it captures global scene motion instead of the target vibration.
- The codebase is already moving toward a **schema-first output format**. Vision rows should keep the shared identity fields and `vision_*` prefixes from `laboratory/legacy/motion-amplifier/scripts/analyze_video_stream.py`; future sensor work should mirror those identity fields and use `sensor_*` prefixes so fusion is a join, not a custom reshape.
- `laboratory/legacy/motion-amplifier/data/` and `laboratory/legacy/motion-amplifier/outputs/` are local working directories and are gitignored. Scripts are expected to read datasets from `data/` and write generated artifacts to `outputs/`.
- Despite its name, `laboratory/legacy/motion-amplifier/scripts/analyze_guitar.py` is used in both the guitar and car-engine experiment records as a **generic one-off video analyzer**. Do not assume it is guitar-specific unless you are intentionally renaming/refactoring it.
