# Changelog

All notable changes to ADMINCHAT Panel will be documented in this file.

## [0.6.0] - 2026-03-23

### New Features
- **RAG Knowledge Base** - Modular RAG provider architecture with Dify Knowledge API integration
  - Abstract `RAGProvider` base class for pluggable backends (Dify, pgvector, custom)
  - `DifyRAGProvider` implementation calling Dify dataset retrieve API (hybrid_search)
  - Factory pattern via `get_rag_provider()` with async-safe singleton
  - `reply_mode=rag` fully functional in both private and group handlers
  - RAG results fed to AI for synthesized answers, with fallback to raw content
- **RAG Configuration** - New env vars: `RAG_PROVIDER`, `DIFY_BASE_URL`, `DIFY_API_KEY`, `DIFY_DATASET_ID`, `RAG_TOP_K`

### Code Quality
- Removed all debug `print` statements from message handlers (PII exposure risk)
- Added `try/finally` for `AIHandler` resource cleanup on all code paths
- Added input validation (empty query, top_k bounds) in RAG provider
- Added URL scheme validation for `DIFY_BASE_URL`
- Added `shutdown_rag_provider()` in FastAPI lifespan for proper cleanup
- Fixed `ai_only` mode not checking for empty AI response in private handler
- Unified fallback model name across all handlers

## [0.5.0] - 2026-03-22

### New Features
- **Bot Groups + FAQ Groups/Categories** - Full bot group management and FAQ routing
- **FAQ Group Routing** - Category -> Group -> Fallback inheritance for bot selection

## [0.4.1] - 2026-03-22

### Bug Fixes
- Removed unused FAQGroup import causing CI build failure

## [0.4.0] - 2026-03-22

### New Features
- **Expandable Sidebar** - Hover to expand (64px -> 224px), shows icon + label text with smooth animation
- **Bot Selector for Group Replies** - Click "Replying via BotName" to choose which bot sends group replies
- **FAQ Group Support** - Bot @mentions in groups now trigger FAQ matching and auto-reply
- **Anonymous Sender Support** - Channel masks / anonymous admins in groups can trigger FAQ
- **FAQ Reply in Panel** - Auto-replies stored in DB and shown in chat panel (sender_type=faq)
- **FAQ Reply Prefix** - User-facing FAQ replies prefixed with "基于FAQ自动回复"
- **Image/Media Send & Receive** - Full support for photos, videos, documents between panel and Telegram
- **AI API Format Selector** - Choose between OpenAI Chat Completions and Anthropic Responses (CRS)
- **WebSocket Real-time** - New messages auto-appear with 5s polling fallback
- **Connection Indicator** - Green/red dot shows WebSocket connection status
- **APScheduler** - Missed knowledge analysis runs automatically at 3:00 AM daily
- **Audit Logging** - Critical operations automatically tracked with viewer page
- **Turnstile Verification** - CF Turnstile page for private chat user verification

### UI Improvements
- **Root CSS Fix** - Fixed `* { padding: 0 }` overriding all Tailwind utilities (the root cause of all spacing issues)
- All pages now properly display card backgrounds (#0A0A0A), borders (#2f2f2f), and rounded corners
- Pixel-perfect styling matching Pencil design system across all 15+ pages
- UTC+8 (Asia/Shanghai) timezone for all timestamp displays
- Dynamic version display in footer (injected at build time)

### Bug Fixes
- Fixed Telegram webhook routing through APISIX (Origin Verify bypass)
- Fixed Docker DNS resolution for external API calls
- Fixed bcrypt compatibility (replaced passlib with direct bcrypt)
- Fixed duplicate admin creation on restart
- Fixed group photo + @mention detection (caption support)
- Fixed message timestamps using Telegram's message.date
- Fixed AI handler URL construction for CRS compatibility
- Fixed GHCR build failures (unused imports, multi-platform removed)

### DevOps
- Removed arm64 build (amd64 only, 10x faster CI)
- Version injected into Docker build via build-args
- Explicit version tags in docker-compose (no more :latest confusion)
- APISIX auto-restart after deployment

## [0.3.x] - 2026-03-21

Internal development versions. See git history for details.

## [0.2.0] - 2026-03-21

### Features
- Actual Telegram message sending from web panel
- Group reply with reply_to_message_id
- FAQ group matching
- Anonymous sender support

## [0.1.0] - 2026-03-21

### Initial Release
- Multi-Bot pool management with rate limiting and failover
- Bidirectional message forwarding (private + group @mentions)
- Real-time web chat via WebSocket
- FAQ auto-reply engine with 8 modes
- User management (tags, groups, blocking, search)
- AI integration (OpenAI-compatible API)
- Cloudflare Turnstile verification
- Role-based access control (Super Admin / Admin / Agent)
- Docker deployment with GHCR
- 23-table PostgreSQL schema
- 50+ REST API endpoints
- 15+ frontend pages
