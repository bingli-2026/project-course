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

### Sensor processing — UNASSIGNED (see Open Question §1 below)
- **Produces**: per-sample CSV with `sensor_*` columns
- **Consumes**: STM32 → Orange Pi sensor stream
- **Status**: `feature_schema.md` says "sensor branch extraction: pending". Until someone owns this, the dashboard will show `has_sensor: false` for every real sample.

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

## Open Questions (Block Coordination)

These are the things that, if left unanswered, will cause rework. Tagged for the team chat:

1. **Who owns sensor-side feature extraction?** `feature_schema.md` declares 30+ `sensor_*` columns but no team member's role explicitly covers it. Needed by ~2026-05-19 to leave time for fusion before midterm.

2. **Is YE Bingli's "back-end driver" the device driver or the web BE?** If the web BE — there is overlap with HE Xinhao's work and we need to split it. (Working assumption above: device driver only.)

3. **Where does YANG Xuanzhi's model run for the midterm demo?** HE Xinhao's working assumption (per 2026-05-10 conversation) is that inference runs on the edge and the web dashboard is display-only. If the model should actually be served from the web BE, the data contract needs `predicted_label` to be required and the BE needs new routes.

4. **Label vocabulary** — is `normal / unbalance / loose / misaligned / unknown` (per `data-contract.md`) the agreed set? The dataset and model accuracy depend on this being closed and stable.

5. **Window length** — is `window_duration_s` fixed at 0.5s for both modalities? `doc/context.md` mentions sliding windows but doesn't pin a number. Producers must agree before generating any "real" data, otherwise vision and sensor rows can't be fused.

A drop-in message you can paste into the team chat to resolve these is in [`team-alignment-questions.md`](team-alignment-questions.md).
