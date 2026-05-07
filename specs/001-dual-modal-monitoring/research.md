# Phase 0 Research - 采样与融合修订版

## 决策 1：六轴采样率定为 1680Hz

- **Decision**: STM32 六轴采样率固定 `1680Hz`，与摄像头 `420fps` 形成 4:1 整数比。
- **Rationale**: 便于帧-传感器窗口对齐，降低同步映射误差。
- **Alternatives considered**:
  - 1kHz：实现简单，但高频信息分辨率不足。
  - 2kHz：吞吐与处理负担更高，课设收益不明显。

## 决策 1.1：时间同步拟合参数定版

- **Decision**: 同步拟合窗口使用最近 `4.0s` 数据；`R² < 0.995` 视为拟合失败；每 `1.0s` 重拟合一次。
- **Rationale**: 4s 在 1680Hz 下具备充足样本点，能抑制串口抖动；1s 重拟合可跟踪温漂和时钟漂移。
- **Alternatives considered**:
  - 1s 拟合窗：对抖动过敏，拟合不稳定。
  - 按任务一次性拟合：无法跟踪运行期间漂移。

## 决策 1.2：Tick 溢出策略

- **Decision**: STM32 使用 `32-bit 1MHz` tick，主机按 `imu_seq` 做 tick unwrap 到逻辑 64-bit 轴。
- **Rationale**: 协议包体更小，且 71.6 分钟溢出可在软件层稳定处理。
- **Alternatives considered**:
  - 64-bit us tick：无需 unwrap，但增加串口负载和固件处理复杂度。

## 决策 2：窗口默认值恢复为 0.25s/0.05s

- **Decision**: 默认 `window_size_s=0.25`、`window_hop_s=0.05`；`1.0/0.5` 作为可选展示模式。
- **Rationale**: 0.25s 已在 legacy 原型验证过；保持技术连续性与复现实验可比性。
- **Alternatives considered**:
  - 仅保留 1.0s：大屏更稳定，但偏离已验证设置。

## 决策 2.1：增量更新最小样本阈值

- **Decision**: 新工况增量更新阈值设为“至少 `90` 个有效窗口 + 至少 `3` 次独立采集任务”。 
- **Rationale**: 低于该阈值时窗口相关性高、更新方差大；该阈值仍保持少样本特性，适合课设节奏。
- **Alternatives considered**:
  - 30-60 窗口：更新结果波动明显。
  - 150+ 窗口：失去少样本更新优势。

## 决策 3：融合主线改为特征向量融合 + ML 分类

- **Decision**: 主线采用 `vision_* + sensor_*` 拼接向量输入 RF/XGBoost/SVM。
- **Rationale**: 与 `doc/context.md` 和 `doc/feature_schema.md` 一致，保留分轴信息表达能力。
- **Alternatives considered**:
  - 三标量频率加权平均：可解释但信息损失大，不作为主线。

## 决策 4：频率加权仅保留为展示派生指标

- **Decision**: `fused_dominant_freq_hz` 作为仪表盘展示字段存在，不作为主分类器唯一输入。
- **Rationale**: 兼顾可解释展示与模型表达能力。
- **Alternatives considered**:
  - 完全移除该字段：会降低大屏可读性。

## 决策 5：串口吞吐预算固化

- **Decision**: 在 plan 中固定吞吐计算：`57120 B/s` 输入、`92160 B/s` 理论串口上限、占用 `62%`。
- **Rationale**: 满足可重复性要求，使后续参数变更可审计。
- **Alternatives considered**:
  - 不做预算：后续无法判断瓶颈与风险。

## 决策 6：主线复用现有 camera 模块

- **Decision**: `capture_service` 编排采集流程，但复用 `src/project_course/camera/{core,v4l2,cli}.py`。
- **Rationale**: 避免重复实现，保持主线一致性。
- **Alternatives considered**:
  - 新写一套摄像头层：维护成本高且易分叉。

## 决策 7：前端框架采用 React

- **Decision**: 前端大屏使用 React + Vite + TypeScript，图表层使用 ECharts（`echarts-for-react`）。
- **Rationale**: 课设周期下脚手架成熟、ECharts 组件化集成成本低，便于快速迭代。
- **Alternatives considered**:
  - Vue：同样可行，但团队当前已有 React 相关代码与经验复用路径。

## 决策 8：STM32 协议握手为强制前置

- **Decision**: 串口第一包必须是握手包（`protocol_version`、`sample_rate`、`tick_hz` 等），后端校验通过后才进入采样。
- **Rationale**: 固件独立演进时可避免“静默字段错位”导致错误数据进入融合链路。
- **Alternatives considered**:
  - 无握手直接流式：实现简单，但协议漂移风险高。
