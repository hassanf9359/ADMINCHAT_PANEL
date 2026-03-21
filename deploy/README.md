# ADMINCHAT Panel - 部署指南 / Deployment Guide

[English](#english) | [中文](#中文)

---

## 中文

### 部署方式总览

| 方式 | 文件 | 适用场景 |
|------|------|---------|
| **Docker Run** | `docker-run.sh` | 已有 PG + Redis，只部署 ADMINCHAT |
| **Compose 独立版** | `docker-compose.standalone.yml` | 已有 PG + Redis，用 Compose 管理 |
| **Compose 一键版** | `docker-compose.full.yml` | 全新服务器，一键部署全部组件 |

### 通用步骤

```bash
# 1. 下载部署文件
git clone https://github.com/fxxkrlab/ADMINCHAT_PANEL.git
cd ADMINCHAT_PANEL/deploy

# 2. 配置环境变量
cp .env.example .env
nano .env  # 修改密码、Bot Token、域名等
```

### 方式一：Docker Run（独立容器）

**前提：** 已有 PostgreSQL 和 Redis 运行中。

```bash
# 修改 .env 中的 DATABASE_URL 和 REDIS_URL 指向你的服务
chmod +x docker-run.sh
./docker-run.sh
```

停止：`docker stop adminchat-backend adminchat-frontend`

### 方式二：Compose 独立版

**前提：** 已有 PostgreSQL 和 Redis。

```bash
# 修改 .env 中的 DATABASE_URL 和 REDIS_URL
docker compose -f docker-compose.standalone.yml up -d
```

更新：

```bash
docker compose -f docker-compose.standalone.yml pull
docker compose -f docker-compose.standalone.yml up -d
```

### 方式三：Compose 一键版（推荐新手）

**包含：** Backend + Frontend + PostgreSQL + Redis + Nginx

```bash
docker compose -f docker-compose.full.yml up -d
```

访问 `http://服务器IP`，默认账号 `admin`（密码见 .env）。

#### 一键版配置组合

| 需求 | 操作 |
|------|------|
| 不用内置 Nginx（自有反向代理） | 注释掉 nginx 服务，取消注释 backend/frontend 的 ports |
| 用外部 PostgreSQL | 注释掉 postgres 服务，修改 DATABASE_URL |
| 用外部 Redis | 注释掉 redis 服务，修改 REDIS_URL |
| 用 bind mount（方便备份） | 将 volume 改为 `./data/xxx:/path` 格式 |
| 连接已有 Docker 网络 | 取消注释 networks.external_net 配置 |

### 数据卷说明

| 类型 | Named Volume | Bind Mount |
|------|-------------|------------|
| 说明 | Docker 管理，`docker volume ls` 查看 | 直接映射宿主机目录 |
| 优点 | 简单、性能好 | 备份方便、直观 |
| PostgreSQL | `adminchat_pgdata` | `./data/postgres` |
| Redis | `adminchat_redisdata` | `./data/redis` |
| 媒体缓存 | `adminchat_media` | `./data/media` |

切换方式：参考各 yml 文件中的注释。

### APISIX / 其他反向代理配置

如果使用 APISIX、Traefik 或其他反向代理，需要配置以下路由：

| 路径 | 转发目标 | 说明 |
|------|---------|------|
| `/api/*` | `adminchat-backend:8000` | REST API |
| `/ws/*` | `adminchat-backend:8000` | WebSocket (需要升级协议) |
| `/webhook/*` | `adminchat-backend:8000` | Telegram Webhook |
| `/verify` | `adminchat-frontend:80` | Turnstile 验证页 |
| `/*` | `adminchat-frontend:80` | 前端 SPA |

---

## English

### Deployment Options

| Method | File | Use Case |
|--------|------|----------|
| **Docker Run** | `docker-run.sh` | Have PG + Redis, deploy ADMINCHAT only |
| **Compose Standalone** | `docker-compose.standalone.yml` | Have PG + Redis, manage with Compose |
| **Compose Full Stack** | `docker-compose.full.yml` | Fresh server, deploy everything |

### Common Steps

```bash
# 1. Clone deployment files
git clone https://github.com/fxxkrlab/ADMINCHAT_PANEL.git
cd ADMINCHAT_PANEL/deploy

# 2. Configure environment
cp .env.example .env
nano .env  # Set passwords, bot tokens, domain, etc.
```

### Method 1: Docker Run (Standalone Containers)

**Prerequisites:** PostgreSQL and Redis already running.

```bash
# Update DATABASE_URL and REDIS_URL in .env
chmod +x docker-run.sh
./docker-run.sh
```

Stop: `docker stop adminchat-backend adminchat-frontend`

### Method 2: Compose Standalone

**Prerequisites:** External PostgreSQL and Redis.

```bash
docker compose -f docker-compose.standalone.yml up -d
```

Update:

```bash
docker compose -f docker-compose.standalone.yml pull
docker compose -f docker-compose.standalone.yml up -d
```

### Method 3: Compose Full Stack (Recommended for beginners)

**Includes:** Backend + Frontend + PostgreSQL + Redis + Nginx

```bash
docker compose -f docker-compose.full.yml up -d
```

Visit `http://server-ip`, default login `admin` (password in .env).

#### Configuration Combinations

| Need | Action |
|------|--------|
| Skip bundled Nginx (own reverse proxy) | Comment out nginx service, uncomment backend/frontend ports |
| Use external PostgreSQL | Comment out postgres service, update DATABASE_URL |
| Use external Redis | Comment out redis service, update REDIS_URL |
| Use bind mounts (easy backup) | Change volumes to `./data/xxx:/path` format |
| Connect to existing Docker network | Uncomment networks.external_net section |

### Volume Types

| Type | Named Volume | Bind Mount |
|------|-------------|------------|
| Description | Docker-managed, `docker volume ls` | Host directory mapping |
| Pros | Simple, good performance | Easy backup, visible |
| PostgreSQL | `adminchat_pgdata` | `./data/postgres` |
| Redis | `adminchat_redisdata` | `./data/redis` |
| Media | `adminchat_media` | `./data/media` |

### Reverse Proxy Routes (APISIX / Traefik / etc.)

| Path | Target | Notes |
|------|--------|-------|
| `/api/*` | `adminchat-backend:8000` | REST API |
| `/ws/*` | `adminchat-backend:8000` | WebSocket (upgrade required) |
| `/webhook/*` | `adminchat-backend:8000` | Telegram Webhook |
| `/verify` | `adminchat-frontend:80` | Turnstile page |
| `/*` | `adminchat-frontend:80` | Frontend SPA |
