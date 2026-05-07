# Phase 1 Data Model - 与 feature_schema 对齐

## 1. ExperimentTask

- **用途**: 代表一次采集-融合-识别任务。
- **字段**:
  - `task_id` (string, required, unique)
  - `task_status` (enum: pending/running/succeeded/failed, required)
  - `created_at` (datetime, required)
  - `started_at` (datetime, optional)
  - `finished_at` (datetime, optional)
  - `device_id` (string, required)
  - `camera_mode` (string, required, 固定 `YUY2_160x140_420fps`)
  - `imu_sample_rate_hz` (int, required, default 1680)
  - `window_size_s` (float, required, default 0.25)
  - `window_hop_s` (float, required, default 0.05)
  - `roi_x`/`roi_y`/`roi_w`/`roi_h` (int, optional；为空时加载设备预设默认 ROI)
  - `model_version` (string, required)
  - `error_message` (string, optional)

## 2. IMUSamplePacket

- **用途**: STM32 上报的六轴原始样本包。
- **字段**:
  - `imu_seq` (int64, required, unique)
  - `t_imu_tick_us` (int64, required)
  - `ax`/`ay`/`az` (float, required)
  - `gx`/`gy`/`gz` (float, required)
  - `packet_crc_ok` (bool, required)

## 3. CameraFrameMeta

- **用途**: 摄像头帧级元数据。
- **字段**:
  - `frame_seq` (int64, required, unique)
  - `t_cam_host_s` (float, required)
  - `width` (int, required, =160)
  - `height` (int, required, =140)
  - `pixel_format` (string, required, =YUY2)
  - `frame_drop_flag` (bool, required)

## 4. TimeWindowSample（统一窗口特征行）

- **用途**: 双模态窗口样本，字段命名与 `doc/feature_schema.md` 对齐。
- **Identity 字段**:
  - `sample_id` (string, required, unique)
  - `label` (string, required)
  - `modality` (enum: vision/sensor/fused, required)
  - `source_name` (string, required)
  - `window_index` (int, required)
  - `window_start_frame` (int, required)
  - `window_end_frame` (int, required)
  - `center_time_s` (float, required)
  - `analysis_fps` (float, required)

- **Vision ROI 字段**:
  - `roi_x`, `roi_y`, `roi_w`, `roi_h` (int)

- **Vision 分轴频域字段**:
  - `vision_dx_peak_hz`, `vision_dy_peak_hz`
  - `vision_dx_peak_power`, `vision_dy_peak_power`
  - `vision_dx_band_power`, `vision_dy_band_power`
  - `vision_dx_spectral_centroid_hz`, `vision_dy_spectral_centroid_hz`
  - `vision_dx_spectral_entropy`, `vision_dy_spectral_entropy`

- **Sensor 元数据字段**:
  - `sensor_sample_rate_hz` (float)
  - `sensor_window_duration_s` (float)

- **Sensor 时域字段（ax/ay/az）**:
  - `sensor_ax_rms`, `sensor_ay_rms`, `sensor_az_rms`
  - `sensor_ax_peak_to_peak`, `sensor_ay_peak_to_peak`, `sensor_az_peak_to_peak`
  - `sensor_ax_kurtosis`, `sensor_ay_kurtosis`, `sensor_az_kurtosis`

- **Sensor 时域字段（gx/gy/gz）**:
  - `sensor_gx_rms`, `sensor_gy_rms`, `sensor_gz_rms`
  - `sensor_gx_peak_to_peak`, `sensor_gy_peak_to_peak`, `sensor_gz_peak_to_peak`
  - `sensor_gx_kurtosis`, `sensor_gy_kurtosis`, `sensor_gz_kurtosis`

- **Sensor 频域字段（ax/ay/az）**:
  - `sensor_ax_peak_hz`, `sensor_ay_peak_hz`, `sensor_az_peak_hz`
  - `sensor_ax_peak_power`, `sensor_ay_peak_power`, `sensor_az_peak_power`
  - `sensor_ax_band_power`, `sensor_ay_band_power`, `sensor_az_band_power`
  - `sensor_ax_spectral_centroid_hz`, `sensor_ay_spectral_centroid_hz`, `sensor_az_spectral_centroid_hz`
  - `sensor_ax_spectral_entropy`, `sensor_ay_spectral_entropy`, `sensor_az_spectral_entropy`

- **Sensor 频域字段（gx/gy/gz）**:
  - `sensor_gx_peak_hz`, `sensor_gy_peak_hz`, `sensor_gz_peak_hz`
  - `sensor_gx_peak_power`, `sensor_gy_peak_power`, `sensor_gz_peak_power`
  - `sensor_gx_band_power`, `sensor_gy_band_power`, `sensor_gz_band_power`
  - `sensor_gx_spectral_centroid_hz`, `sensor_gy_spectral_centroid_hz`, `sensor_gz_spectral_centroid_hz`
  - `sensor_gx_spectral_entropy`, `sensor_gy_spectral_entropy`, `sensor_gz_spectral_entropy`

- **同步与质量字段**:
  - `imu_sample_count` (int)
  - `cam_frame_count` (int)
  - `sync_offset_ms` (float)
  - `sync_drift_ppm` (float)
  - `sync_fit_failed` (bool, 拟合 R²<0.995 时为 true，该窗口不进入融合训练集)
  - `imu_quality_flag` (enum: ok/low_signal/missing)
  - `cam_quality_flag` (enum: ok/blur/occlusion/missing)
  - `seq_gap_count` (int, imu_seq 跳变次数，仅记录不丢弃)

- **展示派生字段（非主训练输入）**:
  - `fused_dominant_freq_hz` (float, optional)
  - `fusion_confidence` (float, optional)

## 5. FusedFeatureVector

- **用途**: 分类模型输入行（由 `vision_*` + `sensor_*` 字段拼接得到）。
- **字段**:
  - `sample_id` (string)
  - `window_index` (int)
  - `label` (string)
  - `features` (array[float], 长度随 schema 字段固定)
- **规则**:
  - 仅当 `imu_quality_flag=ok && cam_quality_flag=ok` 时进入训练集。

## 6. StateInferenceResult

- **字段**:
  - `result_id`, `task_id`, `predicted_state`, `confidence_summary`, `effective_window_count`, `generated_at`

## 7. ModelVersionRecord

- **字段**:
  - `model_version`, `parent_version`, `update_type`, `created_at`, `train_sample_count`, `artifact_path`

## 8. IncrementalUpdateReport

- **字段**:
  - `report_id`, `model_version_before`, `model_version_after`, `new_condition_metric`, `historical_metric`, `delta_new_condition`, `delta_historical`, `generated_at`

## 实体关系

- `ExperimentTask` 1:N `TimeWindowSample`
- `TimeWindowSample` -> `FusedFeatureVector`（窗口 join 后转换）
- `ExperimentTask` 1:1 `StateInferenceResult`
- `ModelVersionRecord` 1:N `ExperimentTask`
- `IncrementalUpdateReport` 关联 before/after 两个模型版本
