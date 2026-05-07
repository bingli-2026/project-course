---
name: project-course-doc-context-tracker
description: 在项目开发过程中自动记录并维护关键上下文文档与项目文档索引，确保信息可追踪。
---

# Project Course Doc Context Tracker

当任务涉及项目文档整理、阶段总结、研究材料归档、或需要快速了解项目上下文时，使用此 skill。

## Workflow

1. 运行文档索引更新脚本，刷新项目文档快照。
2. 检查新增/删除文档是否被正确识别。
3. 在提交前确认 `doc/context/key-context-index.md` 已更新。

## Commands

更新文档索引：

```bash
python3 scripts/update_doc_context_index.py
```

## References

- `.project-skills/doc-context-tracking.md`
- `doc/context/key-context-index.md`
