# ADMINCHAT Panel - Plugin Loader Architecture

Backend plugin lifecycle management: discovery, loading, isolation, and hot-swapping.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Directory Structure](#2-directory-structure)
3. [Database Schema](#3-database-schema)
4. [PluginManager (loader.py)](#4-pluginmanager-loaderpy)
5. [HotSwappableRouter (handler_mount.py)](#5-hotswappablerouter-handler_mountpy)
6. [Dynamic Router Mount (router_mount.py)](#6-dynamic-router-mount-router_mountpy)
7. [Migration Runner (migration_runner.py)](#7-migration-runner-migration_runnerpy)
8. [Static File Server (static_server.py)](#8-static-file-server-static_serverpy)
9. [CoreSDKBridge (core_sdk.py)](#9-coresdkbridge-core_sdkpy)
10. [Secret Store (secret_store.py)](#10-secret-store-secret_storepy)
11. [Config Store (config_store.py)](#11-config-store-config_storepy)
12. [Health Monitor (health_monitor.py)](#12-health-monitor-health_monitorpy)
13. [Event Bus (event_bus.py)](#13-event-bus-event_buspy)
14. [Signature Verifier (signature_verifier.py)](#14-signature-verifier-signature_verifierpy)
15. [Plugin Management API](#15-plugin-management-api)
16. [Startup Sequence](#16-startup-sequence)
17. [File System Layout](#17-file-system-layout)
18. [Sequence Diagrams](#18-sequence-diagrams)
19. [Error Handling](#19-error-handling)

---

## 1. Overview

The Plugin Loader is the backend subsystem that manages the complete lifecycle of ADMINCHAT Panel plugins. It provides:

- **Hot-loading**: Plugins are activated and deactivated without restarting the Panel process.
- **Isolation**: Each plugin gets its own DB table namespace (`plg_{id}_*`), API route namespace (`/api/v1/p/{id}/`), and Alembic migration chain.
- **Safety**: Bundles are Ed25519-signed, plugin code accesses core data only through a scoped SDK bridge, and a health monitor auto-disables misbehaving plugins.
- **Rollback**: Previous plugin versions are retained on disk, enabling one-command rollback with reverse migrations.

Plugins are distributed as signed zip bundles downloaded from ACP Market and cached at `/data/plugins/`.

---

## 2. Directory Structure

```
backend/app/plugins/
├── __init__.py                # Exports PluginManager, get_plugin_manager()
├── loader.py                  # PluginManager - main orchestrator
├── registry.py                # SQLAlchemy models: InstalledPlugin, PluginSecret
├── router_mount.py            # DynamicRouterMount - FastAPI router management
├── handler_mount.py           # HotSwappableRouter - aiogram Router management
├── migration_runner.py        # PluginMigrationRunner - per-plugin Alembic
├── static_server.py           # PluginStaticServer - serve frontend assets
├── core_sdk.py                # CoreSDKBridge - scoped read API for plugins
├── secret_store.py            # PluginSecretStore - Fernet-encrypted secrets
├── config_store.py            # PluginConfigStore - JSON config persistence
├── health_monitor.py          # PluginHealthMonitor - error tracking + auto-disable
├── event_bus.py               # PluginEventBus - core event distribution
├── signature_verifier.py      # BundleSignatureVerifier - Ed25519 verification
├── schemas.py                 # Pydantic schemas for plugin API responses
├── routes.py                  # FastAPI router for /api/v1/plugins/*
├── exceptions.py              # Plugin-specific exception classes
└── utils.py                   # Manifest parsing, dependency resolution, helpers
```

---

## 3. Database Schema

### 3.1 installed_plugins

Tracks every plugin that has been installed on this Panel instance.

```sql
CREATE TABLE installed_plugins (
    id                SERIAL PRIMARY KEY,
    plugin_id         VARCHAR(50) UNIQUE NOT NULL,     -- manifest.id (e.g., "movie-request")
    name              VARCHAR(100) NOT NULL,            -- manifest.name (human-readable)
    version           VARCHAR(20) NOT NULL,             -- semver of current active version
    previous_version  VARCHAR(20),                      -- retained for rollback
    status            VARCHAR(20) NOT NULL DEFAULT 'installed',
                      -- installed | active | disabled | error | updating
    manifest          JSONB NOT NULL,                   -- full manifest.json snapshot
    config            JSONB DEFAULT '{}',               -- plugin-specific runtime config
    license_key       VARCHAR(200),                     -- for paid plugins (validated on activate)
    error_count       INTEGER DEFAULT 0,                -- consecutive errors (reset on success)
    last_error        TEXT,                             -- last error message + traceback summary
    installed_at      TIMESTAMPTZ DEFAULT NOW(),
    activated_at      TIMESTAMPTZ,                     -- NULL if never activated
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_installed_plugins_status ON installed_plugins(status);
CREATE INDEX idx_installed_plugins_plugin_id ON installed_plugins(plugin_id);
```

**Status transitions:**

```
                    install
  (none) ─────────────────────► installed
                                    │
                           activate │
                                    ▼
                    ┌────────── active ◄──────────┐
                    │               │              │
          deactivate│        error  │     activate │
                    │     (auto)    │              │
                    ▼               ▼              │
                disabled ◄────── error ────────────┘
                    │            (manual fix)
             uninstall│
                    ▼
                 (deleted)
```

### 3.2 plugin_secrets

Stores encrypted key-value pairs per plugin (API keys, tokens, etc.).

```sql
CREATE TABLE plugin_secrets (
    id          SERIAL PRIMARY KEY,
    plugin_id   VARCHAR(50) NOT NULL,
    key         VARCHAR(100) NOT NULL,              -- e.g., "tmdb_api_key"
    value       TEXT NOT NULL,                      -- Fernet-encrypted ciphertext
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plugin_id, key)
);

CREATE INDEX idx_plugin_secrets_plugin_id ON plugin_secrets(plugin_id);
```

### 3.3 SQLAlchemy Models (registry.py)

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.models.base import Base


class InstalledPlugin(Base):
    __tablename__ = "installed_plugins"

    id = Column(Integer, primary_key=True)
    plugin_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    previous_version = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="installed", index=True)
    manifest = Column(JSON, nullable=False)
    config = Column(JSON, default=dict)
    license_key = Column(String(200), nullable=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    activated_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PluginSecret(Base):
    __tablename__ = "plugin_secrets"

    id = Column(Integer, primary_key=True)
    plugin_id = Column(String(50), nullable=False, index=True)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)  # Fernet-encrypted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("plugin_id", "key", name="uq_plugin_secret_plugin_key"),
    )
```

---

## 4. PluginManager (loader.py)

The central orchestrator that coordinates all plugin operations.

### 4.1 Class Definition

```python
import importlib
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugins.registry import InstalledPlugin
from app.plugins.router_mount import DynamicRouterMount
from app.plugins.handler_mount import HotSwappableRouter
from app.plugins.migration_runner import PluginMigrationRunner
from app.plugins.static_server import PluginStaticServer
from app.plugins.core_sdk import CoreSDKBridge
from app.plugins.secret_store import PluginSecretStore
from app.plugins.config_store import PluginConfigStore
from app.plugins.health_monitor import PluginHealthMonitor
from app.plugins.event_bus import PluginEventBus
from app.plugins.signature_verifier import BundleSignatureVerifier
from app.plugins.schemas import PluginInfo


PLUGINS_DATA_DIR = Path("/data/plugins")


class PluginManager:
    """Manages the complete plugin lifecycle.

    Instantiated once during Panel startup and available globally
    via get_plugin_manager().
    """

    def __init__(
        self,
        app: FastAPI,
        dispatcher: Dispatcher,
        db_session_factory,          # async_sessionmaker
    ):
        self._app = app
        self._dispatcher = dispatcher
        self._db_session_factory = db_session_factory

        # Sub-components
        self._router_mount = DynamicRouterMount()
        self._handler_mount = HotSwappableRouter()
        self._migration_runner = PluginMigrationRunner(db_session_factory)
        self._static_server = PluginStaticServer(app)
        self._secret_store = PluginSecretStore(db_session_factory)
        self._config_store = PluginConfigStore(db_session_factory)
        self._health_monitor = PluginHealthMonitor(db_session_factory, self)
        self._event_bus = PluginEventBus()
        self._signature_verifier = BundleSignatureVerifier()

        # Runtime state
        self._loaded: dict[str, _LoadedPlugin] = {}   # plugin_id -> loaded state

    # --- Lifecycle -----------------------------------------------------------

    async def startup(self) -> dict[str, str]:
        """Called during Panel startup lifespan.

        Loads and activates every plugin with status='active' in the DB.
        Returns dict of {plugin_id: "ok" | error_message}.
        """

    async def shutdown(self) -> None:
        """Called during Panel shutdown lifespan.

        Calls teardown() on every loaded plugin in reverse load order.
        """

    # --- Install / Uninstall -------------------------------------------------

    async def install(
        self, plugin_id: str, version: str, zip_path: Path
    ) -> PluginInfo:
        """Install a plugin from a downloaded zip bundle.

        Steps:
          1. Verify Ed25519 bundle signature.
          2. Extract zip to /data/plugins/{id}/{version}/.
          3. Parse and validate manifest.json.
          4. Check compatibility: Panel version, Python version, dependencies.
          5. Insert row into installed_plugins (status='installed').
          6. Return PluginInfo (not yet active).

        Raises:
          PluginSignatureError  - invalid or missing signature
          PluginManifestError   - malformed manifest
          PluginConflictError   - already installed at this version
          PluginCompatError     - Panel version mismatch
        """

    async def uninstall(
        self, plugin_id: str, *, drop_tables: bool = False
    ) -> None:
        """Completely remove a plugin.

        Steps:
          1. If currently active, call deactivate() first.
          2. If drop_tables=True, run migration downgrade to base (drops plg_{id}_* tables).
          3. Delete /data/plugins/{id}/ directory tree.
          4. DELETE FROM installed_plugins WHERE plugin_id = :id.
          5. DELETE FROM plugin_secrets WHERE plugin_id = :id.
          6. Emit WebSocket event: plugin_changed(action='uninstalled').
        """

    # --- Activate / Deactivate -----------------------------------------------

    async def activate(self, plugin_id: str) -> None:
        """Activate an installed plugin (hot-load, no restart).

        Steps:
          1. Read manifest.json from /data/plugins/{id}/{version}/.
          2. Dynamic-import the Python entry_point module.
          3. Run pending Alembic migrations for this plugin.
          4. Register FastAPI router at /api/v1/p/{id}/.
          5. Register aiogram handlers via HotSwappableRouter.
          6. Mount frontend static files at /plugins/{id}/.
          7. Create CoreSDKBridge + SecretStore + ConfigStore for plugin.
          8. Call plugin.setup(context).
          9. Update DB: status='active', activated_at=now().
         10. Emit WebSocket event: plugin_changed(action='activated').

        Raises:
          PluginNotFoundError   - no such plugin_id in DB
          PluginImportError     - Python import failed
          PluginSetupError      - plugin.setup() raised
        """

    async def deactivate(self, plugin_id: str) -> None:
        """Deactivate a running plugin (keep all data).

        Steps:
          1. Call plugin.teardown() (with timeout).
          2. Unsubscribe all event bus listeners for this plugin.
          3. Remove FastAPI router for this plugin.
          4. Remove aiogram router from HotSwappableRouter.
          5. Unmount frontend static files.
          6. Remove Python module from sys.modules.
          7. Update DB: status='disabled'.
          8. Emit WebSocket event: plugin_changed(action='deactivated').
        """

    # --- Update / Rollback ---------------------------------------------------

    async def update(
        self, plugin_id: str, new_version: str, zip_path: Path
    ) -> None:
        """Update a plugin to a new version with automatic rollback on failure.

        Steps:
          1. Install new version alongside old (extract to /data/plugins/{id}/{new_version}/).
          2. Verify new manifest compatibility.
          3. Deactivate current version.
          4. Store current version as previous_version.
          5. Run migrations from old schema to new.
          6. Activate new version.
          7. If activation fails:
             a. Reverse-migrate back to old schema.
             b. Reactivate old version.
             c. Set status='error' with error details.
             d. Raise PluginUpdateError.
          8. On success, keep old version dir for future rollback.
        """

    async def rollback(self, plugin_id: str) -> None:
        """Rollback to previous_version.

        Requires previous_version to be set and the old version dir to exist.

        Steps:
          1. Deactivate current version.
          2. Reverse-migrate to old schema.
          3. Swap version and previous_version in DB.
          4. Activate old version.
        """

    # --- Query ---------------------------------------------------------------

    def get_installed(self) -> list[PluginInfo]:
        """Return all installed plugins with their current status."""

    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """Return info for a specific plugin, or None."""

    def is_active(self, plugin_id: str) -> bool:
        """Check if a plugin is currently loaded and active."""

    # --- Internal properties -------------------------------------------------

    @property
    def event_bus(self) -> PluginEventBus:
        """Expose event bus for core code to emit events."""
        return self._event_bus

    @property
    def handler_mount(self) -> HotSwappableRouter:
        """Expose master router for Dispatcher inclusion."""
        return self._handler_mount
```

### 4.2 _LoadedPlugin Internal State

```python
from dataclasses import dataclass, field
from types import ModuleType


@dataclass
class _LoadedPlugin:
    """Runtime state for a loaded plugin."""
    plugin_id: str
    version: str
    manifest: dict
    module: ModuleType                    # The imported plugin.py module
    plugin_path: Path                     # /data/plugins/{id}/{version}/
    sdk: CoreSDKBridge
    secret_store: PluginSecretStore
    config_store: PluginConfigStore
    setup_context: dict = field(default_factory=dict)
```

### 4.3 Dynamic Import Mechanism

```python
async def _import_plugin(self, plugin_id: str, plugin_path: Path, manifest: dict) -> ModuleType:
    """Dynamically import a plugin's entry_point module.

    The manifest specifies:
      "backend": { "entry_point": "plugin" }
    which maps to /data/plugins/{id}/{version}/backend/plugin.py

    Import strategy:
      1. Add plugin's backend/ dir to sys.path temporarily.
      2. Import the module with a namespaced name: plg_{id}.{entry_point}
      3. Validate the module exposes required interface (setup, teardown, etc.).
      4. Remove from sys.path (module stays in sys.modules).
    """
    entry_point = manifest["backend"]["entry_point"]
    module_name = f"plg_{plugin_id}.{entry_point}"
    backend_path = plugin_path / "backend"

    # Namespace the import to avoid collisions
    spec = importlib.util.spec_from_file_location(
        module_name,
        backend_path / f"{entry_point}.py",
        submodule_search_locations=[str(backend_path)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # Validate plugin interface
    if not hasattr(module, "setup"):
        raise PluginImportError(plugin_id, "Module missing setup() function")

    return module
```

### 4.4 Plugin Interface Contract

Every plugin's entry_point module must expose:

```python
# plugin.py (inside the plugin bundle)

async def setup(context: PluginContext) -> None:
    """Called when the plugin is activated.

    context provides:
      - sdk: CoreSDKBridge (scoped read access to core data)
      - secrets: PluginSecretStore (encrypted key-value storage)
      - config: PluginConfigStore (JSON config access)
      - event_bus: subscribe to core events
      - logger: pre-configured logger with plugin prefix
    """

async def teardown() -> None:
    """Called when the plugin is deactivated. Clean up resources."""

def get_router() -> APIRouter | None:
    """Return FastAPI router for plugin API endpoints, or None."""

def get_bot_router() -> Router | None:
    """Return aiogram Router for bot message handlers, or None."""

def get_bot_router_priority() -> int:
    """Return priority for bot router ordering. Default: 50.
    Lower = executes first. Range: 1-100.
    Core handlers run at priority 0."""
```

### 4.5 PluginContext (passed to setup)

```python
@dataclass
class PluginContext:
    """Context object passed to plugin.setup()."""
    plugin_id: str
    version: str
    manifest: dict
    plugin_path: Path              # /data/plugins/{id}/{version}/
    sdk: CoreSDKBridge             # Scoped read access to core data
    secrets: PluginSecretStore     # Encrypted secret storage
    config: PluginConfigStore      # Plugin configuration
    event_bus: PluginEventBus      # Subscribe to core events
    logger: logging.Logger         # Pre-configured logger: "acp.plugin.{id}"
```

---

## 5. HotSwappableRouter (handler_mount.py)

Manages dynamic addition and removal of aiogram Routers at runtime without restarting the Dispatcher.

### 5.1 Problem

aiogram's `Dispatcher.include_router()` is designed to be called once at startup. There is no built-in `remove_router()`. Plugins need to add and remove handlers dynamically.

### 5.2 Solution

Use a single master Router that is included in the Dispatcher once. Plugin sub-routers are added to and removed from this master router. When a plugin is removed, the master router's `sub_routers` list is cleared and rebuilt from the remaining plugins, sorted by priority.

### 5.3 Implementation

```python
from aiogram import Router
import logging

logger = logging.getLogger("acp.plugins.handler_mount")


class HotSwappableRouter:
    """A master Router that allows dynamic add/remove of plugin sub-routers at runtime.

    The master_router is included in the Dispatcher ONCE during Panel startup.
    Plugin routers are added/removed from it dynamically. On each mutation,
    the sub_routers list is cleared and rebuilt in priority order.
    """

    def __init__(self):
        self.master_router = Router(name="plugins_master")
        self._plugin_routers: dict[str, tuple[Router, int]] = {}
        # plugin_id -> (router, priority)

    def add(self, plugin_id: str, router: Router, priority: int = 50) -> None:
        """Add a plugin's aiogram Router.

        Args:
            plugin_id: Unique plugin identifier.
            router: The plugin's aiogram Router instance.
            priority: Execution order. Lower value = executes first.
                      Core handlers run at priority 0.
                      Plugin default is 50. Valid range: 1-100.
        """
        if plugin_id in self._plugin_routers:
            logger.warning("Router for plugin %s already registered, replacing", plugin_id)
            self.remove(plugin_id)

        router.name = f"plg_{plugin_id}"
        self._plugin_routers[plugin_id] = (router, max(1, min(100, priority)))
        self._rebuild()
        logger.info("Added bot router for plugin %s (priority %d)", plugin_id, priority)

    def remove(self, plugin_id: str) -> None:
        """Remove a plugin's aiogram Router.

        Safe to call even if plugin_id is not registered.
        """
        if plugin_id not in self._plugin_routers:
            return
        del self._plugin_routers[plugin_id]
        self._rebuild()
        logger.info("Removed bot router for plugin %s", plugin_id)

    def _rebuild(self) -> None:
        """Clear master_router's sub_routers and re-include all plugin routers
        sorted by priority (ascending = lower priority number executes first).

        This is O(n) where n = number of active plugins. Since n is typically
        small (< 50) and this only runs on plugin activate/deactivate, the cost
        is negligible.
        """
        # Clear existing sub-routers
        self.master_router.sub_routers.clear()

        # Sort by priority (ascending) then by plugin_id (stable order)
        sorted_routers = sorted(
            self._plugin_routers.items(),
            key=lambda item: (item[1][1], item[0]),  # (priority, plugin_id)
        )

        for plugin_id, (router, _priority) in sorted_routers:
            self.master_router.include_router(router)

        logger.debug(
            "Rebuilt master router with %d plugin routers: %s",
            len(sorted_routers),
            [pid for pid, _ in sorted_routers],
        )

    @property
    def active_plugins(self) -> list[str]:
        """Return list of plugin_ids with registered routers."""
        return list(self._plugin_routers.keys())
```

### 5.4 Dispatcher Integration

In `main.py` lifespan:

```python
# During startup, AFTER PluginManager is created:
plugin_manager = PluginManager(app, dispatcher, session_factory)

# Include the master router in the dispatcher ONCE
dispatcher.include_router(plugin_manager.handler_mount.master_router)

# Now activate plugins - their sub-routers are added to master_router
await plugin_manager.startup()
```

### 5.5 Handler Execution Order

```
Incoming Telegram update
  │
  ▼
Dispatcher
  ├── Core Router (priority 0)
  │   ├── /start handler
  │   ├── private message handler
  │   └── group message handler
  │
  └── plugins_master Router
      ├── plg_movie-request Router (priority 30)
      │   └── /movie command handler
      ├── plg_analytics Router (priority 50)
      │   └── message observer (no filter, passes through)
      └── plg_moderation Router (priority 90)
          └── content filter handler
```

aiogram processes handlers in order. If a handler matches and does not propagate, subsequent handlers are skipped.

---

## 6. Dynamic Router Mount (router_mount.py)

Manages dynamic addition and removal of FastAPI APIRouter instances at runtime.

### 6.1 Implementation

```python
from fastapi import FastAPI, APIRouter
from starlette.routing import Mount
import logging

logger = logging.getLogger("acp.plugins.router_mount")

PLUGIN_API_PREFIX = "/api/v1/p"


class DynamicRouterMount:
    """Manages dynamic addition/removal of FastAPI routers for plugins.

    All plugin routes are mounted under /api/v1/p/{plugin_id}/...
    """

    def __init__(self):
        self._mounted: dict[str, APIRouter] = {}  # plugin_id -> router

    def mount(
        self,
        app: FastAPI,
        plugin_id: str,
        router: APIRouter,
    ) -> None:
        """Mount a plugin's router at /api/v1/p/{plugin_id}/.

        Args:
            app: The FastAPI application instance.
            plugin_id: The plugin identifier (used as path prefix).
            router: The plugin's APIRouter.
        """
        if plugin_id in self._mounted:
            self.unmount(app, plugin_id)

        prefix = f"{PLUGIN_API_PREFIX}/{plugin_id}"
        app.include_router(router, prefix=prefix, tags=[f"plugin:{plugin_id}"])
        self._mounted[plugin_id] = router
        logger.info("Mounted API router for plugin %s at %s", plugin_id, prefix)

    def unmount(self, app: FastAPI, plugin_id: str) -> None:
        """Remove all routes for a plugin from the FastAPI app.

        Works by filtering app.router.routes to remove any route whose
        path starts with the plugin's prefix.
        """
        if plugin_id not in self._mounted:
            return

        prefix = f"{PLUGIN_API_PREFIX}/{plugin_id}"
        original_count = len(app.router.routes)

        app.router.routes = [
            route for route in app.router.routes
            if not (
                isinstance(route, (Mount,)) and getattr(route, "path", "").startswith(prefix)
                or hasattr(route, "path") and getattr(route, "path", "").startswith(prefix)
            )
        ]

        removed = original_count - len(app.router.routes)
        del self._mounted[plugin_id]
        logger.info("Unmounted %d routes for plugin %s", removed, plugin_id)

    @property
    def mounted_plugins(self) -> list[str]:
        return list(self._mounted.keys())
```

### 6.2 Plugin Route Example

A plugin's `routes.py`:

```python
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user  # Core dependency reuse

router = APIRouter()

@router.get("/requests")
async def list_requests(user=Depends(get_current_user)):
    """GET /api/v1/p/movie-request/requests"""
    ...

@router.post("/requests")
async def create_request(user=Depends(get_current_user)):
    """POST /api/v1/p/movie-request/requests"""
    ...
```

### 6.3 Authentication

Plugin API routes reuse the core `get_current_user` dependency for JWT authentication. Plugins do not implement their own auth. The core dependency is available because the plugin's backend directory is imported with access to `app.*`.

---

## 7. Migration Runner (migration_runner.py)

Each plugin maintains its own independent Alembic migration chain, fully isolated from the core Panel migrations.

### 7.1 Implementation

```python
import asyncio
from pathlib import Path
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
import logging

logger = logging.getLogger("acp.plugins.migration_runner")


class PluginMigrationRunner:
    """Run per-plugin Alembic migrations.

    Each plugin stores its migration scripts in:
      /data/plugins/{id}/{version}/backend/migrations/

    Each plugin's Alembic version is tracked in a separate table:
      plg_{id}_alembic_version

    This ensures complete isolation from core Panel migrations and from
    other plugins' migrations.
    """

    def __init__(self, db_session_factory):
        self._db_session_factory = db_session_factory

    async def upgrade(self, plugin_id: str, plugin_path: Path) -> None:
        """Run all pending migrations for a plugin to head.

        Args:
            plugin_id: The plugin identifier.
            plugin_path: Path to the active version directory.
        """
        migrations_dir = plugin_path / "backend" / "migrations"
        if not migrations_dir.exists():
            logger.debug("No migrations directory for plugin %s, skipping", plugin_id)
            return

        config = self._build_config(plugin_id, migrations_dir)
        # Run in thread pool since Alembic is synchronous
        await asyncio.to_thread(alembic_command.upgrade, config, "head")
        logger.info("Migrations upgraded to head for plugin %s", plugin_id)

    async def downgrade(self, plugin_id: str, plugin_path: Path, target: str = "-1") -> None:
        """Downgrade one or more migration steps (used for rollback).

        Args:
            plugin_id: The plugin identifier.
            plugin_path: Path to the version directory containing the migrations.
            target: Alembic revision target. "-1" = one step back. "base" = drop all.
        """
        migrations_dir = plugin_path / "backend" / "migrations"
        if not migrations_dir.exists():
            return

        config = self._build_config(plugin_id, migrations_dir)
        await asyncio.to_thread(alembic_command.downgrade, config, target)
        logger.info("Migrations downgraded to %s for plugin %s", target, plugin_id)

    def _build_config(self, plugin_id: str, migrations_dir: Path) -> AlembicConfig:
        """Build an Alembic Config scoped to a specific plugin.

        Key differences from core Alembic config:
          - version_table = plg_{id}_alembic_version
          - script_location = plugin's migrations/ directory
          - Uses the same database URL as the core Panel
        """
        config = AlembicConfig()
        config.set_main_option("script_location", str(migrations_dir))
        config.set_main_option("sqlalchemy.url", self._get_db_url())
        config.set_main_option("version_table", f"plg_{plugin_id}_alembic_version")
        return config
```

### 7.2 Plugin Table Naming Convention

All tables created by a plugin MUST be prefixed with `plg_{plugin_id}_`:

```python
# In a plugin's models.py:
class MovieRequest(Base):
    __tablename__ = "plg_movie_request_requests"  # plg_{id}_requests
    ...
```

This is enforced by manifest validation: the loader checks that every table created by a plugin's migrations uses the correct prefix.

### 7.3 Migration Directory Structure (inside a plugin)

```
backend/migrations/
├── env.py              # Standard Alembic env (provided by plugin SDK template)
├── script.py.mako      # Template
└── versions/
    ├── 001_initial.py
    └── 002_add_status_column.py
```

---

## 8. Static File Server (static_server.py)

Serves plugin frontend assets (JavaScript, CSS, images) via FastAPI's static file mounting.

### 8.1 Implementation

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging

logger = logging.getLogger("acp.plugins.static_server")


class PluginStaticServer:
    """Mount and unmount plugin frontend static files.

    Plugin frontend assets are served at:
      /plugins/{plugin_id}/   ->   /data/plugins/{id}/{version}/frontend/

    The most important file is remoteEntry.js, which is the Module Federation
    entry point loaded by the host frontend.
    """

    def __init__(self, app: FastAPI):
        self._app = app
        self._mounts: dict[str, str] = {}  # plugin_id -> mount_path

    def mount(self, plugin_id: str, plugin_path: Path) -> None:
        """Mount a plugin's frontend/ directory as static files.

        Args:
            plugin_id: The plugin identifier.
            plugin_path: Path to the active version directory.
        """
        frontend_dir = plugin_path / "frontend"
        if not frontend_dir.exists():
            logger.debug("No frontend directory for plugin %s, skipping static mount", plugin_id)
            return

        mount_path = f"/plugins/{plugin_id}"
        self._app.mount(
            mount_path,
            StaticFiles(directory=str(frontend_dir)),
            name=f"plg_static_{plugin_id}",
        )
        self._mounts[plugin_id] = mount_path
        logger.info("Mounted static files for plugin %s at %s", plugin_id, mount_path)

    def unmount(self, plugin_id: str) -> None:
        """Unmount a plugin's static files.

        Removes the Mount from app.routes.
        """
        if plugin_id not in self._mounts:
            return

        mount_path = self._mounts[plugin_id]
        self._app.routes[:] = [
            route for route in self._app.routes
            if not (hasattr(route, "path") and route.path == mount_path)
        ]
        del self._mounts[plugin_id]
        logger.info("Unmounted static files for plugin %s", plugin_id)
```

---

## 9. CoreSDKBridge (core_sdk.py)

Provides plugins with safe, read-only access to core Panel data. Access is scoped by the plugin's declared `core_api_scopes` in its manifest.

### 9.1 Implementation

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

logger = logging.getLogger("acp.plugins.core_sdk")


class PluginPermissionError(Exception):
    """Raised when a plugin attempts to access a scope it hasn't declared."""
    def __init__(self, plugin_id: str, scope: str):
        self.plugin_id = plugin_id
        self.scope = scope
        super().__init__(f"Plugin '{plugin_id}' does not have permission for scope '{scope}'")


class CoreSDKBridge:
    """Read-only access to core Panel data, scoped by manifest permissions.

    Plugins declare required scopes in manifest.json:
      "permissions": {
        "core_api_scopes": ["users:read", "bots:read", "messages:read"]
      }

    Only declared scopes are accessible. Attempting to access undeclared
    scopes raises PluginPermissionError.
    """

    # Available scopes and their descriptions
    AVAILABLE_SCOPES = {
        "users:read":       "Read user profiles and roles",
        "users:write":      "Modify user profiles (admin actions)",
        "bots:read":        "Read bot configurations and status",
        "messages:read":    "Read message history",
        "messages:write":   "Send messages via bots",
        "groups:read":      "Read chat group information",
        "settings:read":    "Read Panel configuration",
        "faq:read":         "Read FAQ entries",
        "faq:write":        "Create/update FAQ entries",
    }

    def __init__(self, plugin_id: str, manifest: dict, session_factory):
        self._plugin_id = plugin_id
        self._allowed_scopes: set[str] = set(
            manifest.get("permissions", {}).get("core_api_scopes", [])
        )
        self._session_factory = session_factory

    def _check_scope(self, scope: str) -> None:
        if scope not in self._allowed_scopes:
            logger.warning(
                "Plugin %s denied access to scope %s", self._plugin_id, scope
            )
            raise PluginPermissionError(self._plugin_id, scope)

    @property
    def users(self) -> "UsersAPI":
        self._check_scope("users:read")
        return UsersAPI(self._session_factory)

    @property
    def bots(self) -> "BotsAPI":
        self._check_scope("bots:read")
        return BotsAPI(self._session_factory)

    @property
    def messages(self) -> "MessagesAPI":
        self._check_scope("messages:read")
        return MessagesAPI(self._session_factory)

    @property
    def groups(self) -> "GroupsAPI":
        self._check_scope("groups:read")
        return GroupsAPI(self._session_factory)

    @property
    def faq(self) -> "FaqAPI":
        self._check_scope("faq:read")
        return FaqAPI(self._session_factory)

    @property
    def settings(self) -> "SettingsAPI":
        self._check_scope("settings:read")
        return SettingsAPI(self._session_factory)


class UsersAPI:
    """Read-only user data access for plugins."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def get_by_id(self, user_id: int) -> dict | None:
        """Get a user by internal ID. Returns sanitized dict (no password hash)."""

    async def get_by_telegram_id(self, telegram_id: int) -> dict | None:
        """Get a user by Telegram user ID."""

    async def list_users(
        self, *, page: int = 1, page_size: int = 20, role: str | None = None
    ) -> dict:
        """List users with pagination. Returns {items: [...], total: int}."""


class BotsAPI:
    """Read-only bot data access for plugins."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def get_active_bots(self) -> list[dict]:
        """Return all active bot configurations (tokens are masked)."""

    async def get_bot(self, bot_id: int) -> dict | None:
        """Get a specific bot's configuration."""


class MessagesAPI:
    """Read-only message data access for plugins."""

    async def get_conversation(
        self, user_telegram_id: int, *, limit: int = 50, before_id: int | None = None
    ) -> list[dict]:
        """Get messages for a conversation with pagination."""

    async def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """Full-text search across messages."""


# GroupsAPI, FaqAPI, SettingsAPI follow the same pattern
```

---

## 10. Secret Store (secret_store.py)

Provides encrypted storage for plugin-specific secrets (API keys, tokens, credentials).

### 10.1 Implementation

```python
from cryptography.fernet import Fernet
from sqlalchemy import select, delete
from app.plugins.registry import PluginSecret
import os
import logging

logger = logging.getLogger("acp.plugins.secret_store")

# Encryption key: generated once during first Panel startup, stored in env/file
# PLUGIN_SECRET_KEY env var, or auto-generated to /data/.plugin_secret_key
_FERNET_KEY: bytes | None = None


def _get_fernet() -> Fernet:
    global _FERNET_KEY
    if _FERNET_KEY is None:
        key = os.environ.get("PLUGIN_SECRET_KEY")
        if not key:
            key_file = Path("/data/.plugin_secret_key")
            if key_file.exists():
                key = key_file.read_text().strip()
            else:
                key = Fernet.generate_key().decode()
                key_file.write_text(key)
                key_file.chmod(0o600)
                logger.info("Generated new plugin secret encryption key")
        _FERNET_KEY = key.encode() if isinstance(key, str) else key
    return Fernet(_FERNET_KEY)


class PluginSecretStore:
    """Encrypted key-value storage scoped to a single plugin.

    Values are encrypted with Fernet (AES-128-CBC) before storage.
    Keys are stored in plaintext for lookup.
    """

    def __init__(self, plugin_id: str, session_factory):
        self._plugin_id = plugin_id
        self._session_factory = session_factory
        self._fernet = _get_fernet()

    async def get(self, key: str) -> str | None:
        """Retrieve a decrypted secret value. Returns None if not found."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PluginSecret).where(
                    PluginSecret.plugin_id == self._plugin_id,
                    PluginSecret.key == key,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return self._fernet.decrypt(row.value.encode()).decode()

    async def set(self, key: str, value: str) -> None:
        """Store an encrypted secret. Overwrites existing value for the same key."""
        encrypted = self._fernet.encrypt(value.encode()).decode()
        async with self._session_factory() as session:
            existing = await session.execute(
                select(PluginSecret).where(
                    PluginSecret.plugin_id == self._plugin_id,
                    PluginSecret.key == key,
                )
            )
            row = existing.scalar_one_or_none()
            if row:
                row.value = encrypted
            else:
                session.add(PluginSecret(
                    plugin_id=self._plugin_id,
                    key=key,
                    value=encrypted,
                ))
            await session.commit()

    async def delete(self, key: str) -> bool:
        """Delete a secret. Returns True if it existed."""
        async with self._session_factory() as session:
            result = await session.execute(
                delete(PluginSecret).where(
                    PluginSecret.plugin_id == self._plugin_id,
                    PluginSecret.key == key,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def list_keys(self) -> list[str]:
        """List all secret keys (not values) for this plugin."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PluginSecret.key).where(
                    PluginSecret.plugin_id == self._plugin_id
                )
            )
            return [row[0] for row in result.all()]

    async def delete_all(self) -> int:
        """Delete all secrets for this plugin (called on uninstall). Returns count."""
        async with self._session_factory() as session:
            result = await session.execute(
                delete(PluginSecret).where(
                    PluginSecret.plugin_id == self._plugin_id
                )
            )
            await session.commit()
            return result.rowcount
```

---

## 11. Config Store (config_store.py)

Manages plugin-specific configuration stored as JSONB in the `installed_plugins.config` column.

```python
from sqlalchemy import select, update
from app.plugins.registry import InstalledPlugin
import copy
import logging

logger = logging.getLogger("acp.plugins.config_store")


class PluginConfigStore:
    """Read/write access to a plugin's configuration (JSONB).

    Config is stored in the installed_plugins.config column.
    Plugins define their config schema in manifest.json under
    "settings.schema" (JSON Schema format), which the Panel UI
    uses to render a settings form.
    """

    def __init__(self, plugin_id: str, session_factory):
        self._plugin_id = plugin_id
        self._session_factory = session_factory
        self._cache: dict | None = None  # In-memory cache

    async def get_all(self) -> dict:
        """Return the full config dict."""
        if self._cache is not None:
            return copy.deepcopy(self._cache)

        async with self._session_factory() as session:
            result = await session.execute(
                select(InstalledPlugin.config).where(
                    InstalledPlugin.plugin_id == self._plugin_id
                )
            )
            config = result.scalar_one_or_none() or {}
            self._cache = config
            return copy.deepcopy(config)

    async def get(self, key: str, default=None):
        """Get a single config value."""
        config = await self.get_all()
        return config.get(key, default)

    async def set(self, key: str, value) -> None:
        """Set a single config value (merges into existing config)."""
        config = await self.get_all()
        config[key] = value
        await self._save(config)

    async def set_many(self, updates: dict) -> None:
        """Set multiple config values at once."""
        config = await self.get_all()
        config.update(updates)
        await self._save(config)

    async def _save(self, config: dict) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(InstalledPlugin)
                .where(InstalledPlugin.plugin_id == self._plugin_id)
                .values(config=config)
            )
            await session.commit()
        self._cache = config

    def invalidate_cache(self) -> None:
        """Clear the in-memory cache (e.g., after external config update)."""
        self._cache = None
```

---

## 12. Health Monitor (health_monitor.py)

Tracks consecutive errors per plugin and auto-disables plugins that exceed the threshold.

### 12.1 Implementation

```python
from sqlalchemy import select, update
from app.plugins.registry import InstalledPlugin
import traceback
import logging

logger = logging.getLogger("acp.plugins.health_monitor")


class PluginHealthMonitor:
    """Track plugin errors and auto-disable on threshold.

    When a plugin handler (bot or API) raises an unhandled exception,
    the error is recorded here. After ERROR_THRESHOLD consecutive errors,
    the plugin is automatically deactivated.

    A single successful execution resets the counter.
    """

    ERROR_THRESHOLD = 5  # consecutive errors before auto-disable

    def __init__(self, session_factory, plugin_manager: "PluginManager"):
        self._session_factory = session_factory
        self._plugin_manager = plugin_manager
        self._counters: dict[str, int] = {}  # in-memory for speed

    async def record_error(self, plugin_id: str, error: Exception) -> None:
        """Record an error for a plugin.

        If the consecutive error count reaches ERROR_THRESHOLD, the plugin
        is automatically deactivated and its status set to 'error'.
        """
        count = self._counters.get(plugin_id, 0) + 1
        self._counters[plugin_id] = count

        error_text = f"{type(error).__name__}: {error}\n{traceback.format_exc()}"

        # Update DB
        async with self._session_factory() as session:
            await session.execute(
                update(InstalledPlugin)
                .where(InstalledPlugin.plugin_id == plugin_id)
                .values(error_count=count, last_error=error_text[:2000])
            )
            await session.commit()

        logger.warning(
            "Plugin %s error %d/%d: %s",
            plugin_id, count, self.ERROR_THRESHOLD, error,
        )

        if count >= self.ERROR_THRESHOLD:
            logger.error(
                "Plugin %s exceeded error threshold (%d), auto-disabling",
                plugin_id, self.ERROR_THRESHOLD,
            )
            try:
                await self._plugin_manager.deactivate(plugin_id)
                # Set status to 'error' (not 'disabled') so UI shows the issue
                async with self._session_factory() as session:
                    await session.execute(
                        update(InstalledPlugin)
                        .where(InstalledPlugin.plugin_id == plugin_id)
                        .values(status="error")
                    )
                    await session.commit()
            except Exception as e:
                logger.error("Failed to auto-disable plugin %s: %s", plugin_id, e)

    async def record_success(self, plugin_id: str) -> None:
        """Reset the error counter on a successful execution."""
        if self._counters.get(plugin_id, 0) == 0:
            return  # No errors to reset

        self._counters[plugin_id] = 0
        async with self._session_factory() as session:
            await session.execute(
                update(InstalledPlugin)
                .where(InstalledPlugin.plugin_id == plugin_id)
                .values(error_count=0)
            )
            await session.commit()

    async def get_status(self, plugin_id: str) -> dict:
        """Return health status for a plugin."""
        return {
            "plugin_id": plugin_id,
            "consecutive_errors": self._counters.get(plugin_id, 0),
            "threshold": self.ERROR_THRESHOLD,
            "healthy": self._counters.get(plugin_id, 0) < self.ERROR_THRESHOLD,
        }
```

### 12.2 Integration with Handlers

Error recording is integrated via middleware/wrappers:

```python
# In plugin bot handler wrapper (handler_mount.py)
async def _wrapped_handler(handler, event, data, plugin_id):
    try:
        result = await handler(event, data)
        await health_monitor.record_success(plugin_id)
        return result
    except Exception as e:
        await health_monitor.record_error(plugin_id, e)
        raise  # Re-raise so aiogram's error handling still works

# In plugin API route wrapper (router_mount.py middleware)
@app.middleware("http")
async def plugin_error_middleware(request, call_next):
    if request.url.path.startswith("/api/v1/p/"):
        plugin_id = request.url.path.split("/")[4]
        try:
            response = await call_next(request)
            await health_monitor.record_success(plugin_id)
            return response
        except Exception as e:
            await health_monitor.record_error(plugin_id, e)
            raise
    return await call_next(request)
```

---

## 13. Event Bus (event_bus.py)

Distributes core Panel events to plugins that have subscribed to them.

### 13.1 Implementation

```python
import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger("acp.plugins.event_bus")


class PluginEventBus:
    """Distributes core events to subscribed plugin handlers.

    Core events are emitted from various parts of the Panel backend.
    Plugins subscribe to events they're interested in during setup().

    Error isolation: if one plugin's handler raises an exception,
    it does not affect other subscribers or the core code that emitted the event.
    """

    def __init__(self):
        self._subscribers: dict[str, list[tuple[str, Callable[..., Awaitable]]]] = {}
        # event_name -> [(plugin_id, async_handler), ...]

    def subscribe(
        self, plugin_id: str, event: str, handler: Callable[..., Awaitable]
    ) -> None:
        """Register a plugin's async handler for an event.

        Args:
            plugin_id: The subscribing plugin's ID.
            event: Event name (e.g., "message.received").
            handler: Async callable(data: dict) -> None.
        """
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append((plugin_id, handler))
        logger.debug("Plugin %s subscribed to event %s", plugin_id, event)

    def unsubscribe_all(self, plugin_id: str) -> int:
        """Remove all subscriptions for a plugin (called on deactivate).

        Returns the number of subscriptions removed.
        """
        removed = 0
        for event in list(self._subscribers.keys()):
            original = len(self._subscribers[event])
            self._subscribers[event] = [
                (pid, handler)
                for pid, handler in self._subscribers[event]
                if pid != plugin_id
            ]
            removed += original - len(self._subscribers[event])
            if not self._subscribers[event]:
                del self._subscribers[event]
        if removed:
            logger.debug("Unsubscribed %d handlers for plugin %s", removed, plugin_id)
        return removed

    async def emit(self, event: str, data: dict) -> None:
        """Emit an event to all subscribers.

        Each handler is called with the event data dict.
        Errors in one handler are logged but do not affect others.
        Handlers run concurrently via asyncio.gather.
        """
        subscribers = self._subscribers.get(event, [])
        if not subscribers:
            return

        logger.debug("Emitting event %s to %d subscribers", event, len(subscribers))

        async def _safe_call(plugin_id: str, handler):
            try:
                await asyncio.wait_for(handler(data), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error(
                    "Plugin %s handler for %s timed out (10s)", plugin_id, event
                )
            except Exception as e:
                logger.error(
                    "Plugin %s handler for %s raised: %s", plugin_id, event, e,
                    exc_info=True,
                )

        await asyncio.gather(
            *[_safe_call(pid, handler) for pid, handler in subscribers]
        )

    @property
    def registered_events(self) -> dict[str, list[str]]:
        """Return {event_name: [plugin_ids]} for debugging."""
        return {
            event: [pid for pid, _ in subs]
            for event, subs in self._subscribers.items()
        }
```

### 13.2 Core Events

Events emitted by core Panel code that plugins can subscribe to:

| Event Name | Data Fields | Emitted From |
|---|---|---|
| `message.received` | `bot_id`, `user_telegram_id`, `chat_id`, `text`, `message_id`, `timestamp` | `private.py` handler |
| `message.sent` | `bot_id`, `user_telegram_id`, `chat_id`, `text`, `message_id`, `operator_id` | Reply API endpoint |
| `message.group` | `bot_id`, `group_id`, `user_telegram_id`, `text`, `message_id` | `group.py` handler |
| `user.new` | `user_telegram_id`, `username`, `first_name`, `bot_id` | First-message detection |
| `user.blocked` | `user_telegram_id`, `blocked_by`, `reason` | Block API endpoint |
| `user.unblocked` | `user_telegram_id`, `unblocked_by` | Unblock API endpoint |
| `bot.started` | `bot_id`, `bot_username` | BotManager start |
| `bot.stopped` | `bot_id`, `bot_username`, `reason` | BotManager stop |
| `operator.login` | `operator_id`, `username`, `role` | Auth login endpoint |
| `faq.matched` | `bot_id`, `user_telegram_id`, `question`, `answer`, `confidence` | FAQ engine |
| `plugin.activated` | `plugin_id`, `version` | PluginManager |
| `plugin.deactivated` | `plugin_id`, `reason` | PluginManager |

### 13.3 Integration Points

Add event emission to existing core code:

```python
# backend/app/bot/handlers/private.py
async def handle_private_message(message: Message, bot_manager, ...):
    # ... existing message processing ...

    # Emit event for plugins
    event_bus = get_plugin_manager().event_bus
    await event_bus.emit("message.received", {
        "bot_id": bot_id,
        "user_telegram_id": message.from_user.id,
        "chat_id": message.chat.id,
        "text": message.text,
        "message_id": message.message_id,
        "timestamp": message.date.isoformat(),
    })
```

---

## 14. Signature Verifier (signature_verifier.py)

Verifies the Ed25519 digital signature on plugin bundles to ensure they originate from ACP Market and have not been tampered with.

### 14.1 Implementation

```python
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature
import hashlib
import os
import logging

logger = logging.getLogger("acp.plugins.signature_verifier")

# Default ACP Market public key (built into the Panel binary)
DEFAULT_MARKET_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA... (Ed25519 public key)
-----END PUBLIC KEY-----"""


class BundleSignatureVerifier:
    """Verify Ed25519 signatures on plugin zip bundles.

    Every plugin bundle downloaded from ACP Market includes a .sig file
    containing the Ed25519 signature of the zip file's SHA-256 hash.

    The public key is built into the Panel and can be overridden via
    the ACP_MARKET_PUBLIC_KEY environment variable (for self-hosted markets).
    """

    def __init__(self):
        key_pem = os.environ.get("ACP_MARKET_PUBLIC_KEY", DEFAULT_MARKET_PUBLIC_KEY)
        self._public_key: Ed25519PublicKey = load_pem_public_key(
            key_pem.encode()
        )

    def verify(self, zip_path: Path, signature_path: Path | None = None) -> bool:
        """Verify the bundle signature.

        Args:
            zip_path: Path to the plugin zip file.
            signature_path: Path to the .sig file. If None, uses zip_path + ".sig".

        Returns:
            True if the signature is valid.

        Raises:
            PluginSignatureError: If signature is invalid or missing.
        """
        if signature_path is None:
            signature_path = zip_path.with_suffix(zip_path.suffix + ".sig")

        if not signature_path.exists():
            raise PluginSignatureError(f"Signature file not found: {signature_path}")

        # Read the zip file and compute SHA-256
        zip_hash = hashlib.sha256(zip_path.read_bytes()).digest()

        # Read the signature
        signature = signature_path.read_bytes()

        try:
            self._public_key.verify(signature, zip_hash)
            logger.info("Bundle signature verified: %s", zip_path.name)
            return True
        except InvalidSignature:
            raise PluginSignatureError(
                f"Invalid signature for bundle: {zip_path.name}"
            )

    def verify_integrity(self, plugin_path: Path, expected_hash: str) -> bool:
        """Verify the integrity of an extracted plugin directory.

        Compares a stored hash (from manifest) against the actual files.
        Used during startup to detect tampering of extracted files.
        """
        actual_hash = self._compute_directory_hash(plugin_path)
        return actual_hash == expected_hash

    @staticmethod
    def _compute_directory_hash(directory: Path) -> str:
        """Compute a deterministic hash of a directory's contents."""
        hasher = hashlib.sha256()
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                hasher.update(str(file_path.relative_to(directory)).encode())
                hasher.update(file_path.read_bytes())
        return hasher.hexdigest()
```

### 14.2 Skip Verification (Development Only)

For local development, signature verification can be skipped:

```env
PLUGIN_SKIP_SIGNATURE_CHECK=true   # NEVER use in production
```

---

## 15. Plugin Management API

FastAPI router providing administrative endpoints for plugin lifecycle operations.

### 15.1 Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/plugins` | admin+ | List all installed plugins |
| GET | `/api/v1/plugins/{id}` | admin+ | Get plugin detail with health status |
| POST | `/api/v1/plugins/install` | super_admin | Download from Market + install |
| POST | `/api/v1/plugins/{id}/activate` | super_admin | Activate an installed plugin |
| POST | `/api/v1/plugins/{id}/deactivate` | super_admin | Deactivate a running plugin |
| POST | `/api/v1/plugins/{id}/update` | super_admin | Update to a new version |
| POST | `/api/v1/plugins/{id}/rollback` | super_admin | Rollback to previous version |
| DELETE | `/api/v1/plugins/{id}` | super_admin | Uninstall (with optional table drop) |
| GET | `/api/v1/plugins/{id}/config` | admin+ | Get plugin configuration |
| PUT | `/api/v1/plugins/{id}/config` | super_admin | Update plugin configuration |
| GET | `/api/v1/plugins/{id}/secrets` | super_admin | List secret keys (no values) |
| PUT | `/api/v1/plugins/{id}/secrets/{key}` | super_admin | Set a secret value |
| DELETE | `/api/v1/plugins/{id}/secrets/{key}` | super_admin | Delete a secret |
| GET | `/api/v1/plugins/market` | admin+ | Browse ACP Market (proxy) |
| GET | `/api/v1/plugins/market/{id}` | admin+ | Get Market plugin details |
| POST | `/api/v1/plugins/market/checkout` | super_admin | Start purchase flow |

### 15.2 Response Schemas

```python
from pydantic import BaseModel
from datetime import datetime


class PluginInfo(BaseModel):
    plugin_id: str
    name: str
    version: str
    previous_version: str | None
    status: str  # installed | active | disabled | error | updating
    manifest: dict
    config: dict
    error_count: int
    last_error: str | None
    installed_at: datetime
    activated_at: datetime | None
    updated_at: datetime

    class Config:
        from_attributes = True


class PluginListResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: list[PluginInfo]


class PluginDetailResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: PluginInfo


class InstallRequest(BaseModel):
    plugin_id: str
    version: str
    market_url: str | None = None  # Override for self-hosted market


class UpdateRequest(BaseModel):
    version: str


class UninstallQuery(BaseModel):
    drop_tables: bool = False
```

### 15.3 Route Implementation (routes.py)

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_current_user, require_role
from app.plugins.loader import get_plugin_manager

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("", response_model=PluginListResponse)
async def list_plugins(user=Depends(require_role("admin"))):
    pm = get_plugin_manager()
    return {"code": 200, "message": "success", "data": pm.get_installed()}


@router.get("/{plugin_id}", response_model=PluginDetailResponse)
async def get_plugin(plugin_id: str, user=Depends(require_role("admin"))):
    pm = get_plugin_manager()
    plugin = pm.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(404, f"Plugin '{plugin_id}' not found")
    return {"code": 200, "message": "success", "data": plugin}


@router.post("/install", response_model=PluginDetailResponse)
async def install_plugin(req: InstallRequest, user=Depends(require_role("super_admin"))):
    pm = get_plugin_manager()
    # 1. Download from Market
    zip_path = await download_from_market(req.plugin_id, req.version, req.market_url)
    # 2. Install
    info = await pm.install(req.plugin_id, req.version, zip_path)
    return {"code": 200, "message": "success", "data": info}


@router.post("/{plugin_id}/activate")
async def activate_plugin(plugin_id: str, user=Depends(require_role("super_admin"))):
    pm = get_plugin_manager()
    await pm.activate(plugin_id)
    return {"code": 200, "message": "success", "data": None}


@router.post("/{plugin_id}/deactivate")
async def deactivate_plugin(plugin_id: str, user=Depends(require_role("super_admin"))):
    pm = get_plugin_manager()
    await pm.deactivate(plugin_id)
    return {"code": 200, "message": "success", "data": None}


@router.post("/{plugin_id}/update")
async def update_plugin(
    plugin_id: str, req: UpdateRequest, user=Depends(require_role("super_admin"))
):
    pm = get_plugin_manager()
    zip_path = await download_from_market(plugin_id, req.version)
    await pm.update(plugin_id, req.version, zip_path)
    return {"code": 200, "message": "success", "data": None}


@router.post("/{plugin_id}/rollback")
async def rollback_plugin(plugin_id: str, user=Depends(require_role("super_admin"))):
    pm = get_plugin_manager()
    await pm.rollback(plugin_id)
    return {"code": 200, "message": "success", "data": None}


@router.delete("/{plugin_id}")
async def uninstall_plugin(
    plugin_id: str,
    drop_tables: bool = Query(False),
    user=Depends(require_role("super_admin")),
):
    pm = get_plugin_manager()
    await pm.uninstall(plugin_id, drop_tables=drop_tables)
    return {"code": 200, "message": "success", "data": None}
```

---

## 16. Startup Sequence

### 16.1 Overview

```
Panel startup (main.py lifespan)
  │
  ├── 1. Initialize DB connection pool
  ├── 2. Initialize Redis connection
  ├── 3. Run core Alembic migrations
  ├── 4. Initialize BotManager
  ├── 5. Initialize PluginManager          <-- new
  │       │
  │       ├── 5a. Create sub-components (router_mount, handler_mount, etc.)
  │       ├── 5b. Include master_router in Dispatcher
  │       └── 5c. PluginManager.startup():
  │               │
  │               ├── i.   Query installed_plugins WHERE status='active'
  │               ├── ii.  Sort by dependency order (from manifest.dependencies)
  │               └── iii. For each plugin:
  │                        ├── Verify bundle integrity (hash check)
  │                        ├── Dynamic import Python modules
  │                        ├── Run pending Alembic migrations
  │                        ├── Register FastAPI router
  │                        ├── Register bot handler in HotSwappableRouter
  │                        ├── Mount frontend static files
  │                        ├── Create SDK + context
  │                        ├── Call plugin.setup(context)
  │                        └── On error: log, set status='error', continue
  │
  ├── 6. Start BotManager (begin polling)
  ├── 7. Start scheduler
  └── 8. Log startup summary (N plugins loaded, M errors)
```

### 16.2 lifespan Integration

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from app.plugins.loader import PluginManager, set_plugin_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...

    # Plugin system initialization
    plugin_manager = PluginManager(app, dispatcher, async_session_factory)
    set_plugin_manager(plugin_manager)

    # Include plugin master router in dispatcher
    dispatcher.include_router(plugin_manager.handler_mount.master_router)

    # Load active plugins
    results = await plugin_manager.startup()
    loaded = sum(1 for v in results.values() if v == "ok")
    errors = sum(1 for v in results.values() if v != "ok")
    logger.info("Plugin loader: %d loaded, %d errors", loaded, errors)

    # ... existing startup continuation (bot start, scheduler) ...

    yield

    # Shutdown
    await plugin_manager.shutdown()
    # ... existing shutdown code ...
```

---

## 17. File System Layout

### 17.1 Plugin Data Directory

```
/data/plugins/
├── movie-request/
│   ├── 1.0.0/                          # Previous version (retained for rollback)
│   │   ├── manifest.json
│   │   ├── manifest.json.sig           # Detached signature
│   │   ├── backend/
│   │   │   ├── __init__.py
│   │   │   ├── plugin.py              # Entry point (setup/teardown/get_router)
│   │   │   ├── routes.py             # FastAPI APIRouter
│   │   │   ├── handlers.py           # aiogram handlers
│   │   │   ├── models.py             # SQLAlchemy models (plg_{id}_* tables)
│   │   │   ├── schemas.py            # Pydantic schemas
│   │   │   ├── services/
│   │   │   │   └── tmdb.py           # Business logic
│   │   │   └── migrations/
│   │   │       ├── env.py
│   │   │       ├── script.py.mako
│   │   │       └── versions/
│   │   │           ├── 001_initial.py
│   │   │           └── 002_add_status.py
│   │   └── frontend/
│   │       ├── remoteEntry.js         # Module Federation entry
│   │       └── assets/
│   │           ├── MainPage-abc123.js
│   │           └── styles-def456.css
│   │
│   └── 1.1.0/                          # Current active version
│       ├── manifest.json
│       ├── backend/
│       └── frontend/
│
└── analytics-dashboard/
    └── 2.0.0/
        ├── manifest.json
        ├── backend/
        └── frontend/
```

### 17.2 Downloaded Bundle Cache

```
/data/plugins/.cache/
├── movie-request-1.0.0.zip
├── movie-request-1.0.0.zip.sig
├── movie-request-1.1.0.zip
└── movie-request-1.1.0.zip.sig
```

Downloaded bundles are cached to avoid re-downloading during rollback. Cache is pruned when a plugin is uninstalled.

---

## 18. Sequence Diagrams

### 18.1 Install + Activate Flow

```
Admin                Panel API              PluginManager         Market
  │                      │                       │                  │
  │  POST /plugins/install                       │                  │
  │─────────────────────►│                       │                  │
  │                      │  download(id, ver)    │                  │
  │                      │──────────────────────────────────────────►
  │                      │                       │    zip + sig     │
  │                      │◄──────────────────────────────────────────
  │                      │  install(id, ver, zip)│                  │
  │                      │──────────────────────►│                  │
  │                      │                       │ verify signature │
  │                      │                       │ extract zip      │
  │                      │                       │ validate manifest│
  │                      │                       │ INSERT DB row    │
  │                      │      PluginInfo       │                  │
  │   200 {status:       │◄──────────────────────│                  │
  │     "installed"}     │                       │                  │
  │◄─────────────────────│                       │                  │
  │                      │                       │                  │
  │  POST /plugins/{id}/activate                 │                  │
  │─────────────────────►│                       │                  │
  │                      │  activate(id)         │                  │
  │                      │──────────────────────►│                  │
  │                      │                       │ import module    │
  │                      │                       │ run migrations   │
  │                      │                       │ mount API router │
  │                      │                       │ mount bot router │
  │                      │                       │ mount static     │
  │                      │                       │ call setup()     │
  │                      │                       │ UPDATE status    │
  │                      │                       │ emit WS event    │
  │                      │      200 ok           │                  │
  │   200 ok             │◄──────────────────────│                  │
  │◄─────────────────────│                       │                  │
  │                      │                       │                  │
  │  [WebSocket: plugin_changed]                 │                  │
  │◄═══════════════════════════════════════════════                  │
  │  (frontend reloads sidebar + routes)         │                  │
```

### 18.2 Update with Rollback Flow

```
PluginManager              Old Plugin              New Plugin
     │                         │                        │
     │  deactivate(old)        │                        │
     │────────────────────────►│                        │
     │                         │ teardown()             │
     │                         │ remove routes          │
     │                         │                        │
     │  run migrations (old→new)                        │
     │──────────────────────────────────────────────────►│
     │                                                   │
     │  activate(new)                                    │
     │──────────────────────────────────────────────────►│
     │                         │                        │
     │  [If activation fails]  │                        │
     │                         │                        │
     │  reverse migrations (new→old)                    │
     │◄──────────────────────────────────────────────────│
     │                         │                        │
     │  reactivate(old)        │                        │
     │────────────────────────►│                        │
     │                         │ setup()                │
     │                         │ mount routes           │
     │                         │                        │
     │  set status='error'     │                        │
     │  log error details      │                        │
```

### 18.3 Message Processing with Plugins

```
Telegram                  Dispatcher             Core Router       Plugin Router
   │                          │                       │                  │
   │  Update (message)        │                       │                  │
   │─────────────────────────►│                       │                  │
   │                          │  route to handlers    │                  │
   │                          │──────────────────────►│                  │
   │                          │                       │                  │
   │                          │  (core processes msg) │                  │
   │                          │                       │                  │
   │                          │  event_bus.emit(      │                  │
   │                          │    "message.received") │                  │
   │                          │                       │──────────────────►
   │                          │                       │   (plugin handles│
   │                          │                       │    event async)  │
   │                          │                       │                  │
   │                          │  route to plugin      │                  │
   │                          │  master_router        │                  │
   │                          │──────────────────────────────────────────►
   │                          │                       │  (plugin may     │
   │                          │                       │   handle /movie  │
   │                          │                       │   command)       │
```

---

## 19. Error Handling

### 19.1 Exception Hierarchy

```python
# backend/app/plugins/exceptions.py

class PluginError(Exception):
    """Base exception for all plugin-related errors."""
    def __init__(self, plugin_id: str, message: str):
        self.plugin_id = plugin_id
        super().__init__(f"[Plugin:{plugin_id}] {message}")


class PluginNotFoundError(PluginError):
    """Plugin ID not found in installed_plugins table."""


class PluginSignatureError(PluginError):
    """Bundle signature verification failed."""


class PluginManifestError(PluginError):
    """Manifest is malformed or missing required fields."""


class PluginCompatError(PluginError):
    """Plugin is incompatible with this Panel version."""


class PluginConflictError(PluginError):
    """Plugin is already installed at this version."""


class PluginImportError(PluginError):
    """Python module import failed."""


class PluginSetupError(PluginError):
    """Plugin's setup() method raised an exception."""


class PluginPermissionError(PluginError):
    """Plugin tried to access a scope it hasn't declared."""


class PluginUpdateError(PluginError):
    """Plugin update failed (activation of new version failed)."""
```

### 19.2 Error Isolation Principles

1. **Plugin errors never crash the Panel.** All plugin code execution is wrapped in try/except.
2. **Plugin errors never affect other plugins.** Event bus handlers and API routes are isolated.
3. **Consecutive errors auto-disable.** After 5 consecutive unhandled errors, the plugin is deactivated with status `error`.
4. **Startup errors are logged, not fatal.** If a plugin fails to activate during Panel startup, it is set to `error` status and the Panel continues loading other plugins.
5. **Timeout protection.** Plugin setup(), teardown(), and event handlers have a 30-second timeout.

### 19.3 Logging

All plugin-related logs use the `acp.plugins.*` logger namespace:

```
acp.plugins.loader          - PluginManager lifecycle events
acp.plugins.handler_mount   - Bot router changes
acp.plugins.router_mount    - API router changes
acp.plugins.migration_runner - Migration execution
acp.plugins.health_monitor  - Error tracking, auto-disable
acp.plugins.event_bus       - Event emission, handler errors
acp.plugins.core_sdk        - Permission denials
acp.plugins.secret_store    - Key management (no values logged)
acp.plugin.{plugin_id}      - Per-plugin logger (passed to plugins via context)
```
