# Implementation Plan: 软硬件WebAI一体化设备状态监测

**Branch**: `master` | **Date**: 2026-05-07 | **Spec**: `/specs/001-dual-modal-monitoring/spec.md`
**Input**: Feature specification from `/specs/001-dual-modal-monitoring/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

基于既定硬件链路（YUY2 160x140@420fps 摄像头 USB 直连香橙派 + STM32 六轴采样），实现双模态频率特征提取、特征级融合与状态识别。融合主线严格遵循 `doc/feature_schema.md`：先生成 `vision_*` 与 `sensor_*` 分轴窗口特征，再按 `sample_id + window_index` 拼接为统一向量，输入 RF/XGBoost/SVM 分类。前端数据大屏展示任务状态、频谱曲线、关键特征和分类结果。

## Technical Context

**Language/Version**: Python 3.10.12（采集/后端/融合）；TypeScript 5.x（前端大屏）  
**Primary Dependencies**: FastAPI、Uvicorn、NumPy、SciPy、OpenCV、scikit-learn、Pydantic Settings、React 18、Vite 5、ECharts 5、echarts-for-react、Axios  
**Storage**: SQLite（任务与版本元数据）+ 文件存储（窗口特征、频谱、模型工件）  
**Testing**: pytest + API 集成测试 + 采样/同步回放测试 + 前端冒烟  
**Target Platform**: 香橙派 Linux + USB UVC 摄像头 + STM32（CDC 串口）+ Chromium 浏览器  
**Project Type**: 单仓库后端服务 + 前端大屏 + 硬件采样支路  
**Performance Goals**: 采样任务端到端 ≤ 60s；大屏刷新周期 1s；窗口对齐成功率 ≥ 90%；时钟对齐误差 p95 ≤ 2ms  
**Constraints**: 摄像头固定 YUY2 160x140@420fps；STM32 负责六轴采样；不引入复杂深度学习；硬件依赖测试不纳入 CI 全量执行  
**Scale/Scope**: 1 套设备，3-5 状态类别，1-3 并发演示任务

## Sampling & Fusion Design

### 采样策略

- 摄像头：`YUY2`，`160x140`，`420fps`，通过 UVC/V4L2 从香橙派采集。
- 六轴（ax/ay/az + gx/gy/gz）：STM32 定时中断采样，目标采样率 `1680Hz`（与 420fps 保持 4:1 整数比）。
- 串口链路：STM32 通过 USB CDC 向香橙派发送样本包，建议 `921600` 波特率或更高。

### 串口吞吐预算（固化参数）

按每个 IMU 样本包估算：

- `imu_seq + tick`: 8 bytes
- 6 轴 float32: 24 bytes
- CRC: 2 bytes
- 合计: 34 bytes/样本

吞吐：

- 输入流量 `1680 * 34 = 57120 B/s`（约 55.8 KiB/s）
- `921600 bps / 10 = 92160 B/s`（8N1 理论字节率）
- 占用率约 `62%`，剩余约 `38%` 裕量

结论：921600 bps 可用，但需要开启串口缓冲和丢包计数监控。

### 时间同步策略

- 摄像头侧记录 `frame_seq` + 主机单调时钟 `t_cam_host_s`。
- STM32 侧记录 `imu_seq` + `t_imu_tick_us`。
- 主机建立映射 `t_host = a * t_imu_tick_us + b`（滑动窗口线性拟合），持续估计 offset 与 drift。
- 拟合窗口大小：`4.0s`（约 6720 个 IMU 点），兼顾抗抖动能力与漂移跟踪速度。
- 拟合质量门限：`R² >= 0.995` 视为有效；低于该阈值时该分析窗口标记 `sync_fit_failed`，不进入融合训练集。
- Tick 策略：采用 `32-bit 1MHz` MCU tick（约 71.6 分钟溢出一次）；主机侧按 `imu_seq` 单调性做 tick unwrap，恢复为逻辑 64-bit 时间轴。
- 重拟合策略：任务运行期间持续重拟合，每 `1.0s` 触发一次，拟合样本始终取最近 `4.0s` 窗口。
- 对齐后按 `sample_id + window_index` join，`center_time_s` 仅作校验字段。

### 窗口切分策略

- **默认（继承已验证原型）**：`window_size_s=0.25`，`window_hop_s=0.05`
- **可选（稳定展示模式）**：`window_size_s=1.0`，`window_hop_s=0.5`

默认值恢复到 legacy 原型，是因为该配置已在吉他/引擎样例上完成技术验证；1.0s 模式作为大屏低抖动展示配置，不替代默认实验配置。

### 增量更新最小样本阈值

- 每个新工况最少需要 `90` 个有效窗口样本，且至少来自 `3` 次独立采集任务，才允许触发增量更新。
- 阈值低于 90 时窗口间相关性过高，易导致更新后漂移；阈值远高于 90 会削弱“少样本增量”价值。
- 后端拒绝策略：若不满足阈值，返回可操作错误（缺少窗口数、缺少独立任务数）。

### ROI 获取策略（Web 化）

- MVP：创建任务接口支持可选 ROI 参数 `roi_x/roi_y/roi_w/roi_h`。
- 若不传 ROI，后端使用设备预设默认值（写入任务元数据并回显）。
- P1 不实现交互式框选；后续扩展为“前端首帧截图 + 手动框选”。

### 特征提取与融合主线（与 schema 一致）

- 视觉输出：`vision_dx_*`、`vision_dy_*` 分轴特征（peak_hz、peak_power、band_power、spectral_centroid_hz、spectral_entropy 等）。
- 传感器输出：`sensor_ax/ay/az_*` 与 `sensor_gx/gy/gz_*` 分轴特征（时域 + 频域）。
- 融合方式：
  1. 生成窗口级 `vision` 行和 `sensor` 行
  2. 按 `sample_id + window_index` join
  3. 得到 fused feature vector（`vision_* + sensor_*`）
  4. 输入 RF/XGBoost/SVM 进行状态分类

说明：`fused_dominant_freq_hz` 可作为展示派生指标保留，但不作为主分类输入的唯一特征。

### 代码复用策略

- `src/project_course/camera/core.py` 与 `src/project_course/camera/v4l2.py` 作为主线摄像头采集基础模块复用。
- 新增 `capture_service` 仅负责任务编排、同步与窗口化，不重复实现底层 V4L2 能力。
- `laboratory/` 中硬件探索代码不直接 import 到主线，通过明确接口迁移。

### STM32 协议契约策略

- 串口首包必须为握手包：包含 `protocol_version`、`imu_sample_rate_hz`、`axis_order`、`tick_hz`、`frame_format`。
- 后端在任务开始阶段必须校验握手包与任务配置一致，不一致则拒绝启动。
- 若 STM32 协议变更，本仓库需同步更新以下文件：
  - `src/project_course/services/capture_service.py`（采样任务编排与握手校验）
  - `src/project_course/fusion/time_sync.py`（tick 映射与 unwrap 逻辑）
  - `src/project_course/fusion/schema.py`（字段映射）
  - `tests/contract/` 下对应协议与接口契约测试

### 错误恢复路径

| 故障模式 | 检测方式 | 阈值/超时 | 恢复动作 |
|---|---|---|---|
| 串口无数据 | 连续读空包计时 | `>= 500ms` | 标记 `imu_stream_timeout`，尝试重连串口 1 次；失败则任务失败并提示检查线缆/波特率 |
| 摄像头帧中断 | 帧间时间差监控 | `> 3 * (1/420)s` | 标记 `camera_frame_gap`，触发相机流重启；重启失败则任务失败 |
| `imu_seq` 跳变 | 序号差分检查 | `delta != 1` | 不丢弃整任务；标记受影响窗口 `imu_quality_flag=low_signal` 并记录 `seq_gap_count` |
| 磁盘空间不足 | 任务启动前预检 | 剩余空间 `< 预估写入量 * 1.5` | 拒绝启动并返回所需/剩余空间提示 |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. 双模态 Schema-First**: PASS  
  data-model 与 contract 字段命名对齐 `doc/feature_schema.md`，保留分轴特征并以 join 作为唯一融合入口。
- **II. 实验室-主线分离**: PASS  
  STM32 驱动与硬件探索在 `laboratory/`；主线融合、API、大屏在 `src/project_course/` 与 `frontend/dashboard/`。
- **III. 增量可交付 & 独立可测**: PASS  
  P1（采样+融合识别闭环）、P2（大屏展示）、P3（增量更新）独立可验收。
- **IV. 可重复性优先**: PASS  
  采样率、窗口参数、串口吞吐预算、同步拟合策略均已固化。
- **V. YAGNI & 范围控制**: PASS  
  保持传统 ML + 轻量增量，不引入复杂深度模型。
- **VI. 测试分级**: PASS  
  主线模块要求 pytest 与集成测试；硬件链路保持实验室 smoke test。

**Post-Design Re-check**: PASS  
Phase 1 产物与 `feature_schema/context` 路线保持一致，并补全了同步参数、协议契约、ROI 与错误恢复策略，无新增违例。

## Project Structure

### Documentation (this feature)

```text
specs/001-dual-modal-monitoring/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api.yaml
└── tasks.md
```

### Source Code (repository root)

```text
src/project_course/
├── api/
│   ├── routers/
│   └── ...
├── camera/
│   ├── core.py
│   ├── v4l2.py
│   └── cli.py
├── fusion/
│   ├── schema.py
│   ├── imu_features.py
│   ├── camera_features.py
│   ├── time_sync.py
│   └── feature_vector_fusion.py
├── services/
│   ├── capture_service.py
│   ├── task_service.py
│   └── model_update_service.py
└── main.py

frontend/dashboard/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── pages/
│   ├── components/
│   ├── hooks/
│   ├── store/
│   └── services/
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json

tests/
├── contract/
├── integration/
└── unit/

laboratory/
└── global-camera/
```

**Structure Decision**: 采用“单仓库 + 前后端分层 + 主线复用 camera 模块 + 硬件实验隔离”结构，满足交付稳定性与实验灵活性。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 无 | N/A | N/A |
