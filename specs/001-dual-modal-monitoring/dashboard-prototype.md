# 前端大屏原型设计

**关联**: spec.md User Story 2, plan.md, contracts/api.yaml  
**技术栈**: React 18 + Vite 5 + TypeScript + ECharts 5 (echarts-for-react) + Axios  
**刷新策略**: 1s REST 轮询（plan 决策 6），后续可扩展 WebSocket  
**目标平台**: 香橙派 Linux + Chromium 浏览器，16:9 横屏（答辩投影仪/外接显示器）

---

## 整体布局

```
┌──────────────────────────────────────────────────────────┐
│  顶部栏：任务状态 + 控制                                   │
├────────────┬──────────────────┬──────────────────────────┤
│            │                  │                          │
│  左侧      │   中央           │   右侧                   │
│  双模态    │   融合频率       │   状态结论               │
│  频谱      │   趋势           │   + 模型版本             │
│  八轴 Tab  │                  │                          │
│            │                  │                          │
├────────────┴──────────────────┴──────────────────────────┤
│  底部栏：同步质量 + 窗口进度 + 更新时间                     │
└──────────────────────────────────────────────────────────┘
```

---

## 各区块设计

### 1. 顶部栏 — TaskBar

```
┌────────────────────────────────────────────┐
│  ● 运行中  │ 任务 #task-001 │ 窗口 47/120  │
│            │  设备 rig-01   │              │
│  [新建任务]  [停止]                        │
└────────────────────────────────────────────┘
```

**功能**:
- 状态指示灯（pending→灰, running→绿脉冲, succeeded→绿常亮, failed→红）
- "新建任务"按钮弹出模态窗（字段：`device_id` 必填；`roi_x/y/w/h` 四个整数字段，可选，不填用预设默认值；窗口参数有预填默认值 `0.25s/0.05s`）
- "停止"按钮（仅在 running 状态可用）

**数据源**: `GET /dashboard/overview`（1s 轮询）

---

### 2. 左侧 — SpectrumPanel（占 40% 宽度）

八轴频谱展示，用 **Tab 分组** 切换以降低信息密度：

```
┌───────────────────────────────────┐
│ [加速度计] [陀螺仪] [视觉]         │  ← Tab 切换
│                                   │
│  ┊    ╱╲    ╱╲                   │  ← ECharts line
│  ┊   ╱  ╲  ╱  ╲    ax           │
│  ┊  ╱    ╲╱    ╲   — ay (虚线)   │    频率 (Hz) → x轴
│  ┊ ╱            ╲  … az (虚线)   │    功率 → y轴
│  ┊╱              ╲               │
│  └──┬──┬──┬──┬──┘                │
│     │  │  │  │                   │
│  标记主频峰值（markLine）          │
│                                   │
│  ☑ ax  ☑ ay  ☑ az               │  ← 图例/切换
└───────────────────────────────────┘
```

**Tab 内容**:

| Tab | 线条 | 数据源 |
|---|---|---|
| 加速度计 | `sensor_ax`, `sensor_ay`, `sensor_az` 频谱 | `GET /spectra?window_index=N` → `sensor_ax/ay/az` |
| 陀螺仪 | `sensor_gx`, `sensor_gy`, `sensor_gz` 频谱 | `GET /spectra?window_index=N` → `sensor_gx/gy/gz` |
| 视觉 | `vision_dx`, `vision_dy` 频谱 | `GET /spectra?window_index=N` → `vision_dx/dy` |

**交互**:
- 每条谱线标注主频峰值（从 WindowSample 的 `*_peak_hz` 字段取，垂直虚线 + 数值标签）
- 图例可点击切换单轴显示/隐藏
- 窗口切换通过底部时间轴 slider 驱动

---

### 3. 中央 — FusionTrend（占 35% 宽度）

```
┌──────────────────────────────┐
│  融合频率趋势                  │
│                              │
│  ┊  ┊    ╱╲                  │
│  ┊  ┊   ╱  ╲    ╱╲         │  ← fused_dominant_freq_hz（粗实线）
│  ┊ ╱╲  ╱    ╲  ╱  ╲        │
│  ╱    ╲╱      ╲╱    ╲───    │
│                              │
│  ─── 融合频率  ┈┈┈ 置信度     │
│  置信度 < 0.5 区域灰色标记    │
└──────────────────────────────┘
```

**功能**:
- 横轴：`window_index`（0..N）
- 主曲线：`fused_dominant_freq_hz`（粗实线，蓝色）
- 置信度着色：`fusion_confidence < 0.5` 区段用灰色底色或虚线标记
- 可选叠加：`acc_dominant_freq_hz`、`gyro_dominant_freq_hz`、`cam_dominant_freq_hz` 作为半透明参考线（展示"融合前后对比"叙事）

**数据源**: `GET /tasks/{task_id}/windows` → 取全部窗口的 `window_index`, `fused_dominant_freq_hz`, `fusion_confidence`

---

### 4. 右侧 — StateCard（占 25% 宽度）

```
┌───────────────────┐
│  当前状态          │
│                   │
│   ┌───────────┐   │
│   │  正常      │   │  ← 大字标签
│   │  置信 0.87 │   │     颜色编码: 正常→绿 / 异常→红 / 不确定→黄
│   └───────────┘   │
│                   │
│  模型版本          │
│  v1.2-baseline    │
│                   │
│  任务成功率(24h)   │
│  95%              │
│                   │
│  最近历史          │
│  ┌───┬──┬────┐    │
│  │ # │状态│置信│    │  ← 可折叠迷你列表，最多 10 条
│  │ 3 │异常│0.92│   │
│  │ 2 │正常│0.88│   │
│  │ 1 │正常│0.91│   │
│  └───┴──┴────┘    │
│                   │
│  [增量更新]        │  ← P3 功能入口（P1/P2 阶段灰显）
└───────────────────┘
```

- 大字状态标签 + 置信度数字，三色映射
- 模型版本号 + 任务成功率
- 最近 10 条历史结果的迷你表格（可折叠）
- "增量更新"按钮（P3 功能，P1/P2 阶段禁用灰显）

**数据源**: `GET /dashboard/overview` → `latest_predicted_state`, `confidence_summary`, `active_model_version`, `task_success_rate_24h`

---

### 5. 底部栏 — StatusBar

```
┌──────────────────────────────────────────────────────────┐
│  同步偏移 p95: 1.2ms │ 对齐率: 95% │ 漂移: 3.2ppm │ 刷新于 14:32:05
└──────────────────────────────────────────────────────────┘
```

**数据源**: `GET /dashboard/overview` → `sync_offset_ms_p95`, `aligned_window_ratio`（来自 TaskDetailResponse.sync_quality）

---

## 交互说明

### MVP（P1/P2 阶段）

- 页面加载后自动轮询 `/dashboard/overview`，有任务时进入监控视图
- 频谱 Tab 切换 → 纯前端，使用已加载的 `/spectra` 数据
- 趋势图和频谱图随 `window_index` 自动推进（默认显示最新窗口）
- 无任务时显示空状态引导："点击新建任务开始"

### 扩展预留（不在 P1/P2）

- 窗口时间轴 slider：拖动后重新请求 `/spectra?window_index={selected}`
- ROI 交互框选：首帧截图 + 手动拖拽矩形 → 写入 `roi_x/y/w/h` 参数（plan 已标注"P1 不实现"）
- WebSocket 推送替代 1s 轮询（plan 已标注"保留后续流式扩展位"）

---

## 目录结构

```
frontend/dashboard/
├── src/
│   ├── main.tsx              # ReactDOM.createRoot，挂载 App
│   ├── App.tsx               # 四区块 CSS Grid 布局容器 + 1s 轮询调度
│   ├── App.css               # 全局布局样式（Grid 定义、颜色变量）
│   ├── pages/
│   │   └── Dashboard.tsx     # 唯一页面（MVP 无路由，路径留空）
│   ├── components/
│   │   ├── TaskBar.tsx        # 顶部任务状态 + 控制按钮
│   │   ├── TaskCreateModal.tsx # 创建任务模态窗（device_id、ROI、窗口参数）
│   │   ├── SpectrumPanel.tsx  # 频谱 Tab 面板（ECharts line × 3 tabs）
│   │   ├── FusionTrend.tsx    # 融合频率趋势图（ECharts line）
│   │   ├── StateCard.tsx      # 状态结论 + 模型版本 + 历史列表
│   │   └── StatusBar.tsx      # 底部同步质量栏
│   ├── hooks/
│   │   ├── usePolling.ts      # 通用 1s 轮询 hook（useEffect + setInterval）
│   │   └── useTask.ts         # 当前任务状态（task_id、window_index、status）
│   ├── services/
│   │   └── api.ts             # Axios 实例 + 所有端点函数（类型化返回值）
│   ├── store/
│   │   └── dashboardStore.ts  # Zustand/Context 全局状态
│   └── types/
│       └── api.ts             # API 响应类型定义（对应 api.yaml schemas）
├── index.html                 # Vite 入口 HTML
├── vite.config.ts             # Vite 配置（proxy → localhost:8000）
├── tsconfig.json
└── package.json
```

---

## 数据流

```
1s 定时器
  │
  ├─ GET /dashboard/overview ──────→ TaskBar + StateCard + StatusBar
  ├─ GET /tasks/{id}/windows ──────→ FusionTrend（全量窗口趋势）
  └─ GET /tasks/{id}/spectra       → SpectrumPanel（当前窗口频谱）
         ?window_index={latest}
```

- 任务未创建时：仅轮询 `/dashboard/overview`（其他请求跳过）
- 任务 running/succeeded 时：三路请求并行，window_index 默认取最新
- 加载态：每个区块独立显示骨架屏/loading，不做全页面阻塞

---

## 错误与空状态

| 状态 | 表现 |
|---|---|
| 后端不可达 | 顶部栏红色提示"服务不可用"，其他区块保持上次数据 |
| 无任务 | StateCard 显示"暂无任务记录"，TaskBar 显示 [新建任务] 按钮高亮 |
| 任务失败 | 状态灯红色，错误信息从 `TaskDetailResponse.error_message` 取，显示在 StatusBar |
| 频谱数据缺失 | 对应 Tab 图显示"本窗口无有效频谱数据"占位文字 |
| 同步质量不达标 | StatusBar 对应指标显示橙色警告色（align ratio < 90% 或 offset > 2ms） |

---

## 颜色与视觉规范

```
正常/成功: #52c41a (绿)
异常/失败: #ff4d4f (红)
不确定/警告: #faad14 (黄/橙)
置信度低: 灰色底色或虚线标记
主曲线: #1677ff (蓝)
参考线: 半透明灰色
背景: #f5f5f5 (浅灰)
卡片: #ffffff (白) + 1px 边框 #e8e8e8
```

---

## 依赖清单（package.json）

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "echarts": "^5.5",
    "echarts-for-react": "^3.0",
    "axios": "^1.7"
  },
  "devDependencies": {
    "typescript": "^5.4",
    "vite": "^5.4",
    "@vitejs/plugin-react": "^4.3",
    "@types/react": "^18.3",
    "@types/react-dom": "^18.3"
  }
}
```
