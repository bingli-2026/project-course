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
