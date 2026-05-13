# Tasks: 软硬件WebAI一体化设备状态监测

**Input**: Design documents from `/specs/001-dual-modal-monitoring/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.yaml, quickstart.md

**Tests**: 主线代码必须包含 pytest 与集成测试；硬件链路保留 smoke test。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 建立后端融合模块与前端大屏基础骨架

- [X] T001 创建主线融合与服务目录结构 `src/project_course/fusion/`、`src/project_course/services/`、`src/project_course/api/routers/`
- [ ] T002 创建前端大屏工程骨架 `frontend/dashboard/package.json`、`frontend/dashboard/vite.config.ts`、`frontend/dashboard/tsconfig.json`
- [ ] T003 [P] 初始化前端入口文件 `frontend/dashboard/src/main.tsx` 和 `frontend/dashboard/src/App.tsx`
- [X] T004 [P] 新增采样与同步阈值配置 `src/project_course/api/config.py`（R²、超时、窗口默认值、增量阈值）
- [X] T005 在 `pyproject.toml` 增补后端依赖与开发脚本（融合模块、测试分组）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共用的阻塞基础能力

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 定义与 `feature_schema` 对齐的窗口特征模型 `src/project_course/fusion/schema.py`
- [X] T007 实现任务与模型版本持久化层 `src/project_course/services/task_store.py` 与 `src/project_course/services/model_registry.py`
- [X] T008 实现 STM32 协议握手与数据包解析 `src/project_course/services/imu_protocol.py`
- [X] T009 实现 tick unwrap 与线性拟合同步核心 `src/project_course/fusion/time_sync.py`
- [X] T010 实现采样编排基础骨架并复用现有 camera 模块 `src/project_course/services/capture_service.py`
- [X] T011 实现统一错误码与恢复动作映射 `src/project_course/services/error_codes.py`
- [X] T012 [P] 实现 API 基础路由骨架 `src/project_course/api/routers/tasks.py`、`src/project_course/api/routers/dashboard.py`、`src/project_course/api/routers/models.py`
- [X] T013 [P] 建立接口契约测试骨架 `tests/contract/test_api_contract.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 完成双测点数据采集与状态判别 (Priority: P1) 🎯 MVP

**Goal**: 完成一次采集、同步、分轴特征提取、融合向量构建与状态识别闭环

**Independent Test**: 在固定设备上发起任务后，可获取窗口级 `vision_* + sensor_*` 特征与最终分类结果，且失败场景可返回可操作错误

### Tests for User Story 1

- [X] T014 [P] [US1] 编写同步算法单元测试 `tests/unit/test_time_sync.py`（4s 拟合窗、R² 阈值、tick 溢出）
- [X] T015 [P] [US1] 编写 IMU 协议解析单元测试 `tests/unit/test_imu_protocol.py`（握手校验、seq 跳变）
- [X] T016 [US1] 编写采集闭环集成测试 `tests/integration/test_capture_pipeline.py`
- [X] T017 [US1] 编写任务窗口接口契约测试 `tests/contract/test_tasks_windows_contract.py`

### Implementation for User Story 1

- [X] T018 [P] [US1] 实现六轴分轴特征提取 `src/project_course/fusion/imu_features.py`
- [X] T019 [P] [US1] 实现视觉分轴特征提取 `src/project_course/fusion/camera_features.py`
- [X] T020 [US1] 实现特征向量 join 与训练输入构建 `src/project_course/fusion/feature_vector_fusion.py`
- [X] T021 [US1] 实现基线分类推理服务 `src/project_course/services/inference_service.py`
- [X] T022 [US1] 完成采样任务编排与错误恢复逻辑 `src/project_course/services/capture_service.py`
- [X] T023 [US1] 实现任务创建与查询接口 `src/project_course/api/routers/tasks.py`
- [X] T024 [US1] 实现窗口特征与频谱接口 `src/project_course/api/routers/tasks.py`
- [X] T025 [US1] 在应用入口注册路由与依赖 `src/project_course/api/app.py`

**Checkpoint**: User Story 1 should be fully functional and independently testable

---

## Phase 4: User Story 2 - 通过Web界面进行过程管理与结果查看 (Priority: P2)

**Goal**: 前端大屏可发起任务、查看状态、查看分轴频谱与结果摘要

**Independent Test**: 不使用命令行，前端页面可完成“任务发起 -> 状态轮询 -> 结果展示 -> 频谱查看”

### Tests for User Story 2

- [ ] T026 [P] [US2] 编写大屏概览接口契约测试 `tests/contract/test_dashboard_contract.py`
- [ ] T027 [US2] 编写前后端联调集成测试 `tests/integration/test_dashboard_flow.py`

### Implementation for User Story 2

- [ ] T028 [P] [US2] 实现前端 API 客户端 `frontend/dashboard/src/services/api.ts`
- [ ] T029 [P] [US2] 实现任务发起与 ROI 输入组件 `frontend/dashboard/src/components/TaskControlPanel.tsx`
- [ ] T030 [P] [US2] 实现分轴频谱图组件 `frontend/dashboard/src/components/SpectraPanel.tsx`
- [ ] T031 [P] [US2] 实现任务状态与结果组件 `frontend/dashboard/src/components/TaskStatusPanel.tsx`
- [ ] T032 [US2] 实现大屏页面与轮询逻辑 `frontend/dashboard/src/pages/DashboardPage.tsx`
- [ ] T033 [US2] 实现前端状态管理 `frontend/dashboard/src/store/taskStore.ts`
- [ ] T034 [US2] 实现后端大屏概览接口 `src/project_course/api/routers/dashboard.py`

**Checkpoint**: User Stories 1 and 2 both work independently

---

## Phase 5: User Story 3 - 支持少样本新增工况的增量更新 (Priority: P3)

**Goal**: 支持阈值守卫下的增量更新，并产出更新前后对比报告

**Independent Test**: 提交新工况样本后，系统能在满足阈值时成功更新并产出报告；阈值不足时拒绝更新并返回可操作反馈

### Tests for User Story 3

- [X] T035 [P] [US3] 编写增量阈值守卫单元测试 `tests/unit/test_incremental_threshold.py`
- [X] T036 [US3] 编写增量更新集成测试 `tests/integration/test_incremental_update_flow.py`
- [X] T037 [US3] 编写模型版本接口契约测试 `tests/contract/test_model_versions_contract.py`

### Implementation for User Story 3

- [X] T038 [P] [US3] 实现增量更新引擎与报告计算 `src/project_course/services/model_update_service.py`
- [X] T039 [US3] 实现增量更新阈值校验与拒绝反馈 `src/project_course/services/model_update_service.py`
- [X] T040 [US3] 实现增量更新与版本查询接口 `src/project_course/api/routers/models.py`
- [X] T041 [US3] 将更新报告纳入大屏概览输出 `src/project_course/api/routers/dashboard.py`

**Checkpoint**: All user stories are independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事稳定性、文档和验证收尾

- [ ] T042 [P] 更新硬件协议与采样参数文档 `doc/hardware-protocol.md`
- [ ] T043 [P] 更新项目说明文档（大屏、ROI、增量更新）`README.md`
- [ ] T044 执行并修复全量测试与静态检查 `tests/`、`src/project_course/`、`frontend/dashboard/`
- [ ] T045 [P] 回归验证 quickstart 步骤并更新 `specs/001-dual-modal-monitoring/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 可立即开始
- **Phase 2 (Foundational)**: 依赖 Phase 1，且阻塞所有用户故事
- **Phase 3 (US1)**: 依赖 Phase 2
- **Phase 4 (US2)**: 依赖 Phase 2，且需要 US1 的后端基础接口可用
- **Phase 5 (US3)**: 依赖 Phase 2，且复用 US1 产出的特征与模型流程
- **Phase 6 (Polish)**: 依赖所有目标用户故事完成

### User Story Dependencies

- **US1 (P1)**: 无其他故事依赖（MVP）
- **US2 (P2)**: 依赖 US1 已暴露任务与窗口接口
- **US3 (P3)**: 依赖 US1 的基础分类流程与模型版本记录

### Within Each User Story

- 先完成测试任务，再完成实现任务
- 先完成数据/服务层，再完成 API 与前端集成
- 每个故事完成后可独立演示和验收

## Parallel Opportunities

- Phase 1 中 `T003`、`T004` 可并行
- Phase 2 中 `T012`、`T013` 可并行
- US1 中 `T014`、`T015`、`T018`、`T019` 可并行
- US2 中 `T028`、`T029`、`T030`、`T031` 可并行
- US3 中 `T035` 与 `T038` 可并行

## Parallel Example: User Story 1

```bash
Task: "T014 [US1] 同步算法单元测试 in tests/unit/test_time_sync.py"
Task: "T015 [US1] IMU 协议解析单元测试 in tests/unit/test_imu_protocol.py"
Task: "T018 [US1] 六轴分轴特征提取 in src/project_course/fusion/imu_features.py"
Task: "T019 [US1] 视觉分轴特征提取 in src/project_course/fusion/camera_features.py"
```

## Parallel Example: User Story 2

```bash
Task: "T028 [US2] 前端 API 客户端 in frontend/dashboard/src/services/api.ts"
Task: "T029 [US2] 任务发起与 ROI 输入组件 in frontend/dashboard/src/components/TaskControlPanel.tsx"
Task: "T030 [US2] 分轴频谱图组件 in frontend/dashboard/src/components/SpectraPanel.tsx"
Task: "T031 [US2] 任务状态与结果组件 in frontend/dashboard/src/components/TaskStatusPanel.tsx"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1 和 Phase 2
2. 完成 US1（Phase 3）
3. 运行 `T014-T017` 测试并完成一次真实设备演示
4. 达成 MVP 后再推进 US2/US3

### Incremental Delivery

1. MVP（US1）: 先跑通采样-同步-融合-识别闭环
2. 演示增强（US2）: 加入前端大屏展示与 ROI 入参
3. 能力扩展（US3）: 加入增量更新与版本报告

### Team Parallel Strategy

1. 一人负责采样与同步（US1 服务层）
2. 一人负责 API 与契约测试（US1/US3 路由）
3. 一人负责前端大屏（US2）
4. 共享接口契约 `contracts/api.yaml` 作为联调基准

## Notes

- 所有任务均包含明确文件路径，满足可执行性要求
- `[P]` 仅用于可并行任务（不同文件、无阻塞依赖）
- US1 为建议 MVP 范围
