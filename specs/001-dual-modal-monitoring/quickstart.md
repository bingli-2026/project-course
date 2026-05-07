# Quickstart - YUY2@420fps + STM32 六轴融合演示

## 1. 目标

在 10 分钟内完成一次真实硬件链路演示：

1. 以 `YUY2 160x140@420fps` 采集视频
2. 以 `1680Hz` 采集 STM32 六轴数据
3. 按 `0.25s/0.05s` 默认窗口完成对齐与特征融合
4. 在前端大屏查看分轴频谱与分类结果

## 2. 前置条件

- 摄像头通过 USB 直连香橙派并可被 V4L2 识别
- STM32 通过 USB CDC 连到香橙派，可稳定输出六轴数据
- 已安装项目依赖

## 3. 启动步骤

### 3.1 启动后端

```bash
uv run project-course-api-dev
```

### 3.2 启动前端大屏

```bash
cd frontend/dashboard
npm install
npm run dev
```

## 4. 创建采样任务（默认 legacy 窗口）

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id":"rig-01",
    "camera_mode":"YUY2_160x140_420fps",
    "imu_sample_rate_hz":1680,
    "window_size_s":0.25,
    "window_hop_s":0.05
  }'
```

## 5. 查询结果

### 5.1 任务与同步质量

```bash
curl -sS http://127.0.0.1:8000/api/v1/tasks/<task_id>
```

关注：

- `sync_quality.offset_ms_p95 <= 2.0`
- `sync_quality.aligned_window_ratio >= 0.90`

### 5.2 窗口级分轴特征

```bash
curl -sS http://127.0.0.1:8000/api/v1/tasks/<task_id>/windows
```

检查存在：

- `vision_dx_peak_hz`, `vision_dy_peak_hz`
- `sensor_ax_peak_hz ... sensor_gz_peak_hz`
- `sensor_ax_band_power ... sensor_gz_band_power`

### 5.3 频谱曲线（大屏画图）

```bash
curl -sS "http://127.0.0.1:8000/api/v1/tasks/<task_id>/spectra?window_index=0"
```

## 6. 验收判定

- 端到端任务成功完成（无人工补录）
- API 输出字段与 `doc/feature_schema.md` 命名一致
- 大屏可展示分轴频谱曲线与分类结论
