# `data/` — 样本特征文件目录

> **English-language contract**: The authoritative rules for these files are in [`../doc/data-contract.md`](../doc/data-contract.md). The Chinese notes below are a quick onboarding summary; if they ever disagree with the English contract, the English contract wins.

---


仪表盘后端 (`project-course-api`) 在启动时会扫描 `data/samples/` 下的所有 `.csv` / `.parquet` 文件,把符合 schema 的样本入库到 `data/project_course.sqlite3`。无效文件会被忽略并打日志。

## 投喂方式

两种方式任选其一,效果一致:

1. **直接拷贝** —— 把生成好的 `<sample_id>.csv` 或 `<sample_id>.parquet` 放进 `data/samples/`,然后重启后端
2. **网页上传** —— 仪表盘"样本"页右上角点 `+ 上传特征文件`,选文件即可

## 文件命名

- 一个文件 = 一个 `sample_id`(如果文件里出现多个 `sample_id`,会被拒绝)
- 推荐文件名:`<sample_id>.csv`,例如 `gearbox_run01.csv`

## 必填列(否则 422 拒收)

| 列名 | 类型 | 说明 |
|---|---|---|
| `sample_id` | string | 全文件唯一,稳定的采集标识 |
| `window_index` | int | 滑窗序号(0、1、2...) |
| `center_time_s` | float | 该窗中心点时间(秒) |

## 推荐列(显示更友好)

| 列名 | 用途 |
|---|---|
| `label` | `normal` / `unbalance` / `looseness` 等 — 列表页可筛选 |
| `modality` | `vision` / `sensor` / `fused` |
| `source_name` | 视频或采集文件名 |
| `analysis_fps`、`window_start_frame`、`window_end_frame` | schema 标识字段,便于追溯 |

## 视觉/传感器特征列

凡以 `vision_` 开头的列被视为视觉特征,`sensor_` 开头的列被视为传感器特征。是否落到列表的 modality 徽章上,由该样本下相应前缀列**是否存在且有值**决定。完整字段表参见 [`doc/feature_schema.md`](../doc/feature_schema.md)。

## 生成示例数据

```bash
uv run python scripts/generate_demo_samples.py
```

会写出 3 个合成样本:`demo_normal.csv`、`demo_unbalance.csv`、`demo_looseness.csv`,可直接用来彩排演示。

## 注意

- `data/project_course.sqlite3` 是后端自动生成的索引文件,可随时删除 — 重启后会按 `data/samples/` 重建
- 不要把真实采集的大体积视频原文件提交到 git;只提交特征 CSV/Parquet
