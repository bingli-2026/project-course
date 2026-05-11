# Data Contract — Feature Files

> 中文版本: [`data-contract.zh.md`](data-contract.zh.md) (English is authoritative; the Chinese version is for team chat convenience.)


This document is the **operational rulebook** for the feature CSV/Parquet files exchanged between team members. It sits on top of [`feature_schema.md`](feature_schema.md), which defines the columns themselves. Read both before producing or consuming a feature file.

The web backend in `src/project_course/api/storage/ingest.py` enforces a subset of these rules at upload time. **If you change this contract, update `ingest.py` in the same commit.**

---

## 1. File Format

| Aspect | Rule |
|---|---|
| Extensions | `.csv` or `.parquet` only |
| CSV encoding | UTF-8, **no BOM** |
| CSV delimiter | `,` (comma) |
| CSV decimal separator | `.` (dot) — never `,` |
| Newline | `\n` or `\r\n` (pandas default is fine) |
| Floats | `float64`; round to 4 decimals where reasonable to keep payloads small |
| Booleans | encode as integers `0` / `1`, not `True` / `False` |
| Missing values | leave the cell empty in CSV; use `NaN` in Parquet |
| Compression (Parquet) | `snappy` (the default) is fine; don't use `brotli` |

Use **Parquet for files larger than ~5 MB**, CSV otherwise.

## 2. One File = One Sample

- A single file MUST contain rows for exactly **one** `sample_id`. The backend rejects multi-sample files (HTTP 422).
- A single sample MAY contain rows from one or both modalities (`vision`, `sensor`, or `fused`). The backend infers `has_vision` / `has_sensor` from whether columns prefixed `vision_` / `sensor_` are present and have non-null values.
- Recommended file name: `<sample_id>.csv` or `<sample_id>.parquet`. The filename is informational only — the source of truth is the `sample_id` column.

## 3. `sample_id` Naming

Format: `^[a-z][a-z0-9_]{2,63}$`

- lowercase ASCII letters, digits, underscores
- starts with a letter
- 3–64 characters total
- no spaces, no Chinese characters, no dashes, no dots

**Recommended pattern**: `<scenario>_<run>` or `<scenario>_<yyyymmdd>_<run>`

Examples:
- `gearbox_run01`
- `gearbox_unbalance_20260518_03`
- `demo_normal`

Bad:
- `Test 1.csv` (space, capital letter, name has extension)
- `齿轮箱实验1` (non-ASCII)
- `00-run` (starts with digit)

Once a `sample_id` is in use, **never reassign it to different data**. If you re-collect, bump the run number.

## 4. Required Columns (Hard)

Every row, every modality:

| Column | Type | Notes |
|---|---|---|
| `sample_id` | string | Same value on every row of the file |
| `window_index` | int (≥ 0) | 0, 1, 2, ... contiguous |
| `center_time_s` | float (≥ 0) | Center timestamp of the window in seconds |

Missing any of these → backend returns 422 with `missing_columns` listed.

## 5. Strongly Recommended Columns (Soft)

The dashboard renders much better when these are present. Producers should populate them whenever possible:

| Column | Type | Notes |
|---|---|---|
| `label` | string | See §6 vocabulary. Empty/NaN = "unlabeled" |
| `modality` | string | `vision`, `sensor`, or `fused` |
| `source_name` | string | Original video/sensor file name for traceability |
| `analysis_fps` | float | Effective sampling rate used for spectral analysis |
| `window_start_frame` | int | Inclusive |
| `window_end_frame` | int | Exclusive |

## 6. Label Vocabulary (Closed Set)

Until the team agrees otherwise, `label` MUST be one of:

```
normal
unbalance
loose
misaligned
unknown
```

Rules:
- lowercase, ASCII only
- exact spelling — `Loose`, `loose ` (trailing space), `松动` are all rejected by downstream tooling
- if you genuinely don't know, use `unknown` rather than leaving empty
- adding a new label requires a PR that updates this section AND `scripts/generate_demo_samples.py`

## 7. Window Alignment Between Modalities

When a sample contains both modalities, vision rows and sensor rows MUST share:

- the same `sample_id`
- the same `window_index` numbering scheme (0..N-1, no gaps)
- the same `center_time_s` for matching `window_index`
- the same `window_start_frame` / `window_end_frame` semantics if both are populated

Producers are responsible for resampling/synchronizing before writing the file. The web backend does **not** attempt to align mismatched windows — it ingests what it's given.

## 8. Optional/Reserved Columns

These columns are **reserved** for future use. If you produce them, follow the names below; if you don't need them, leave them out.

| Column | Type | Reserved for |
|---|---|---|
| `predicted_label` | string | Model output written back into the CSV |
| `prediction_confidence` | float (0–1) | Per-window confidence |
| `model_version` | string | e.g. `rf_v0.3` |

The current dashboard does not display these yet; they will be added once the model team confirms the format.

## 9. Validation Behavior

What the backend does on upload (`POST /api/v1/samples`) or startup scan:

| Condition | Result |
|---|---|
| Unsupported extension | 400 |
| Empty file or no rows | 422 |
| Missing required column | 422 with `missing_columns` array |
| Multiple distinct `sample_id` values | 422 |
| Schema OK, ingest succeeds | 201 (upload) or logged on startup scan |

Invalid uploads are deleted from disk; invalid files found by the startup scan are skipped with a warning log (they remain on disk so you can inspect them).

## 10. Examples

**Minimal vision-only row (CSV):**
```
sample_id,window_index,center_time_s,label,modality,vision_dx_peak_hz,vision_dy_peak_hz
gearbox_run01,0,0.25,normal,vision,12.4,14.1
gearbox_run01,1,0.75,normal,vision,12.5,14.0
```

**Minimal fused row (one row per window, both branches populated):**
```
sample_id,window_index,center_time_s,label,modality,vision_dx_peak_hz,sensor_ax_peak_hz
gearbox_run01,0,0.25,unbalance,fused,24.3,99.8
```

For a complete schema-compliant CSV, run `uv run python scripts/generate_demo_samples.py` and inspect `data/samples/demo_normal.csv`.

## 11. Owners

- **Schema columns** (which features exist): owned by [`feature_schema.md`](feature_schema.md)
- **Operational rules** (this file): owned by HE Xinhao (web BE/FE)
- **Backend enforcement**: `src/project_course/api/storage/ingest.py`
- **Reference producer**: `scripts/generate_demo_samples.py`

Changes that affect any of the above MUST update all three in the same commit/PR.
