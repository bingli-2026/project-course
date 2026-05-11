# 数据契约 — 特征文件规范

> 英文版本:[`data-contract.md`](data-contract.md) (以英文版为准,中文版用于队内交流)

本文档是队员之间交换特征 CSV / Parquet 文件时的**操作规则书**,叠加在 [`feature_schema.md`](feature_schema.md) 之上 —— 后者定义"有哪些列",本文定义"列怎么填、文件怎么命名、什么会被拒收"。生产或消费特征文件之前请先看这两份。

Web 后端的 `src/project_course/api/storage/ingest.py` 在上传时强制执行本契约的子集。**如果你修改了本契约,必须在同一个 commit 里更新 `ingest.py`。**

---

## 1. 文件格式

| 项 | 规则 |
|---|---|
| 扩展名 | 仅支持 `.csv` 或 `.parquet` |
| CSV 编码 | UTF-8,**不带 BOM** |
| CSV 分隔符 | `,`(英文逗号) |
| CSV 小数点 | `.`(英文句号),不能用 `,` |
| 换行符 | `\n` 或 `\r\n` 均可(pandas 默认即可) |
| 浮点 | `float64`;能保留 4 位小数就保留 4 位,减小体积 |
| 布尔 | 编码成整数 `0` / `1`,不要写 `True` / `False` |
| 缺失值 | CSV 留空单元格;Parquet 用 `NaN` |
| Parquet 压缩 | 默认 `snappy` 即可,不要用 `brotli` |

**~5 MB 以上用 Parquet,以下用 CSV**。

## 2. 一个文件 = 一个样本

- 单个文件**必须**只包含一个 `sample_id`。多 sample_id 的文件后端会拒收(HTTP 422)
- 单个样本**可以**包含一种或两种模态的行(`vision` / `sensor` / `fused`)。后端通过"是否存在 `vision_` / `sensor_` 前缀列且有非空值"来推断 `has_vision` / `has_sensor`
- 推荐文件名:`<sample_id>.csv` 或 `<sample_id>.parquet`。文件名只是参考,**真正的 source of truth 是 `sample_id` 列**

## 3. `sample_id` 命名规则

正则:`^[a-z][a-z0-9_]{2,63}$`

- 小写 ASCII 字母 / 数字 / 下划线
- 必须以字母开头
- 长度 3–64 个字符
- 不准有空格、中文、连字符、点号

**推荐格式**:`<场景>_<编号>` 或 `<场景>_<yyyymmdd>_<编号>`

合规示例:
- `gearbox_run01`
- `gearbox_unbalance_20260518_03`
- `demo_normal`

不合规:
- `Test 1.csv`(含空格、大写、文件名带扩展名)
- `齿轮箱实验1`(非 ASCII)
- `00-run`(以数字开头、含连字符)

**`sample_id` 一旦使用就不能重新指向不同的数据。**重新采集时请增加编号。

## 4. 必填列(硬性)

任何行、任何模态都必须有:

| 列名 | 类型 | 说明 |
|---|---|---|
| `sample_id` | string | 文件中每一行都是同一个值 |
| `window_index` | int (≥ 0) | 0、1、2 …… 连续 |
| `center_time_s` | float (≥ 0) | 窗中心时间戳,单位秒 |

缺任一列 → 后端返回 422,响应里 `missing_columns` 数组会列出来。

## 5. 强烈推荐列(软性)

有这些列仪表盘渲染会好看很多。生产方应尽量填:

| 列名 | 类型 | 说明 |
|---|---|---|
| `label` | string | 见 §6 词表。空/NaN 表示"未标注" |
| `modality` | string | `vision`、`sensor` 或 `fused` |
| `source_name` | string | 原始视频/传感器文件名,便于溯源 |
| `analysis_fps` | float | 用于谱分析的有效采样率 |
| `window_start_frame` | int | 起始帧(含) |
| `window_end_frame` | int | 结束帧(不含) |

## 6. Label 闭集词表

在团队另行约定之前,`label` **必须**取以下之一:

```
normal       正常
unbalance    不平衡
loose        松动
misaligned   不对中
unknown      未知
```

规则:
- 小写 ASCII,严格拼写 —— `Loose`、`loose `(末尾有空格)、`松动` 都会被下游工具拒收
- 真不知道的就写 `unknown`,**不要留空**
- 增加新 label 必须通过 PR 同时改本节 + `scripts/generate_demo_samples.py`

## 7. 模态之间的窗口对齐

当一个样本同时包含两种模态时,vision 行和 sensor 行必须共享:

- 相同 `sample_id`
- 相同 `window_index` 编号规则(0..N-1,不准跳号)
- 相同 `window_index` 对应相同 `center_time_s`
- 如果同时有 `window_start_frame` / `window_end_frame`,语义必须一致

**生产方负责在写文件前做重采样/时间对齐。**Web 后端不做窗口对齐,拿到什么就入什么。

## 8. 可选/预留列

下列列名为**预留**,将来用得到时按下表命名;现在不需要就别写。

| 列名 | 类型 | 预留给 |
|---|---|---|
| `predicted_label` | string | 模型把预测结果回写到 CSV |
| `prediction_confidence` | float (0–1) | 每窗置信度 |
| `model_version` | string | 例如 `rf_v0.3` |

仪表盘目前不显示这几列,等模型组确认输出格式后再加。

## 9. 校验行为

后端在上传(`POST /api/v1/samples`)或启动扫描时的处理:

| 条件 | 结果 |
|---|---|
| 扩展名不支持 | 400 |
| 文件空 / 没有行 | 422 |
| 缺必填列 | 422,响应里附 `missing_columns` 数组 |
| 文件包含多个不同 `sample_id` | 422 |
| schema OK,入库成功 | 上传 201;启动扫描会打 log |

上传失败的文件**会从磁盘删掉**;启动扫描遇到无效文件会**保留**并打 warning,方便你去看看是哪里错了。

## 10. 示例

**仅视觉、最小行(CSV)**:
```
sample_id,window_index,center_time_s,label,modality,vision_dx_peak_hz,vision_dy_peak_hz
gearbox_run01,0,0.25,normal,vision,12.4,14.1
gearbox_run01,1,0.75,normal,vision,12.5,14.0
```

**融合后、最小行(每窗一行,两边都填)**:
```
sample_id,window_index,center_time_s,label,modality,vision_dx_peak_hz,sensor_ax_peak_hz
gearbox_run01,0,0.25,unbalance,fused,24.3,99.8
```

完整 schema 兼容的 CSV 示例请跑 `uv run python scripts/generate_demo_samples.py`,然后看 `data/samples/demo_normal.csv`。

## 11. 责任归属

- **Schema 列定义**(有哪些特征):由 [`feature_schema.md`](feature_schema.md) 拥有
- **操作规则**(本文档):由 贺鑫皓 (Web BE/FE)拥有
- **后端强制执行**:`src/project_course/api/storage/ingest.py`
- **参考生产方**:`scripts/generate_demo_samples.py`

**改这三个里任何一个都必须在同一 commit / PR 里同步改其余两个。**
