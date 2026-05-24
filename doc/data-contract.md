# Data Contract — Window Samples

> 中文版本: [`data-contract.zh.md`](data-contract.zh.md) (English is authoritative; the Chinese version is for team chat convenience.)

This document is the **operational rulebook** for `WindowSample` rows — the unit of data exchanged between the feature pipeline, the model, the web backend, and the dashboard. It sits on top of [`feature_schema.md`](feature_schema.md), which defines which columns exist. Read both before producing or consuming a window sample.

The contract is enforced in two places:
- **Live path** — `src/project_course/api/live/state.py:publish_window(payload)`. The feature pipeline and the model call this in-process; no JSON / no HTTP.
- **Offline path** — `src/project_course/api/storage/ingest.py`. Validates CSV/Parquet files dropped into `data/samples/` for the history page.

**If you change this contract, update both files in the same commit.**

---

## 1. The Two Data Paths

The web backend, the feature pipeline, and the model inference all run **inside the same Python process** on the Orange Pi. Window samples flow in-process; nothing is serialized between them.

```
┌──────────────────────────────────────────────────────────────┐
│ Single Python process on the Orange Pi                       │
│                                                              │
│  Acquisition (YE Bingli, YANG Zhe)                           │
│    │ camera frames + IMU packets                             │
│    ▼                                                         │
│  Feature extraction (HE Xinhao + YANG Xuanzhi)               │
│    │                                                         │
│    │   call live.publish_window({...})                       │
│    ▼                                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ live.state.LIVE_STATE                                  │  │
│  │   - active_task: LiveTask | None                       │  │
│  │   - buffer: deque[WindowSample] (size 240)             │  │
│  │   - sync_quality: {offset_ms_p95, drift_ppm, ...}      │  │
│  └────────────────────────────────────────────────────────┘  │
│                  │            │                              │
│                  ▼            ▼                              │
│       Web BE routes      Model inference                     │
│       (reads buffer +    (reads buffer,                      │
│       persists window    writes predicted_state              │
│       into SQLite)       back via publish_window)            │
│                  │                                           │
│                  ▼ HTTP                                      │
│             Dashboard browser                                │
└──────────────────────────────────────────────────────────────┘

Offline path (history replay, demo rehearsals):

  data/samples/<sample_id>.csv  ─┐
                                 │ on startup or POST /api/v1/history
                                 ▼
                            ingest.py validates + writes to
                            history_samples table in SQLite
```

## 2. The `publish_window(payload)` Contract (Live Path)

`payload` is a `dict[str, Any]`. The backend does **not** validate the dict against the full schema at runtime — that would slow down the hot path and would happen too late anyway. Producers are on the honor system to populate fields correctly. Tests should cover the producer side.

### 2.1 Required Keys (Hard)

| Key | Type | Notes |
|---|---|---|
| `sample_id` | `str` | Stable identifier for this acquisition session. The live runtime uses the task's `task_id` for this. |
| `window_index` | `int (≥ 0)` | Sliding-window index, monotonically increasing within a task. Will be coerced via `int()` before SQLite insert. |
| `center_time_s` | `float (≥ 0)` | Window center timestamp in seconds. |

Missing any of these will cause `publish_window` to raise `KeyError` or the SQLite insert to fail.

### 2.2 Strongly Recommended Keys (Soft)

These are not enforced but the dashboard renders empty/None when they're absent.

| Key | Type | Used by |
|---|---|---|
| `label` | `str` (closed set, §6) | dashboard StateCard color mapping |
| `modality` | `"vision" \| "sensor" \| "fused"` | indicates which feature branch produced this row |
| `source_name` | `str` | traceability |
| `analysis_fps` | `float` | sanity check |
| `window_start_frame` / `window_end_frame` | `int` | reproducibility |

### 2.3 Feature Keys (the actual payload)

Any key starting with `vision_`, `sensor_`, or `fused_` is treated as a feature value. The schema in [`feature_schema.md`](feature_schema.md) lists what's expected per modality. The dashboard's SpectrumPanel and FusionTrend look for specific keys:

- `vision_dx_peak_hz`, `vision_dy_peak_hz` + `*_peak_power`
- `sensor_ax_peak_hz` ... `sensor_gz_peak_hz` + `*_peak_power`
- `fused_dominant_freq_hz`, `fusion_confidence`

Producers that don't fill these in will see the corresponding chart line missing.

### 2.4 Reserved Keys

`publish_window` recognizes these and updates task summary fields:

| Key | Effect |
|---|---|
| `predicted_state` | Updates `tasks.predicted_state` and the dashboard StateCard |
| `prediction_confidence` | Updates `tasks.confidence_summary` |
| `model_version` | (Not yet — task's model_version is set at `start_task` time) |

### 2.5 Sync Quality (Separate Call)

For metrics that don't change every window, use `live.record_sync_quality(...)` instead of repeating values inside every payload:

```python
from project_course.api.live import record_sync_quality

record_sync_quality(
    offset_ms_p95=1.23,
    drift_ppm=3.4,
    aligned_window_ratio=0.96,
)
```

Called typically every N seconds, not every window.

### 2.6 Example Producer Code

```python
from project_course.api.live import publish_window

publish_window({
    "sample_id": current_task.task_id,
    "window_index": w,
    "center_time_s": w * 0.25 + 0.25,
    "label": "unbalance",
    "modality": "fused",
    "analysis_fps": 420.0,
    "vision_dx_peak_hz": 24.5,
    "vision_dy_peak_hz": 26.0,
    "vision_dx_peak_power": 1.4,
    "vision_dy_peak_power": 1.6,
    "sensor_ax_peak_hz": 100.0,
    "sensor_ax_peak_power": 1.96,
    # ... rest of sensor_*, fused_* fields
    "predicted_state": "unbalance",
    "prediction_confidence": 0.88,
})
```

## 3. The CSV/Parquet Offline Contract (History Path)

Used for **demo rehearsals without hardware** and for replaying past acquisitions. The same schema applies, but the file is validated at ingest time (HTTP 422 on failure).

| Aspect | Rule |
|---|---|
| Extensions | `.csv` or `.parquet` only |
| CSV encoding | UTF-8, **no BOM** |
| CSV delimiter | `,` (comma) |
| CSV decimal separator | `.` (dot) — never `,` |
| Floats | round to 4 decimals where reasonable |
| Booleans | encode as `0` / `1` integers |
| Missing values | empty CSV cell, or `NaN` in Parquet |
| One file = one sample | distinct `sample_id` values are rejected |

Recommended file name: `<sample_id>.csv`. The filename is informational; the `sample_id` column is the source of truth.

### 3.1 Required CSV Columns

Same as §2.1: `sample_id`, `window_index`, `center_time_s`. Missing any returns HTTP 422 with a `missing_columns` array.

### 3.2 Where to Put Files

```
data/samples/<sample_id>.csv   <- drop files here
data/project_course.sqlite3    <- auto-generated index, do not edit
```

Backend startup scans `data/samples/` and ingests anything new. Or upload via the dashboard's history page (`/history` → top-right button).

## 4. `sample_id` Naming

Format: `^[a-z][a-z0-9_-]{2,63}$` (live tasks use `task-<12 hex>` which satisfies this).

- lowercase ASCII letters, digits, underscore, dash
- starts with a letter
- 3–64 characters

Recommended pattern for offline files: `<scenario>_<run>` or `<scenario>_<yyyymmdd>_<run>`. Examples: `gearbox_run01`, `gearbox_unbalance_20260518_03`.

Bad: `Test 1.csv` (space, capital), `齿轮箱实验1` (non-ASCII), `00run` (starts with digit).

**Once a `sample_id` is in use, never reassign it to different data.** Bump the run number instead.

## 5. Window Alignment Between Modalities

When a sample contains both vision and sensor rows:

- same `sample_id`
- same `window_index` numbering scheme (0..N-1, no gaps)
- same `center_time_s` for matching `window_index`

Producers do the alignment **before** publishing. The web backend does not attempt to fuse mismatched windows. The fused row (one per window, both branches populated) is the cleanest format and the simulator emits exactly that.

## 6. Label Vocabulary (Closed Set, Team-Confirmed 2026-05-11)

`label` MUST be one of:

```
normal
unbalance
loose
misaligned
unknown
```

Rules:
- lowercase, ASCII only — `Loose`, `loose ` (trailing space), `松动` are all wrong
- if you don't know, use `unknown`, not empty
- adding a new label requires a PR that updates §6, the dashboard `STATE_COLORS` map, and the simulator profiles

## 7. Window Parameters (Team-Confirmed 2026-05-11)

| Parameter | Value |
|---|---|
| `window_size_s` | 0.5 |
| `window_hop_s` | 0.25 |
| `imu_sample_rate_hz` | 1680 |
| `camera_mode` | `YUY2_160x140_420fps` |
| `analysis_fps` | 420.0 |

Configurable per-task via `POST /api/v1/tasks` request body. The defaults above are set in `src/project_course/api/config.py`. The earlier `0.25 / 0.05` values from `specs/.../plan.md` are kept as legacy reference.

## 8. Validation Behavior

For the **live path**, no validation — producers are trusted. Garbage in → garbage on the dashboard.

For the **offline path** (`POST /api/v1/history` or startup scan):

| Condition | Result |
|---|---|
| Unsupported extension | 400 |
| Empty file or no rows | 422 |
| Missing required column | 422 with `missing_columns` array |
| Multiple distinct `sample_id` values | 422 |
| Schema OK | 201 (upload) or logged on startup scan |

Invalid uploads are deleted from disk. Invalid files found during startup scan are kept on disk and logged as warnings so the operator can inspect.

## 9. Persistence

What the web backend persists:

| Data | SQLite table | Lifetime |
|---|---|---|
| Task metadata + summary | `tasks` | forever |
| Live window samples | `window_samples` | forever (FK cascade with `tasks`) |
| Offline history index | `history_samples` | forever |
| Original CSV/Parquet files | filesystem `data/samples/` | manually managed |
| Sync quality history | (just latest, in `tasks` row) | per-task |

What we **do not persist** (handled by hardware/edge):
- Raw camera frames
- Raw STM32 IMU packets
- Per-window spectrum arrays (the dashboard fakes these from peak features for the midterm demo)

## 10. Owners

- **Schema columns** (which features exist): `doc/feature_schema.md`
- **Operational rules** (this file): HE Xinhao (web BE/FE) + YANG Xuanzhi (model)
- **Live producer**: feature pipeline in same process — see §2.6 for example
- **Live consumer**: `src/project_course/api/storage/db.py:insert_window` + dashboard
- **Offline producer**: anyone with a valid CSV
- **Offline consumer**: `src/project_course/api/storage/ingest.py` + history page
- **Simulator (reference live producer)**: `src/project_course/api/live/simulator.py`

Changes that affect any of the above MUST update all three of `feature_schema.md`, this file, and `ingest.py` in the same commit.
