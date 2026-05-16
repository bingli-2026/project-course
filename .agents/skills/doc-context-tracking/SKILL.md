---
name: doc-context-tracking
description: 在项目开发过程中自动记录并维护关键上下文文档与项目文档索引，确保信息可追踪。
---

# Doc Context Tracking

## 目标

自动记录两类核心资产：

- 关键上下文文档：用于理解研究方向、沟通历史和设计意图。
- 项目文档：用于理解代码结构、运行方式和实验模块。

## 关键文件约定

- 输出文件：`doc/context/key-context-index.md`
- 更新脚本：`scripts/update_doc_context_index.py`

## 执行规则

1. 每次新增、重命名、删除 `doc/` 下文档后，运行一次更新脚本。
2. 每次涉及 `README.md` 或实验模块 `laboratory/` 的大改动后，运行一次更新脚本。
3. 提交前检查索引中“Generated at”时间是否与当前工作一致。

## 建议提交策略

- 文档内容改动与索引文件可放在同一提交。
- 如果索引变更很大，可先独立提交“doc index refresh”。
