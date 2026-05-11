# 数据契约 — 窗口样本

> 英文版本:[`data-contract.md`](data-contract.md) (以英文版为准,中文版用于队内交流)

本文档是**操作规则书**,定义 `WindowSample` 行 —— 特征 pipeline、模型、Web 后端、仪表盘之间交换数据的基本单位。叠加在 [`feature_schema.md`](feature_schema.md) 之上 —— 后者定义"有哪些列",本文定义"怎么往里传、怎么往出读"。生产或消费数据之前请先看这两份。

契约在两个地方强制执行:
- **实时路径** —— `src/project_course/api/live/state.py:publish_window(payload)`。特征 pipeline 和模型在同进程内调用,**没有 JSON、没有 HTTP**
- **离线路径** —— `src/project_course/api/storage/ingest.py`。校验丢到 `data/samples/` 下的 CSV/Parquet 文件,供历史回放页使用

**修改本契约必须在同一 commit 里同步修改这两个文件。**

---

## 1. 两条数据路径

Web 后端、特征 pipeline、模型推理**全部跑在香橙派的同一个 Python 进程里**。窗口样本在进程内流转,中间不做任何序列化。

```
┌──────────────────────────────────────────────────────────────┐
│ 香橙派 - 单个 Python 进程                                    │
│                                                              │
│  采集层 (冶秉礼,杨喆)                                       │
│    │ 相机帧 + IMU 包                                         │
│    ▼                                                         │
│  特征提取 (贺鑫皓 + 杨炫志)                                  │
│    │                                                         │
│    │   调用 live.publish_window({...})                       │
│    ▼                                                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ live.state.LIVE_STATE                                  │  │
│  │   - active_task: LiveTask | None                       │  │
│  │   - buffer: deque[WindowSample](容量 240)              │  │
│  │   - sync_quality: {offset_ms_p95, drift_ppm, ...}      │  │
│  └────────────────────────────────────────────────────────┘  │
│                  │            │                              │
│                  ▼            ▼                              │
│       Web BE 路由       模型推理                             │
│       (读 buffer +      (读 buffer,                          │
│        持久化窗口到      把 predicted_state 通过             │
│        SQLite)          publish_window 写回)                 │
│                  │                                           │
│                  ▼ HTTP                                      │
│             仪表盘浏览器                                     │
└──────────────────────────────────────────────────────────────┘

离线路径(历史回放、没硬件时演示彩排):

  data/samples/<sample_id>.csv  ─┐
                                 │ 启动扫描 或 POST /api/v1/history
                                 ▼
                          ingest.py 校验后写入
                          SQLite 的 history_samples 表
```

## 2. `publish_window(payload)` 契约(实时路径)

`payload` 是 `dict[str, Any]`。后端**不在运行时按完整 schema 做校验** —— 那会让热路径变慢,而且发现错误时也晚了。生产方按规矩填字段,测试覆盖在生产侧做。

### 2.1 必填键(硬性)

| 键 | 类型 | 说明 |
|---|---|---|
| `sample_id` | `str` | 本次采集会话的稳定标识。实时运行时直接用 task 的 `task_id` |
| `window_index` | `int (≥ 0)` | 滑窗序号,在一个 task 内单调递增。SQLite 落库前会 `int()` 强转 |
| `center_time_s` | `float (≥ 0)` | 窗中心时间(秒) |

缺任一键会让 `publish_window` 抛 `KeyError`,或 SQLite 插入失败。

### 2.2 强烈推荐键(软性)

不强制,但缺了仪表盘相应位置显示空/None。

| 键 | 类型 | 用途 |
|---|---|---|
| `label` | `str`(闭集,见 §6) | 仪表盘 StateCard 颜色映射 |
| `modality` | `"vision" \| "sensor" \| "fused"` | 标识本行由哪一支特征分支产出 |
| `source_name` | `str` | 溯源 |
| `analysis_fps` | `float` | sanity check |
| `window_start_frame` / `window_end_frame` | `int` | 可复现性 |

### 2.3 特征键(主要载荷)

任何以 `vision_`、`sensor_`、`fused_` 开头的键都被视为特征值。`feature_schema.md` 列了每种模态期望的字段。仪表盘的 SpectrumPanel 和 FusionTrend 会找这些键:

- `vision_dx_peak_hz`、`vision_dy_peak_hz` + `*_peak_power`
- `sensor_ax_peak_hz` ... `sensor_gz_peak_hz` + `*_peak_power`
- `fused_dominant_freq_hz`、`fusion_confidence`

不填的话,对应曲线会缺失。

### 2.4 预留键

`publish_window` 识别这些键并更新 task 摘要字段:

| 键 | 效果 |
|---|---|
| `predicted_state` | 更新 `tasks.predicted_state` 和仪表盘 StateCard |
| `prediction_confidence` | 更新 `tasks.confidence_summary` |
| `model_version` | (暂时不通过这里;task 的 `model_version` 在 `start_task` 时设置) |

### 2.5 同步质量(独立接口)

不必每窗都重复填的指标,用 `live.record_sync_quality(...)`:

```python
from project_course.api.live import record_sync_quality

record_sync_quality(
    offset_ms_p95=1.23,
    drift_ppm=3.4,
    aligned_window_ratio=0.96,
)
```

典型调用频率是每 N 秒一次,不是每窗一次。

### 2.6 生产方代码示例

```python
from project_course.api.live import publish_window

publish_window({
    "sample_id": current_task.task_id,
    "window_index": w,
    "center_time_s": w * 0.25 + 0.25,
    "label": "unbalance",
    "modality": "fused",
    "analysis_fps": 420.0,
    "vision_dx_peak_hz": 24.5,
    "vision_dy_peak_hz": 26.0,
    "vision_dx_peak_power": 1.4,
    "vision_dy_peak_power": 1.6,
    "sensor_ax_peak_hz": 100.0,
    "sensor_ax_peak_power": 1.96,
    # ... 其他 sensor_*、fused_* 字段
    "predicted_state": "unbalance",
    "prediction_confidence": 0.88,
})
```

## 3. CSV/Parquet 离线契约(历史路径)

用于**没硬件时演示彩排**和回放历史采集。schema 一样,但文件在 ingest 时强制校验(失败 HTTP 422)。

| 项 | 规则 |
|---|---|
| 扩展名 | 仅 `.csv` 或 `.parquet` |
| CSV 编码 | UTF-8,**不带 BOM** |
| CSV 分隔符 | `,`(英文逗号) |
| CSV 小数点 | `.`(英文句号),不能用 `,` |
| 浮点 | 能保 4 位小数就保 4 位 |
| 布尔 | 编码成整数 `0` / `1` |
| 缺失值 | CSV 留空单元格,Parquet 用 `NaN` |
| 一文件 = 一样本 | 文件包含多个不同 `sample_id` 会被拒收 |

推荐文件名:`<sample_id>.csv`。文件名只是参考,**真正的 source of truth 是 `sample_id` 列**。

### 3.1 必填 CSV 列

同 §2.1:`sample_id`、`window_index`、`center_time_s`。缺任一返回 HTTP 422 + `missing_columns` 数组。

### 3.2 文件放哪

```
data/samples/<sample_id>.csv   <- 文件丢这里
data/project_course.sqlite3    <- 自动生成的索引,不要手动改
```

后端启动时扫描 `data/samples/` 把新文件入库。也可以通过仪表盘的"历史回放"页右上角按钮上传。

## 4. `sample_id` 命名

正则:`^[a-z][a-z0-9_-]{2,63}$`(实时任务用 `task-<12 位 hex>`,自动符合)

- 小写 ASCII 字母、数字、下划线、连字符
- 必须以字母开头
- 3–64 字符

离线文件推荐格式:`<场景>_<编号>` 或 `<场景>_<yyyymmdd>_<编号>`。例如 `gearbox_run01`、`gearbox_unbalance_20260518_03`。

不合规:`Test 1.csv`(空格、大写)、`齿轮箱实验1`(非 ASCII)、`00run`(以数字开头)。

**`sample_id` 一旦使用就不能重新指向不同数据。**重采就增加编号。

## 5. 模态之间的窗口对齐

样本同时包含视觉行和传感器行时:

- 相同 `sample_id`
- 相同 `window_index` 编号规则(0..N-1,不跳号)
- 相同 `window_index` 对应相同 `center_time_s`

生产方在 publish **之前**做对齐。Web 后端不尝试融合错位窗口。最干净的格式是 fused 行(每窗一行,两边都填),simulator 就是按这个产的。

## 6. Label 闭集词表(2026-05-11 团队确认)

`label` **必须**取以下之一:

```
normal       正常
unbalance    不平衡
loose        松动
misaligned   不对中
unknown      未知
```

规则:
- 小写 ASCII,严格拼写 —— `Loose`、`loose `(末尾有空格)、`松动` 都不行
- 不确定就写 `unknown`,**不要留空**
- 新增 label 必须通过 PR 同时改本节、仪表盘的 `STATE_COLORS`、simulator 的 profile

## 7. 窗口参数(2026-05-11 团队确认)

| 参数 | 值 |
|---|---|
| `window_size_s` | 0.5 |
| `window_hop_s` | 0.25 |
| `imu_sample_rate_hz` | 1680 |
| `camera_mode` | `YUY2_160x140_420fps` |
| `analysis_fps` | 420.0 |

每个任务可在 `POST /api/v1/tasks` 请求体里覆盖。默认值在 `src/project_course/api/config.py`。`specs/.../plan.md` 里的 legacy `0.25 / 0.05` 留作参考。

## 8. 校验行为

**实时路径**:不做校验 —— 信任生产方。垃圾进,垃圾出。

**离线路径**(`POST /api/v1/history` 或启动扫描):

| 条件 | 结果 |
|---|---|
| 扩展名不支持 | 400 |
| 文件空 / 没有行 | 422 |
| 缺必填列 | 422,附 `missing_columns` 数组 |
| 多个不同 `sample_id` | 422 |
| schema OK | 上传 201,启动扫描打 log |

上传失败的文件**会从磁盘删掉**;启动扫描遇到无效文件**保留**并打 warning,方便排查。

## 9. 持久化

Web 后端会持久化什么:

| 数据 | SQLite 表 | 生命周期 |
|---|---|---|
| Task 元数据 + 摘要 | `tasks` | 永久 |
| 实时窗口样本 | `window_samples` | 永久(FK cascade `tasks`) |
| 离线历史索引 | `history_samples` | 永久 |
| 原始 CSV/Parquet 文件 | 文件系统 `data/samples/` | 手动管理 |
| 同步质量历史 | (只存最新值,在 `tasks` 行) | 每任务 |

**不持久化**(交由硬件/边缘端):
- 原始相机帧
- 原始 STM32 IMU 包
- 每窗的频谱数组(中期演示阶段仪表盘从峰值特征合成可视化)

## 10. 责任归属

- **Schema 列定义**(有哪些特征):`doc/feature_schema.md`
- **操作规则**(本文):贺鑫皓 (Web BE/FE) + 杨炫志 (模型)
- **实时生产方**:同进程的特征 pipeline —— 见 §2.6 示例
- **实时消费方**:`src/project_course/api/storage/db.py:insert_window` + 仪表盘
- **离线生产方**:任何能写出合规 CSV 的人
- **离线消费方**:`src/project_course/api/storage/ingest.py` + 历史回放页
- **Simulator(参考实时生产方实现)**:`src/project_course/api/live/simulator.py`

**改动 `feature_schema.md`、本文、`ingest.py` 任何一个都必须在同一 commit 里同步改其余两个。**
