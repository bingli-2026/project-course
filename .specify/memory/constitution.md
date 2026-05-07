<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0
- Modified principles:
  - I. 双模态 Schema-First（补充规范文档固定路径）
  - V. YAGNI & 范围控制（补充 context 文档固定路径）
- Added sections:
  - Governance / 语义化版本策略
  - Governance / 规范引用文档
- Removed sections:
  - 无
- Templates requiring updates:
  - ✅ 无需更新（.specify/templates/* 为生成参考模板，不属于面向人的项目文档约束范围）
- Follow-up TODOs:
  - 无
-->

# 项目宪法

<!--
  本宪法是项目开发过程中的最高准则。所有 Spec、Plan、Task 和实现代码
  必须遵守本宪法。宪法与任何其他习惯、建议冲突时，以宪法为准。
-->

## 核心原则

### I. 双模态 Schema-First

任何产生数据的 feature，必须先定义输出 schema，再写实现。视觉分支和传感器分支共享统一的身份字段（`sample_id`、`window_index`、`center_time_s`）。双模态融合**只能**通过 join 完成，禁止任何写死单一模态假设的融合逻辑。

**Why**: `doc/feature_schema.md` 已确立此契约。这是视觉和传感器分支能独立开发、分别测试、最终自然融合的基础。违背此原则将导致两个分支的数据无法对齐。

**How to apply**:
- 每个 spec 中如涉及数据输出，必须在 spec 文档中明确 schema 字段
- plan 阶段的 `data-model.md` 必须对照 `doc/feature_schema.md` 检查兼容性
- 新增字段时先在 `doc/feature_schema.md` 中更新 schema 定义，再修改代码

---

### II. 实验室-主线分离

代码按成熟度分层管理：

- **`laboratory/`**：实验、探索、硬件调试代码。允许有自己的 `pyproject.toml` 和独立环境，允许与主线临时代码重复
- **`src/project_course/`**：稳定交付代码。必须有测试、API 稳定、遵循所有 lint 规则
- Lab 代码**毕业**到主线的条件：有 pytest 测试覆盖、API 文档清晰、无实验性死代码

Lab 和主线之间**禁止**互相 import。各自是独立的 uv 项目上下文。

**Why**: 硬件调试和实验探索天然具有不确定性。分层管理既保护主线代码的稳定性，又给予实验代码充分的灵活性。临时代码重复是好于过早抽象的——等稳定了再收敛。

**How to apply**: plan 阶段必须明确：新代码放在哪个区域？如果是实验室验证性质，直接放 lab；如果是最终交付，放 mainline 并补齐测试和文档。

---

### III. 增量可交付 & 独立可测

每个 User Story 必须能在不依赖其他 Story 的情况下独立测试和独立演示。不允许出现"等 Story 2 做完 Story 1 才有意义"的情况。

**Why**: 课设 3 个月时间紧张。Story 之间松耦合确保每个阶段都有可演示的增量价值，即使某个 Story 未能按时完成也不影响其他部分的交付。

**How to apply**:
- 每个 spec 的 User Story 必须有明确优先级（P1/P2/P3）
- P1 即 MVP——一个即可演示的最小可用系统
- 每个 Story 的验收场景（Acceptance Scenarios）必须可独立执行
- 如果一个 Story 的"Independent Test"写不出来，说明粒度不对

---

### IV. 可重复性优先

所有实验和开发必须可被他人（或未来的自己）完全复现。

**规则**：
- Python 版本精确锁定（`3.10.12`），不可随意升级
- 依赖锁文件（`uv.lock`）**必须提交**到版本库
- 所有实验参数（ROI 坐标、FPS override、窗口大小、滤波器参数等）必须记录在对应的实验文档中
- 实验脚本对相同输入和参数必须产生确定性输出
- 实验数据集和生成产物**必须 gitignore**，不提交到仓库

**Why**: 学术项目的基本要求。你的吉他实验和汽车引擎实验文档已经在这做了——宪法只是将此明确为所有实验的硬性要求。

**How to apply**:
- 实验完成后，对应的 experiment doc 必须更新完整参数记录
- 新增实验产物的输出目录必须加入 `.gitignore`
- CI 不需要跑硬件相关的实验测试（硬件不可在 CI 环境中复现）

---

### V. YAGNI & 范围控制

不做当前不需要的东西。课设范围严格控制在以下边界内：

**包含范围**：
- 1 台实验设备或 1 套振动台
- 3 到 5 种设备状态
- 双模态（视觉 + 传感器）采集与特征提取
- 传统 ML 分类器（Random Forest / XGBoost / SVM）
- 原型/质心更新法实现小样本增量学习

**红线（禁止）**：
- 复杂深度神经网络的算法研发
- 嵌入式或实时在线部署
- 多机泛化或大规模工业异常诊断
- 运动放大算法研发（EVM 仅作为可视化辅助工具）

任何超出上述范围的提案必须通过宪法修正流程。

**Why**: `doc/context.md` 第 6 节已论证。3 个月课设的成败在于范围控制——把主线做深做稳，比追求新奇复杂更重要。

**How to apply**: plan 阶段的 Constitution Check 必须对照此原则逐条审查。如果某个 feature 引入了深度网络或超出了红色边界，Gate 不通过，除非走宪法修正。

---

### VI. 测试分级

根据代码所在区域执行分级测试策略：

| 代码区域 | 测试要求 |
|---|---|
| **Mainline**（`src/project_course/`） | 必须有 pytest 测试；P1 Story 必须有集成测试 |
| **Laboratory**（`laboratory/`，非 legacy） | Smoke test 即可，不做覆盖率硬性要求 |
| **Legacy**（`laboratory/legacy/`） | 豁免测试要求，保留现有功能即可 |
| **Schema/契约** | 视觉和传感器分支的数据输出必须通过 schema 验证 |

Lab 代码毕业到 mainline 时，必须补齐测试。

**Why**: 硬件相关的实验代码写单元测试成本高、价值低。但 mainline 的 API 和数据处理逻辑必须有测试保护——这是最终交付质量的基础。

**How to apply**:
- TDD 仅对 mainline 代码强制执行
- Lab 代码的"测试"可以是通过手工 smoke test + 截图/可视化验证
- Schema 验证：在 CI 中运行一份基础的 schema 校验脚本，确保数据输出字段符合 `doc/feature_schema.md`

---

## 开发工作流

### Commit 规范

采用**约定式提交（Conventional Commits）**格式：

```
<type>(<scope>): <简短描述>

<详细说明（可选）>

<关联 issue 或 spec（可选）>
```

**类型（type）**：
- `feat`：新功能
- `fix`：Bug 修复
- `refactor`：重构（不改变功能）
- `docs`：文档变更
- `test`：测试变更
- `chore`：构建、依赖、配置等杂项

**范围（scope）**示例：`api`、`camera`、`lab`、`spec`、`docs`

**示例**：
```
feat(camera): add FOURCC negotiation for YUYV mode
refactor(api): extract health router into separate module
fix(lab): correct ROI coordinate parsing in analyze_video_stream
```

### 分支命名

遵循 Speckit 约定：`###-feature-name`

- 数字序号与 spec 目录名对应
- 使用英文小写、短横线分隔
- 示例：`001-camera-v4l2-discovery`、`002-vision-frequency-extraction`

### 文档语言

项目文档统一使用中文。代码注释、commit message、变量/函数命名可以使用英文或中英混合，但所有面向人的文档必须使用简体中文。

**中文范围**：
- Spec、Plan、Task、宪法、实验记录
- 开题报告、答辩材料、README
- Mermaid / PlantUML 图中的文字说明

**可使用英文的范围**：
- 代码标识符（函数名、变量名、类名）
- Commit message（遵循 Conventional Commits，英文）
- Git 分支名
- 第三方库的配置文件和原始 API 调用

### Spec-Driven 开发流程

1. **Specify** — 编写 feature spec（用户故事 + 验收标准 + 需求）
2. **Plan** — 技术方案、数据模型、API 契约
3. **Constitution Check** — 对照本宪法逐条检查
4. **Tasks** — 按 User Story 拆分任务，P1 优先
5. **Implement** — 按任务列表实现，每个 Story 完成后独立验证

所有 phase 输出物使用中文编写。

---

## Governance

### 决策机制

本项目为扁平化小组结构。**所有成员均可提议宪法修正并批准变更。**

### 修正流程

1. 在 `.specify/memory/constitution.md` 中修改对应条款
2. 在版本记录中注明变更原因、变更人和日期
3. 提交 PR，任一成员审查通过即可合并
4. 修正生效后，进行中的 specs 无需回溯修改——仅对新 spec 生效

### 语义化版本策略

宪法版本采用 SemVer：`MAJOR.MINOR.PATCH`。

- **MAJOR**：删除或重定义既有核心原则，导致历史合规方式不再被接受
- **MINOR**：新增核心原则、治理章节，或对既有规则做实质性扩展
- **PATCH**：仅文字澄清、错别字修复、示例替换，不改变合规判断结果

每次修正必须在 PR 描述中注明版本升级类型及理由。

### 规范引用文档

以下文件为宪法依赖的规范文档，路径为固定契约：

- `doc/feature_schema.md`
- `doc/context.md`

若上述文件迁移或重命名，必须在同一 PR 中同步更新本宪法引用路径；否则 Constitution Check 视为不通过。

### 合规审查

- 每个 plan 的 Constitution Check gate 必须逐条对照本宪法
- 如发现违反行为，必须：
  - **方案 A**：修改 plan 以符合宪法
  - **方案 B**：在 Complexity Tracking 表格中记录违规并给出充分理由
  - **方案 C**：启动宪法修正流程

---

**版本**: 1.1.0 | **批准日期**: 2026-05-07 | **最后修订**: 2026-05-07
