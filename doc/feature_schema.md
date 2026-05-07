# Unified Feature Schema

## Goal

Define one shared window-level feature schema for the final dual-sensor project:

- vision branch: camera ROI motion spectrum
- sensor branch: 6-axis vibration spectrum (3-axis accelerometer + 3-axis gyroscope)

The main design rule is simple:

- one row = one time window
- one `sample_id` = one acquisition session or clip
- vision and sensor rows must share the same time-window definition
- fusion can happen by joining on `sample_id + window_index`

## Row Identity Fields

These fields should exist in both modalities.

| Field | Type | Meaning |
| --- | --- | --- |
| `sample_id` | string | Stable acquisition identifier |
| `label` | string | Class label, such as `normal`, `misaligned`, `loose`, `unknown` |
| `modality` | string | `vision` or `sensor` |
| `source_name` | string | Video name or sensor file name |
| `window_index` | int | Sliding-window index |
| `window_start_frame` | int | Start frame for vision, or mapped frame index for synchronized sensor data |
| `window_end_frame` | int | End frame for vision, or mapped frame index for synchronized sensor data |
| `center_time_s` | float | Center timestamp of the window in seconds |
| `analysis_fps` | float | Effective frame rate used in spectral analysis |

## Vision Fields

These fields are already produced by:

- `laboratory/legacy/motion-amplifier/scripts/analyze_video_stream.py`

### ROI Metadata

| Field | Type | Meaning |
| --- | --- | --- |
| `roi_x` | int | ROI x coordinate |
| `roi_y` | int | ROI y coordinate |
| `roi_w` | int | ROI width |
| `roi_h` | int | ROI height |

### Vision Spectrum Features

| Field | Type | Meaning |
| --- | --- | --- |
| `vision_dx_peak_hz` | float | Dominant frequency from x displacement |
| `vision_dy_peak_hz` | float | Dominant frequency from y displacement |
| `vision_dx_peak_power` | float | Peak spectral power in x |
| `vision_dy_peak_power` | float | Peak spectral power in y |
| `vision_dx_band_power` | float | Total band power in x |
| `vision_dy_band_power` | float | Total band power in y |
| `vision_dx_spectral_centroid_hz` | float | Spectral centroid in x |
| `vision_dy_spectral_centroid_hz` | float | Spectral centroid in y |
| `vision_dx_spectral_entropy` | float | Spectral entropy in x |
| `vision_dy_spectral_entropy` | float | Spectral entropy in y |

## Sensor Fields

These are the fields we should target when the 6-axis sensor branch is added.

### Raw Window Metadata

| Field | Type | Meaning |
| --- | --- | --- |
| `sensor_sample_rate_hz` | float | Sensor sampling rate |
| `sensor_window_duration_s` | float | Window duration |

### Accelerometer — Time-Domain Features (ax / ay / az)

| Field | Type | Meaning |
| --- | --- | --- |
| `sensor_ax_rms` | float | RMS of x-axis acceleration |
| `sensor_ay_rms` | float | RMS of y-axis acceleration |
| `sensor_az_rms` | float | RMS of z-axis acceleration |
| `sensor_ax_peak_to_peak` | float | Peak-to-peak x acceleration |
| `sensor_ay_peak_to_peak` | float | Peak-to-peak y acceleration |
| `sensor_az_peak_to_peak` | float | Peak-to-peak z acceleration |
| `sensor_ax_kurtosis` | float | Kurtosis of x-axis acceleration |
| `sensor_ay_kurtosis` | float | Kurtosis of y-axis acceleration |
| `sensor_az_kurtosis` | float | Kurtosis of z-axis acceleration |

### Accelerometer — Spectrum Features (ax / ay / az)

| Field | Type | Meaning |
| --- | --- | --- |
| `sensor_ax_peak_hz` | float | Dominant x-axis frequency |
| `sensor_ay_peak_hz` | float | Dominant y-axis frequency |
| `sensor_az_peak_hz` | float | Dominant z-axis frequency |
| `sensor_ax_peak_power` | float | Dominant x-axis power |
| `sensor_ay_peak_power` | float | Dominant y-axis power |
| `sensor_az_peak_power` | float | Dominant z-axis power |
| `sensor_ax_band_power` | float | Total x-axis band power |
| `sensor_ay_band_power` | float | Total y-axis band power |
| `sensor_az_band_power` | float | Total z-axis band power |
| `sensor_ax_spectral_centroid_hz` | float | Spectral centroid of x-axis |
| `sensor_ay_spectral_centroid_hz` | float | Spectral centroid of y-axis |
| `sensor_az_spectral_centroid_hz` | float | Spectral centroid of z-axis |
| `sensor_ax_spectral_entropy` | float | Spectral entropy of x-axis |
| `sensor_ay_spectral_entropy` | float | Spectral entropy of y-axis |
| `sensor_az_spectral_entropy` | float | Spectral entropy of z-axis |

### Gyroscope — Time-Domain Features (gx / gy / gz)

| Field | Type | Meaning |
| --- | --- | --- |
| `sensor_gx_rms` | float | RMS of x-axis angular velocity |
| `sensor_gy_rms` | float | RMS of y-axis angular velocity |
| `sensor_gz_rms` | float | RMS of z-axis angular velocity |
| `sensor_gx_peak_to_peak` | float | Peak-to-peak x angular velocity |
| `sensor_gy_peak_to_peak` | float | Peak-to-peak y angular velocity |
| `sensor_gz_peak_to_peak` | float | Peak-to-peak z angular velocity |
| `sensor_gx_kurtosis` | float | Kurtosis of x-axis angular velocity |
| `sensor_gy_kurtosis` | float | Kurtosis of y-axis angular velocity |
| `sensor_gz_kurtosis` | float | Kurtosis of z-axis angular velocity |

### Gyroscope — Spectrum Features (gx / gy / gz)

| Field | Type | Meaning |
| --- | --- | --- |
| `sensor_gx_peak_hz` | float | Dominant x-axis angular frequency |
| `sensor_gy_peak_hz` | float | Dominant y-axis angular frequency |
| `sensor_gz_peak_hz` | float | Dominant z-axis angular frequency |
| `sensor_gx_peak_power` | float | Dominant x-axis angular power |
| `sensor_gy_peak_power` | float | Dominant y-axis angular power |
| `sensor_gz_peak_power` | float | Dominant z-axis angular power |
| `sensor_gx_band_power` | float | Total x-axis angular band power |
| `sensor_gy_band_power` | float | Total y-axis angular band power |
| `sensor_gz_band_power` | float | Total z-axis angular band power |
| `sensor_gx_spectral_centroid_hz` | float | Spectral centroid of x-axis angular |
| `sensor_gy_spectral_centroid_hz` | float | Spectral centroid of y-axis angular |
| `sensor_gz_spectral_centroid_hz` | float | Spectral centroid of z-axis angular |
| `sensor_gx_spectral_entropy` | float | Spectral entropy of x-axis angular |
| `sensor_gy_spectral_entropy` | float | Spectral entropy of y-axis angular |
| `sensor_gz_spectral_entropy` | float | Spectral entropy of z-axis angular |

## Fusion Strategy

For the course project, the most practical fusion strategy is:

1. Generate window-level vision rows
2. Generate window-level sensor rows
3. Join by:
   - `sample_id`
   - `window_index`
   - or `center_time_s` after synchronization
4. Build a fused training table

Example fused table groups:

- shared identity fields
- `vision_*` fields
- `sensor_*` fields
- optional target field: `label`

## Why This Schema Fits The Final Goal

This schema is designed for the exact final task:

- real-time or near-real-time spectrum extraction
- stable sliding windows
- structured model input
- easy upgrade from traditional ML to deep learning

It supports both routes:

### Traditional ML

Use the fused table directly for:

- `RandomForest`
- `XGBoost`
- `SVM`

### Deep Learning

Use window sequences or stacked features for:

- `1D CNN`
- `LSTM`
- small temporal transformer

In other words:

- the schema is not tied to one specific model
- it gives us a clean bridge from signal processing to learning

## Current Status

Current implementation status:

- vision window-level extraction: done
- unified identity fields in vision output: done
- sensor branch extraction (6-axis accelerometer + gyroscope): pending
- synchronized fusion table: pending

## Next Implementation Step

The next concrete step should be:

- build a matching `sensor` sliding-window extractor that reads 6-axis sensor data and outputs the same identity fields plus `sensor_a*` (accelerometer) and `sensor_g*` (gyroscope) features

Once that exists, we can generate the first real fused dataset for model training.
