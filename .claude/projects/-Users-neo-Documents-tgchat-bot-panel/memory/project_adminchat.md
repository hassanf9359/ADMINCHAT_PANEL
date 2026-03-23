---
name: ADMINCHAT Panel 项目概况
description: Telegram 双向消息转发 Bot + Web 客服管理面板项目，Python 后端 + React 前端
type: project
---

ADMINCHAT Panel: Telegram 双向消息转发 Bot 配合 Web 管理面板的客服系统。

**技术栈决定:** Python 3.12 + FastAPI (后端) / React + TS + Vite + shadcn/ui (前端) / PostgreSQL / Redis / aiogram 3 (Bot框架) / Docker + GHCR 部署

**核心功能:** 多 Bot 池管理、私聊+群组@消息双向转发、FAQ 自动回复引擎(8种模式含AI)、用户管理(标签/分组/拉黑)、客服权限系统(3角色)、CF Turnstile 验证、遗漏知识点分析、RAG 预留

**Why:** 市面上没有好用的 Telegram 客服管理 Bot 方案
**How to apply:** 所有开发文档在 docs/ 目录，进度跟踪在 docs/DEVELOPMENT_PROGRESS.md
