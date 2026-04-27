# Car Engine Experiment Record

## Goal

Use the official `car_engine` sample to verify whether the same visual vibration pipeline used on `guitar` also works on a machine-like target.

This is closer to the final course-project scenario than the guitar case.

Pipeline:

`ROI -> feature tracking -> displacement signal -> Welch spectrum -> dominant frequency`

## Data Sources

Source video:

- `[data/phase/Source and Result Videos/car_engine.avi](/home/davisye/test/test-motion-amplifier/data/phase/Source%20and%20Result%20Videos/car_engine.avi)`

Official magnified result:

- `[data/phase/Source and Result Videos/results/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave.avi](/home/davisye/test/test-motion-amplifier/data/phase/Source%20and%20Result%20Videos/results/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave.avi)`

Reference frames:

- `[outputs/car_engine/car_engine_first_frame.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/car_engine_first_frame.png)`
- `[outputs/car_engine/car_engine_result_first_frame.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/car_engine_result_first_frame.png)`

## Video Metadata

Both files report:

- frame size: `1776 x 904`
- frame count: `300`
- metadata fps: `25`

Important context:

- The official result filename includes `sr400`
- For analysis, this experiment therefore uses `--fps-override 400`
- As with the `guitar` case, acquisition frame rate matters more than the playback/container fps

## Tested ROIs

Two source-video ROIs were tested.

### ROI A: Cover Center

- `x=520`
- `y=170`
- `w=620`
- `h=260`

Why:

- Contains textured engine-cover surface
- Has stable edges and embossed structure
- Avoids excessive background clutter

### ROI B: Right Ribs

- `x=1070`
- `y=150`
- `w=260`
- `h=300`

Why:

- Strong vertical rib texture
- Good for repeated edge-based tracking

## Source Video Results

### Test A: Cover Center ROI

Command:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_guitar.py \
  'data/phase/Source and Result Videos/car_engine.avi' \
  --fps-override 400 \
  --roi 520 170 620 260 \
  --min-frequency 5 \
  --output-dir outputs/car_engine/cover_center_fps400
```

Result:

- processed frames: `300`
- valid tracked points: `150`
- dominant `dx`: `15.6250 Hz`
- dominant `dy`: `21.8750 Hz`

Outputs:

- `[outputs/car_engine/cover_center_fps400/car_engine_preview.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/cover_center_fps400/car_engine_preview.png)`
- `[outputs/car_engine/cover_center_fps400/car_engine_analysis.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/cover_center_fps400/car_engine_analysis.png)`

### Test B: Right Ribs ROI

Command:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_guitar.py \
  'data/phase/Source and Result Videos/car_engine.avi' \
  --fps-override 400 \
  --roi 1070 150 260 300 \
  --min-frequency 5 \
  --output-dir outputs/car_engine/right_ribs_fps400
```

Result:

- processed frames: `300`
- valid tracked points: `150`
- dominant `dx`: `15.6250 Hz`
- dominant `dy`: `21.8750 Hz`

Outputs:

- `[outputs/car_engine/right_ribs_fps400/car_engine_preview.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/right_ribs_fps400/car_engine_preview.png)`
- `[outputs/car_engine/right_ribs_fps400/car_engine_analysis.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/right_ribs_fps400/car_engine_analysis.png)`

## Official Result Video Check

Command:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_guitar.py \
  'data/phase/Source and Result Videos/results/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave.avi' \
  --fps-override 400 \
  --roi 520 170 620 260 \
  --min-frequency 5 \
  --output-dir outputs/car_engine/result_cover_center_fps400
```

Result:

- processed frames: `300`
- valid tracked points: `150`
- dominant `dx`: `15.6250 Hz`
- dominant `dy`: `21.8750 Hz`

Outputs:

- `[outputs/car_engine/result_cover_center_fps400/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave_preview.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/result_cover_center_fps400/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave_preview.png)`
- `[outputs/car_engine/result_cover_center_fps400/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave_analysis.png](/home/davisye/test/test-motion-amplifier/outputs/car_engine/result_cover_center_fps400/car_engine-FIRWindowBP-band15.00-25.00-sr400-alpha15-mp0-sigma3-octave_analysis.png)`

## Main Findings

1. The visual frequency pipeline transfers successfully from `guitar` to a machine-like sample.
2. The dominant frequencies land inside the same band suggested by the official result naming: `15-25 Hz`.
3. Two different textured ROIs on the engine cover produce the same dominant-band estimate.
4. The source video and the official magnified result video give the same dominant frequencies in this experiment.
5. This is another strong sign that motion magnification is helpful for visibility but not strictly necessary for primary frequency extraction.

## Interpretation

The pair of peaks:

- `15.625 Hz`
- `21.875 Hz`

likely indicates:

- one dominant mechanical vibration component
- plus another strong component, harmonic, structural mode, or axis-dependent response

At this stage, the important result is not choosing which one is "the only true frequency."
The important result is:

- the pipeline consistently extracts stable peaks
- those peaks fall in the expected engine-vibration band
- the result is repeatable across different ROIs and the magnified reference

## What This Means For The Project

This experiment is a stronger project signal than `guitar`, because it is structurally closer to your final machine-state use case.

It supports the following design decisions:

- keep `ROI motion tracking + frequency analysis` as the main visual path
- treat motion magnification as an auxiliary visualization tool
- rely on textured local regions rather than whole-frame motion
- always carry the real acquisition fps as explicit metadata into analysis

## Next Recommended Step

Best next move:

- rename the script from `analyze_guitar.py` to a general name such as `analyze_video.py`
- standardize the experiment-output format
- then start building a reusable feature extractor for:
  - dominant peaks
  - peak amplitudes
  - band energy
  - spectral entropy
  - ROI consistency

That will move us from "single demo measurements" toward the feature pipeline needed for the final dual-sensor classifier.
