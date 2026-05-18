# Team Interfaces

> 中文版本: [`team-interfaces.zh.md`](team-interfaces.zh.md) (English is authoritative; the Chinese version is for team chat convenience.)


A one-page map of who produces what, who consumes what, and where it lives in the repo. The goal is to avoid silent overlaps (two people building the same thing) and silent gaps (no one building something everyone assumed).

The roles below come from the proposal's personnel section. If anyone disagrees with their listed scope, raise it before writing code — it's much cheaper to renegotiate now than to merge two parallel implementations later.

---

## At a Glance

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Hardware/Acquisition                                                   │
│  ─────────────────────                                                  │
│  Motor + gearbox  ──►  ADXL345  ──►  STM32  ──►  Orange Pi              │
│   (GAN Yunxuan,        (sensor)     (acq +     (host computer,          │
│    YANG Zhe)                         control,   YE Bingli)              │
│                                      driver)                            │
│                          Camera  ──────────────►                        │
│                       (YE Bingli)                                       │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ raw video + raw sensor stream
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Feature Extraction (offline / on Orange Pi)                            │
│  ────────────────────────────────────────                               │
│  Visual processing                Sensor processing                     │
│   (ZHANG Zhanshuo)                 (TBD — see Open Q)                   │
│   produces vision_* features       produces sensor_* features           │
│   in a CSV per sample              in a CSV per sample                  │
│                                                                         │
│   Both write to:  data/samples/<sample_id>.csv                          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ feature CSV/Parquet
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Storage + Display (web stack)        Modeling (offline)                │
│  ────────────────────────────         ─────────────────                 │
│  Web BE (FastAPI)                     Model training                    │
│   (HE Xinhao) — this codebase          (YANG Xuanzhi)                   │
│   ingest, index, serve via              consumes data/samples/,         │
│   /api/v1/samples                       trains classifier,              │
│                                         (later) writes predictions      │
│  Web FE (React/Vite)                    back into CSVs                  │
│   (HE Xinhao)                                                           │
│   list / detail / charts                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                           Documentation & QA
                           (ZHANG Jiaxin)
```

---

## Per-Person Contract

### YE Bingli — Teacher liaison, backend driver, camera data collection
- **Produces**: raw camera video files; STM32 ↔ Orange Pi communication driver
- **Consumes**: hardware from GAN Yunxuan / YANG Zhe
- **Hands off to**: ZHANG Zhanshuo (raw video for visual processing)
- **Where in repo**: `src/project_course/camera/` (camera CLI tools already exist)
- **Note on "back-end driver"**: this means the **device-side driver software** between STM32 and Orange Pi, NOT the web backend. To avoid confusion, prefer the term *"acquisition driver"* in commits and chat.

### ZHANG Zhanshuo — Visual data processing
- **Produces**: per-sample CSV with `vision_*` columns, conforming to [`data-contract.md`](data-contract.md) and [`feature_schema.md`](feature_schema.md)
- **Consumes**: raw videos from YE Bingli
- **Hands off to**: HE Xinhao (drops file into `data/samples/`) and YANG Xuanzhi (same file)
- **Where in repo**: visual processing scripts under `laboratory/` (current location) — long-term should move to `src/project_course/vision/`

### Sensor processing — HE Xinhao + YANG Xuanzhi (co-owned, resolved 2026-05-11)
- **Produces**: in-process `WindowSample` payloads with `sensor_*` fields populated, pushed via `live.publish_window`
- **Consumes**: STM32 → Orange Pi sensor stream surfaced by YE Bingli's acquisition driver
- **Where in repo**: target `src/project_course/fusion/imu_features.py` (planned in `specs/.../tasks.md` T018)

### YANG Xuanzhi — Model training
- **Produces**: trained model artefacts (NOT served by the web BE for the May 26 milestone — runs offline / on edge per HE Xinhao's clarification on 2026-05-10)
- **Consumes**: `data/samples/*.csv` (the same files the dashboard reads)
- **Hands off to**: edge runtime on Orange Pi
- **Optional later**: write `predicted_label` / `prediction_confidence` columns back into CSVs (reserved in the data contract)
- **Where in repo**: TBD — suggest `src/project_course/modeling/`

### HE Xinhao — Web frontend & backend (this codebase)
- **Produces**: web dashboard at `http://localhost:5173` + REST API at `http://localhost:8000/api/v1`
- **Consumes**: `data/samples/*.csv` (read-only) — does **not** write back
- **Where in repo**: `src/project_course/api/`, `frontend/dashboard/`
- **Out of scope**: model inference, real-time streaming, incremental learning, raw-video storage

### GAN Yunxuan / YANG Zhe — Hardware
- **Produces**: working physical setup (motor + gearbox + accelerometer + STM32 board); BOM / wiring documentation
- **Consumes**: budget items
- **Hands off to**: YE Bingli (working hardware to acquire data from)
- **Where in repo**: hardware notes, schematics, BOM under `doc/hardware/` (to be created)

### ZHANG Jiaxin — Documentation & testing
- **Produces**: proposal / midterm / final reports; test plans; defense PPT
- **Consumes**: everyone else's outputs
- **Where in repo**: `doc/`

---

## File-System Boundaries

| Path | Owner | Read by |
|---|---|---|
| `src/project_course/api/` | HE Xinhao | — |
| `frontend/dashboard/` | HE Xinhao | — |
| `data/samples/` | feature producers (Zhang Zhanshuo + sensor owner) | HE Xinhao (web BE), YANG Xuanzhi (model) |
| `data/project_course.sqlite3` | auto-generated by web BE | — (do not edit by hand) |
| `src/project_course/camera/` | YE Bingli | — |
| `laboratory/` | ZHANG Zhanshuo (vision prototypes) | reference only |
| `doc/` | everyone (PR-reviewed) | everyone |

**Do not write into `data/project_course.sqlite3` directly.** It's an index rebuilt from `data/samples/` on every backend startup. If you need to clear it, just delete the file.

---

## Resolved Decisions (Team chat, 2026-05-11)

All five blocking questions are answered. Originals tracked in [`team-alignment-questions.md`](team-alignment-questions.md) (archived).

1. **Sensor-side feature extraction owner** — HE Xinhao + YANG Xuanzhi (co-ownership, same Python process as the web backend). Updates `team-interfaces.md` above: sensor processing is no longer "TBD".

2. **YE Bingli's "back-end driver"** — confirmed = **device-side acquisition driver** (STM32 ↔ Orange Pi data link, plus camera ingestion). NOT the web backend. YANG Zhe owns the hardware-to-Python interface above the STM32.

3. **Model serving for midterm demo** — model runs on the **edge node (Orange Pi)** in the same Python process as the web backend. No separate gRPC/REST hop for midterm. Later upgrade to a standalone model service is possible without changing the data contract.

4. **Label vocabulary** — adopted: `normal / unbalance / loose / misaligned / unknown`. Closed set, lowercase ASCII, strict spelling. Any extension goes through a versioned PR; no main vocabulary changes before midterm. See [`data-contract.md`](data-contract.md) §6.

5. **Window length** — `window_size_s = 0.5`, `window_hop_s = 0.25`. Both modalities share this. See [`data-contract.md`](data-contract.md) §7. The web backend doesn't persist raw sliding-window arrays; features are computed on the edge and pushed into the web BE via `live.publish_window`.

## Updated Per-Person Contract Deltas

The team chat answers change three lines in §"Per-Person Contract" above:

- **Sensor processing — UNASSIGNED** → now jointly owned by HE Xinhao + YANG Xuanzhi, runs in-process with the web BE on the Orange Pi.
- **YANG Xuanzhi — Model training** → also responsible for **model inference at edge runtime** in the same Python process. Predictions are pushed back into the live buffer via `live.publish_window({..., "predicted_state": ..., "prediction_confidence": ...})` — no separate HTTP service for midterm.
- **HE Xinhao — Web frontend & backend** → web BE now exposes `live.publish_window` and `live.record_sync_quality` as the in-process API for feature/model code; remains read-only consumer of the buffer for HTTP routes.
