# project-course

## Root project

The mainline Python package lives in `src/project_course`.

## Camera tools

List detected V4L2 devices and video nodes:

```bash
uv run project-course-camera list
```

Then probe the device you want to use:

```bash
uv run project-course-camera probe \
  --device <index> \
  --backend v4l2 \
  --fourcc YUYV \
  --width 1280 \
  --height 720 \
  --fps 60
```

For the interactive Qt preview window, use `laboratory/global-camera`.

## FastAPI service

Run API in standard mode:

```bash
uv run project-course-api
```

Run API in development hot-reload mode:

```bash
uv run project-course-api-dev
```

## IMU tools (ATK-MS6DSV)

Run the MS6DSV capture CLI (Orange Pi):

```bash
uv run project-course-ms6dsv \
  --bus 7 \
  --address 0x6A \
  --odr-hz 480 \
  --target-hz 480 \
  --duration-s 5 \
  --log-path artifacts/logs/ms6dsv_capture.log \
  --output artifacts/ms6dsv_capture.csv
```

Current recommended stable profile is `480 Hz` for both sensor ODR and host
capture target rate on Orange Pi I2C.

By default the CLI uses soft fallback: if hardware is unavailable, it logs a
warning and exits successfully so non-hardware development is not blocked.
Use `--strict-hardware` in CI or hardware validation stages.
