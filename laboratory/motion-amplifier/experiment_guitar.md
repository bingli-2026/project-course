# Guitar Experiment Record

## Goal

Use the official `guitar` sample video to verify the core visual vibration-frequency pipeline:

`ROI -> feature tracking -> displacement signal -> Welch spectrum -> dominant frequency`

This experiment is meant to answer one question first:

Can the visual pipeline recover a physically meaningful vibration frequency from a known vibrating target?

## Data Sources

Source videos used in this round:

- `[data/phase/Source and Result Videos/guitar.avi](/home/davisye/test/test-motion-amplifier/data/phase/Source%20and%20Result%20Videos/guitar.avi)`
- `[data/phase/Source and Result Videos/results/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave.avi](/home/davisye/test/test-motion-amplifier/data/phase/Source%20and%20Result%20Videos/results/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave.avi)`

Reference frame preview:

- `[outputs/guitar/guitar_first_frame.png](/home/davisye/test/test-motion-amplifier/outputs/guitar/guitar_first_frame.png)`

## Environment

Python environment is managed with `uv`.

Project config:

- `[pyproject.toml](/home/davisye/test/test-motion-amplifier/pyproject.toml)`

Analysis script:

- `[scripts/analyze_guitar.py](/home/davisye/test/test-motion-amplifier/scripts/analyze_guitar.py)`

Installed analysis dependencies:

- `numpy`
- `scipy`
- `opencv-python`
- `matplotlib`

## Video Metadata

Both the source and result video containers report:

- frame size: `432 x 192`
- frame count: `300`
- metadata fps: `29.97`

Important note:

- The official result filename includes `sr600`, which indicates the meaningful analysis frame rate is `600 fps`
- Therefore this experiment uses `--fps-override 600`
- This confirms a key engineering rule for the project: container metadata is not always the real acquisition frame rate

## First Attempt: Full-Frame Tracking

Command:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_guitar.py \
  'data/phase/Source and Result Videos/guitar.avi' \
  --output-dir outputs/guitar/source_metadata
```

Result:

- dominant `dx`: `3.9804 Hz`
- dominant `dy`: `4.0975 Hz`

Interpretation:

- Full-frame tracking was dominated by low-frequency global motion
- The pipeline locked onto overall scene movement instead of string vibration
- This result is not useful as the target vibration estimate

Conclusion:

- Full-frame analysis is not valid for this kind of task
- Tight ROI selection is required

## Second Attempt: String ROI With 600 fps Override

Selected ROI:

- `x=15`
- `y=40`
- `w=210`
- `h=70`

Reason:

- This rectangle covers the visible string region and excludes most of the guitar body and other low-frequency motion

Command:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_guitar.py \
  'data/phase/Source and Result Videos/guitar.avi' \
  --fps-override 600 \
  --roi 15 40 210 70 \
  --min-frequency 20 \
  --output-dir outputs/guitar/strings_roi_fps600
```

Result:

- processed frames: `300`
- valid tracked points: `117`
- dominant `dx`: `79.6875 Hz`
- dominant `dy`: `79.6875 Hz`

Output files:

- `[outputs/guitar/strings_roi_fps600/guitar_preview.png](/home/davisye/test/test-motion-amplifier/outputs/guitar/strings_roi_fps600/guitar_preview.png)`
- `[outputs/guitar/strings_roi_fps600/guitar_analysis.png](/home/davisye/test/test-motion-amplifier/outputs/guitar/strings_roi_fps600/guitar_analysis.png)`

Interpretation:

- Once the ROI is constrained to the strings, the dominant frequency moves into the expected high-frequency band
- The result falls near `80 Hz`, which is consistent with the official result video naming convention `band72.00-92.00`

## Third Attempt: Official Magnified Result Video

Command:

```bash
MPLCONFIGDIR=.mplconfig UV_CACHE_DIR=.uv-cache uv run python scripts/analyze_guitar.py \
  'data/phase/Source and Result Videos/results/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave.avi' \
  --fps-override 600 \
  --roi 15 40 210 70 \
  --min-frequency 20 \
  --output-dir outputs/guitar/strings_roi_result_fps600
```

Result:

- processed frames: `300`
- valid tracked points: `105`
- dominant `dx`: `79.6875 Hz`
- dominant `dy`: `82.0312 Hz`

Output files:

- `[outputs/guitar/strings_roi_result_fps600/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave_preview.png](/home/davisye/test/test-motion-amplifier/outputs/guitar/strings_roi_result_fps600/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave_preview.png)`
- `[outputs/guitar/strings_roi_result_fps600/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave_analysis.png](/home/davisye/test/test-motion-amplifier/outputs/guitar/strings_roi_result_fps600/guitar-FIRWindowBP-band72.00-92.00-sr600-alpha25-mp0-sigma2-halfOctave_analysis.png)`

Interpretation:

- The magnified result video does not fundamentally change the recovered dominant band
- The estimated dominant frequencies remain around `80 Hz`
- This supports the current project view that motion magnification is useful as an auxiliary aid, but not strictly required for primary frequency extraction

## Main Findings

1. The visual frequency-extraction pipeline works on the official `guitar` sample.
2. ROI selection is critical. Full-frame tracking fails for this task.
3. The correct frame rate must be set from acquisition context, not blindly read from container metadata.
4. The current optical-flow-based method can recover a stable dominant band around `80 Hz`.
5. Official magnification improves visibility, but the core measurable frequency is already recoverable from the source video when ROI is chosen correctly.

## What This Means For The Project

This experiment is an important positive signal for the course project:

- It validates the feasibility of the visual measurement chain
- It supports using `ROI motion tracking + spectral analysis` as the main visual path
- It further supports keeping motion magnification as a secondary visualization or debugging tool

The lesson that should carry into the real hardware stage:

- always control ROI tightly
- always record real acquisition fps
- always avoid using full-frame motion as the main vibration signal

## Next Recommended Experiment

Next target:

- `car_engine`

Reason:

- It is closer to the machine vibration use case than `guitar`
- It is more relevant to the final dual-sensor equipment-state project

Suggested next objective:

- verify whether the same pipeline can recover a stable dominant band from an engine vibration video
