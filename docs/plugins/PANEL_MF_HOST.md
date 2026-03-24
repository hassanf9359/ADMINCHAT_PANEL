# ADMINCHAT Panel - Module Federation Host Specification

Frontend dynamic plugin loading via Module Federation, React lazy loading, and runtime route/sidebar injection.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Vite Configuration](#2-vite-configuration)
3. [Dynamic Remote Loading](#3-dynamic-remote-loading)
4. [PluginLoader Component](#4-pluginloader-component)
5. [Dynamic Sidebar](#5-dynamic-sidebar)
6. [Dynamic Routes](#6-dynamic-routes)
7. [Dynamic Settings Tabs](#7-dynamic-settings-tabs)
8. [Plugin Context and SDK](#8-plugin-context-and-sdk)
9. [Error Boundary](#9-error-boundary)
10. [WebSocket Integration](#10-websocket-integration)
11. [Icon Resolution](#11-icon-resolution)
12. [CSS and Theming](#12-css-and-theming)
13. [Build Considerations](#13-build-considerations)
14. [Directory Structure](#14-directory-structure)
15. [Sequence Diagrams](#15-sequence-diagrams)
16. [Type Definitions](#16-type-definitions)

---

## 1. Overview

The ADMINCHAT Panel frontend acts as a Module Federation **Host** application. It does not contain any plugin code at build time. Instead, it discovers active plugins from the backend API at runtime and dynamically loads their frontend bundles (remoteEntry.js) on demand.

Key design goals:

- **Zero-config for plugin consumers**: Installing a plugin on the backend automatically makes it available in the frontend. No rebuild required.
- **Lazy loading**: Plugin JavaScript is only fetched when the user navigates to a plugin's route.
- **Isolation**: Plugin errors are caught by error boundaries and do not crash the host application.
- **Shared dependencies**: React, React DOM, React Router, TanStack Query, and the plugin SDK are shared as singletons to avoid duplicate bundles.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser                                      │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   ADMINCHAT Host App                           │  │
│  │                                                               │  │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐ │  │
│  │  │ Sidebar  │  │  Core Pages  │  │  Plugin Routes          │ │  │
│  │  │          │  │              │  │                         │ │  │
│  │  │ - Dashboard  │ - Dashboard │  │  /p/movie-request/*    │ │  │
│  │  │ - Chat   │  │ - Chat      │  │  ┌───────────────────┐ │ │  │
│  │  │ - Bots   │  │ - Bots      │  │  │  PluginLoader     │ │ │  │
│  │  │ ─────────│  │ - Settings  │  │  │  ┌─────────────┐  │ │ │  │
│  │  │ - Movies │  │             │  │  │  │ Suspense    │  │ │ │  │
│  │  │   (plg)  │  │             │  │  │  │ ┌─────────┐ │  │ │ │  │
│  │  │ - Stats  │  │             │  │  │  │ │ Remote  │ │  │ │ │  │
│  │  │   (plg)  │  │             │  │  │  │ │ Module  │ │  │ │ │  │
│  │  │          │  │             │  │  │  │ └─────────┘ │  │ │ │  │
│  │  └──────────┘  └──────────────┘  │  │  └─────────────┘  │ │ │  │
│  │                                   │  └───────────────────┘ │ │  │
│  │                                   └─────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│     /plugins/movie-request/  Core API        WebSocket              │
│      remoteEntry.js         /api/v1/*        /ws/chat               │
│      assets/*.js                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Vite Configuration

### 2.1 Host Configuration

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import federation from '@module-federation/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    federation({
      name: 'adminchat_host',

      // No static remotes - all plugins are discovered and loaded at runtime
      remotes: {},

      // Shared dependencies - singleton ensures only one copy is loaded
      // across host and all plugin remotes
      shared: {
        'react': {
          singleton: true,
          requiredVersion: '^18.0.0',
        },
        'react-dom': {
          singleton: true,
          requiredVersion: '^18.0.0',
        },
        'react-router-dom': {
          singleton: true,
          requiredVersion: '^6.0.0',
        },
        '@tanstack/react-query': {
          singleton: true,
          requiredVersion: '^5.0.0',
        },
        'zustand': {
          singleton: true,
          requiredVersion: '^4.0.0 || ^5.0.0',
        },
        'lucide-react': {
          singleton: false,  // Tree-shakeable, no need for singleton
        },
        '@acp/plugin-sdk': {
          singleton: true,   // Plugin SDK must be a single instance
        },
      },
    }),
  ],

  // Dev server proxy for plugin static files
  server: {
    proxy: {
      '/plugins': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

### 2.2 Shared Dependency Strategy

| Dependency | Singleton | Reason |
|---|---|---|
| `react` | Yes | Multiple React instances cause hooks errors |
| `react-dom` | Yes | Must match React instance |
| `react-router-dom` | Yes | Router context must be shared |
| `@tanstack/react-query` | Yes | QueryClient must be shared |
| `zustand` | Yes | Stores must be accessible cross-module |
| `lucide-react` | No | Stateless icons, safe to duplicate |
| `@acp/plugin-sdk` | Yes | Plugin context and SDK must be single instance |

---

## 3. Dynamic Remote Loading

Since plugins are installed at runtime, we cannot declare static remotes in vite.config.ts. Instead, we use the `@module-federation/runtime` API to register and load remotes dynamically.

### 3.1 Remote Registration and Loading

```typescript
// frontend/src/plugins/loadRemote.ts
import { init, loadRemote as mfLoadRemote } from '@module-federation/runtime'

// Track registered remotes to avoid duplicate registration
const registeredRemotes = new Set<string>()

// Initialize Module Federation runtime (called once during app startup)
let initialized = false

function ensureInitialized() {
  if (initialized) return
  init({
    name: 'adminchat_host',
    remotes: [],  // Start with no remotes
  })
  initialized = true
}

/**
 * Register a plugin as a Module Federation remote and load a module from it.
 *
 * @param pluginId  - The plugin identifier (used as remote name)
 * @param moduleName - The exposed module path (e.g., "./pages/MainPage")
 * @param remoteUrl  - URL to the plugin's remoteEntry.js
 * @returns The loaded module's default export (typically a React component)
 */
export async function loadPluginModule<T = React.ComponentType>(
  pluginId: string,
  moduleName: string,
  remoteUrl: string,
): Promise<T> {
  ensureInitialized()

  // Register the remote if not already registered
  if (!registeredRemotes.has(pluginId)) {
    __FEDERATION__.__INSTANCES__[0].registerRemotes([
      {
        name: pluginId,
        entry: remoteUrl,
      },
    ])
    registeredRemotes.add(pluginId)
  }

  // Load the exposed module
  const module = await mfLoadRemote<{ default: T }>(
    `${pluginId}/${moduleName}`
  )

  if (!module) {
    throw new Error(
      `Failed to load module "${moduleName}" from plugin "${pluginId}"`
    )
  }

  return module.default
}

/**
 * Unregister a plugin remote (called when a plugin is deactivated).
 * Clears the cached remote so it can be re-registered if reactivated.
 */
export function unregisterPluginRemote(pluginId: string): void {
  registeredRemotes.delete(pluginId)
  // Note: Module Federation runtime doesn't support true unregistration,
  // but removing from our tracking set ensures re-registration on next load.
}
```

### 3.2 Remote Entry URL Convention

Plugin frontend bundles are served by the backend's `PluginStaticServer` at:

```
/plugins/{plugin_id}/remoteEntry.js
```

This maps to the file on disk at:

```
/data/plugins/{plugin_id}/{version}/frontend/remoteEntry.js
```

---

## 4. PluginLoader Component

The `PluginLoader` component wraps the dynamic remote loading with React Suspense, error boundaries, and the plugin SDK context.

### 4.1 Implementation

```tsx
// frontend/src/plugins/PluginLoader.tsx
import React, { Suspense, useMemo } from 'react'
import { loadPluginModule } from './loadRemote'
import { PluginErrorBoundary } from './PluginErrorBoundary'
import { PluginContextProvider, createPluginSDK } from './PluginContext'
import { PageLoader } from '@/components/ui/page-loader'

interface PluginLoaderProps {
  /** The plugin identifier */
  pluginId: string
  /** The module to load (e.g., "./pages/MainPage") */
  module: string
  /** Optional custom loading fallback */
  fallback?: React.ReactNode
  /** Optional props to pass to the loaded component */
  componentProps?: Record<string, unknown>
}

/**
 * Dynamically loads a plugin's React component via Module Federation.
 *
 * Wraps the loaded component with:
 * 1. PluginErrorBoundary - catches render errors without crashing the host
 * 2. Suspense - shows loading state while the remote module is fetched
 * 3. PluginContextProvider - provides the plugin SDK to child components
 */
export function PluginLoader({
  pluginId,
  module,
  fallback,
  componentProps = {},
}: PluginLoaderProps) {
  // Memoize the lazy component to avoid re-creating on every render
  const LazyComponent = useMemo(
    () =>
      React.lazy(() =>
        loadPluginModule(
          pluginId,
          module,
          `/plugins/${pluginId}/remoteEntry.js`,
        ).then((Component) => ({ default: Component as React.ComponentType }))
      ),
    [pluginId, module],
  )

  // Create SDK instance for this plugin
  const sdk = useMemo(() => createPluginSDK(pluginId), [pluginId])

  return (
    <PluginErrorBoundary pluginId={pluginId}>
      <Suspense fallback={fallback || <PluginLoadingFallback pluginId={pluginId} />}>
        <PluginContextProvider pluginId={pluginId} sdk={sdk}>
          <LazyComponent {...componentProps} />
        </PluginContextProvider>
      </Suspense>
    </PluginErrorBoundary>
  )
}

/**
 * Default loading fallback for plugins.
 * Shows a subtle loading indicator that matches the host design system.
 */
function PluginLoadingFallback({ pluginId }: { pluginId: string }) {
  return (
    <PageLoader
      message={`Loading plugin: ${pluginId}...`}
      className="min-h-[400px]"
    />
  )
}
```

### 4.2 Usage Example

```tsx
// In a route definition:
<Route
  path="/p/movie-request/*"
  element={
    <PluginLoader
      pluginId="movie-request"
      module="./pages/MainPage"
    />
  }
/>
```

---

## 5. Dynamic Sidebar

The sidebar merges core navigation items with plugin-provided items discovered from the API.

### 5.1 Plugin Navigation Item Schema (from manifest)

```json
{
  "frontend": {
    "sidebar": [
      {
        "path": "/p/movie-request",
        "label": "Movie Requests",
        "icon": "Film",
        "module": "./pages/MainPage",
        "minRole": "operator",
        "position": "after:chat",
        "badge": {
          "module": "./components/RequestBadge",
          "type": "count"
        }
      }
    ]
  }
}
```

### 5.2 Sidebar Integration

```tsx
// frontend/src/components/layout/Sidebar.tsx (modifications)
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'
import { getIcon } from '@/plugins/iconResolver'
import { mergeNavItems } from '@/plugins/navMerge'
import type { NavItem, PluginInfo, Role } from '@/types'

// Core navigation items (existing, unchanged)
const coreNavItems: NavItem[] = [
  { to: '/', icon: 'LayoutDashboard', label: 'Dashboard', minRole: 'operator' },
  { to: '/chat', icon: 'MessageSquare', label: 'Chat', minRole: 'operator' },
  { to: '/bots', icon: 'Bot', label: 'Bots', minRole: 'admin' },
  { to: '/users', icon: 'Users', label: 'Users', minRole: 'admin' },
  { to: '/faq', icon: 'HelpCircle', label: 'FAQ', minRole: 'admin' },
  { to: '/settings', icon: 'Settings', label: 'Settings', minRole: 'admin' },
]

function SidebarInner() {
  const { user } = useAuthStore()

  // Fetch active plugins to build dynamic navigation
  const { data: plugins } = useQuery<PluginInfo[]>({
    queryKey: ['installed-plugins'],
    queryFn: () => api.get('/plugins').then((r) => r.data.data),
    staleTime: 60_000,        // Cache for 1 minute
    refetchOnWindowFocus: false,
    // Only fetch if user is logged in
    enabled: !!user,
  })

  // Build plugin nav items from active plugins with sidebar config
  const pluginNavItems: NavItem[] = (plugins || [])
    .filter((p) => p.status === 'active' && p.manifest.frontend?.sidebar)
    .flatMap((p) =>
      p.manifest.frontend.sidebar.map(
        (item: PluginSidebarItem): NavItem => ({
          to: item.path,
          icon: item.icon,
          label: item.label,
          minRole: (item.minRole || 'operator') as Role,
          isPlugin: true,
          pluginId: p.plugin_id,
          position: item.position,  // e.g., "after:chat", "before:settings"
        }),
      ),
    )

  // Merge core items with plugin items, respecting position hints
  const allItems = mergeNavItems(coreNavItems, pluginNavItems)

  // Filter by user role
  const visibleItems = allItems.filter(
    (item) => hasMinRole(user?.role, item.minRole),
  )

  return (
    <nav className="flex flex-col gap-1 px-3">
      {visibleItems.map((item) => (
        <SidebarLink
          key={item.to}
          to={item.to}
          icon={item.icon}
          label={item.label}
          isPlugin={item.isPlugin}
        />
      ))}
    </nav>
  )
}
```

### 5.3 Navigation Item Merging

```typescript
// frontend/src/plugins/navMerge.ts
import type { NavItem } from '@/types'

/**
 * Merge core navigation items with plugin navigation items,
 * respecting position hints.
 *
 * Position hint format:
 *   - "after:{path}"   - Insert after the item with matching path
 *   - "before:{path}"  - Insert before the item with matching path
 *   - "top"            - Insert at the top of the list
 *   - "bottom"         - Insert at the bottom (default)
 *   - undefined        - Append to the bottom
 *
 * Items with invalid or unresolvable position hints are placed at the bottom.
 */
export function mergeNavItems(
  coreItems: NavItem[],
  pluginItems: NavItem[],
): NavItem[] {
  const result = [...coreItems]

  // Separate plugin items by position type
  const topItems: NavItem[] = []
  const bottomItems: NavItem[] = []
  const positionedItems: { item: NavItem; type: 'after' | 'before'; target: string }[] = []

  for (const item of pluginItems) {
    const pos = item.position

    if (!pos || pos === 'bottom') {
      bottomItems.push(item)
    } else if (pos === 'top') {
      topItems.push(item)
    } else if (pos.startsWith('after:')) {
      positionedItems.push({
        item,
        type: 'after',
        target: pos.slice(6),  // Remove "after:" prefix
      })
    } else if (pos.startsWith('before:')) {
      positionedItems.push({
        item,
        type: 'before',
        target: pos.slice(7),  // Remove "before:" prefix
      })
    } else {
      bottomItems.push(item)  // Unrecognized position, treat as bottom
    }
  }

  // Insert positioned items relative to their targets
  for (const { item, type, target } of positionedItems) {
    // Find the target by matching the last segment of the path
    const targetIndex = result.findIndex(
      (r) => r.to === `/${target}` || r.to === target,
    )

    if (targetIndex === -1) {
      bottomItems.push(item)  // Target not found, place at bottom
      continue
    }

    const insertIndex = type === 'after' ? targetIndex + 1 : targetIndex
    result.splice(insertIndex, 0, item)
  }

  // Add top and bottom items
  result.unshift(...topItems)
  result.push(...bottomItems)

  return result
}
```

### 5.4 Plugin Divider

When plugin items are present, a visual divider separates core items from plugin items:

```tsx
function SidebarInner() {
  // ... item building code ...

  const coreVisible = visibleItems.filter((i) => !i.isPlugin)
  const pluginVisible = visibleItems.filter((i) => i.isPlugin)

  return (
    <nav className="flex flex-col gap-1 px-3">
      {coreVisible.map((item) => (
        <SidebarLink key={item.to} {...item} />
      ))}

      {pluginVisible.length > 0 && (
        <>
          <div className="my-2 border-t border-[#1A1A1A]" />
          <span className="px-3 text-xs font-medium text-[#4a4a4a] uppercase tracking-wider">
            Plugins
          </span>
          {pluginVisible.map((item) => (
            <SidebarLink key={item.to} {...item} />
          ))}
        </>
      )}
    </nav>
  )
}
```

---

## 6. Dynamic Routes

Plugin page routes are injected into the React Router configuration dynamically based on the active plugins query.

### 6.1 Implementation

```tsx
// frontend/src/App.tsx (modifications)
import { Routes, Route, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout/AppLayout'
import { PluginLoader } from '@/plugins/PluginLoader'
import { api } from '@/lib/api'
import type { PluginInfo } from '@/types'

// Core page imports (unchanged)
import Dashboard from '@/pages/Dashboard'
import Chat from '@/pages/Chat'
import Bots from '@/pages/Bots'
import Users from '@/pages/Users'
import FAQ from '@/pages/FAQ'
import Settings from '@/pages/Settings'

function AppRoutes() {
  const { data: plugins } = useQuery<PluginInfo[]>({
    queryKey: ['installed-plugins'],
    queryFn: () => api.get('/plugins').then((r) => r.data.data),
    staleTime: 60_000,
  })

  // Build plugin route configs from active plugins
  const pluginRoutes = (plugins || [])
    .filter((p) => p.status === 'active' && p.manifest.frontend?.sidebar)
    .flatMap((p) =>
      p.manifest.frontend.sidebar.map(
        (item: PluginSidebarItem) => ({
          path: item.path,
          pluginId: p.plugin_id,
          module: item.module || './pages/MainPage',
          minRole: item.minRole || 'operator',
        }),
      ),
    )

  return (
    <Routes>
      {/* Core routes (unchanged) */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/chat/:id" element={<Chat />} />
        <Route path="/bots" element={<Bots />} />
        <Route path="/users" element={<Users />} />
        <Route path="/faq" element={<FAQ />} />
        <Route path="/settings" element={<Settings />} />

        {/* Dynamic plugin routes */}
        {pluginRoutes.map((route) => (
          <Route
            key={route.path}
            path={`${route.path}/*`}
            element={
              <RoleGuard minRole={route.minRole}>
                <PluginLoader
                  pluginId={route.pluginId}
                  module={route.module}
                />
              </RoleGuard>
            }
          />
        ))}

        {/* Catch-all: redirect unknown paths to dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
```

### 6.2 Plugin Sub-Routing

Plugins receive `/*` wildcard routes, meaning a plugin can define its own internal routing:

```tsx
// Inside a plugin's MainPage component:
import { Routes, Route } from 'react-router-dom'

export default function MainPage() {
  return (
    <Routes>
      <Route index element={<RequestList />} />
      <Route path="new" element={<NewRequest />} />
      <Route path=":id" element={<RequestDetail />} />
    </Routes>
  )
}
```

The plugin navigates using relative paths. For example, if the plugin is mounted at `/p/movie-request`, then:
- `/p/movie-request` renders `<RequestList />`
- `/p/movie-request/new` renders `<NewRequest />`
- `/p/movie-request/123` renders `<RequestDetail />`

### 6.3 RoleGuard Wrapper

```tsx
// frontend/src/components/auth/RoleGuard.tsx
import { useAuthStore } from '@/stores/authStore'
import { hasMinRole } from '@/utils/roles'

interface RoleGuardProps {
  minRole: string
  children: React.ReactNode
}

export function RoleGuard({ minRole, children }: RoleGuardProps) {
  const { user } = useAuthStore()

  if (!user || !hasMinRole(user.role, minRole)) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-[#6a6a6a] text-sm">
          You do not have permission to access this plugin.
        </p>
      </div>
    )
  }

  return <>{children}</>
}
```

---

## 7. Dynamic Settings Tabs

Plugins can contribute tabs to the Settings page, allowing configuration UIs to be rendered alongside core settings.

### 7.1 Manifest Schema

```json
{
  "frontend": {
    "settings_tabs": [
      {
        "key": "config",
        "label": "Movie Request Settings",
        "module": "./pages/SettingsTab",
        "icon": "Film",
        "minRole": "admin"
      }
    ]
  }
}
```

### 7.2 Settings Page Integration

```tsx
// frontend/src/pages/Settings.tsx (modifications)
import { useQuery } from '@tanstack/react-query'
import { PluginLoader } from '@/plugins/PluginLoader'
import { getIcon } from '@/plugins/iconResolver'

// Core settings tabs (unchanged)
const CORE_TABS = [
  { key: 'general', label: 'General', icon: 'Settings' },
  { key: 'notifications', label: 'Notifications', icon: 'Bell' },
  { key: 'appearance', label: 'Appearance', icon: 'Palette' },
  { key: 'security', label: 'Security', icon: 'Shield' },
]

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general')

  const { data: plugins } = useQuery<PluginInfo[]>({
    queryKey: ['installed-plugins'],
    queryFn: () => api.get('/plugins').then((r) => r.data.data),
    staleTime: 60_000,
  })

  // Build plugin settings tabs
  const pluginTabs = (plugins || [])
    .filter((p) => p.status === 'active' && p.manifest.frontend?.settings_tabs)
    .flatMap((p) =>
      p.manifest.frontend.settings_tabs.map((tab: PluginSettingsTab) => ({
        key: `plg_${p.plugin_id}_${tab.key}`,
        label: tab.label,
        icon: tab.icon || 'Puzzle',
        pluginId: p.plugin_id,
        module: tab.module,
        minRole: tab.minRole || 'admin',
        isPlugin: true,
      })),
    )

  // Merge: core tabs first, then a divider concept, then plugin tabs
  const allTabs = [...CORE_TABS, ...pluginTabs]

  // Find the active tab config
  const activeTabConfig = allTabs.find((t) => t.key === activeTab)

  return (
    <div className="flex h-full">
      {/* Tab sidebar */}
      <div className="w-56 border-r border-[#2f2f2f] bg-[#080808] p-4">
        <h3 className="text-sm font-medium text-[#8a8a8a] mb-3">Settings</h3>
        {CORE_TABS.map((tab) => (
          <TabButton
            key={tab.key}
            tab={tab}
            active={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
          />
        ))}

        {pluginTabs.length > 0 && (
          <>
            <div className="my-3 border-t border-[#1A1A1A]" />
            <h3 className="text-sm font-medium text-[#4a4a4a] mb-3">Plugins</h3>
            {pluginTabs.map((tab) => (
              <TabButton
                key={tab.key}
                tab={tab}
                active={activeTab === tab.key}
                onClick={() => setActiveTab(tab.key)}
              />
            ))}
          </>
        )}
      </div>

      {/* Tab content */}
      <div className="flex-1 p-6 overflow-y-auto">
        {activeTabConfig?.isPlugin ? (
          <PluginLoader
            pluginId={activeTabConfig.pluginId}
            module={activeTabConfig.module}
          />
        ) : (
          <CoreSettingsContent tab={activeTab} />
        )}
      </div>
    </div>
  )
}
```

---

## 8. Plugin Context and SDK

Every plugin component receives a `PluginSDK` via React context, providing scoped API access and core data access.

### 8.1 Plugin SDK Interface

```typescript
// frontend/src/plugins/PluginContext.tsx
import { createContext, useContext, type ReactNode } from 'react'
import { api } from '@/lib/api'
import type { AxiosResponse } from 'axios'

/**
 * SDK interface provided to plugin components via context.
 */
export interface PluginSDK {
  /** The plugin identifier */
  pluginId: string

  /**
   * Scoped API client. All requests are prefixed with /api/v1/p/{pluginId}.
   * Authentication is handled automatically via the host's JWT token.
   */
  api: {
    get: <T = any>(path: string, params?: Record<string, any>) => Promise<AxiosResponse<T>>
    post: <T = any>(path: string, data?: any) => Promise<AxiosResponse<T>>
    put: <T = any>(path: string, data?: any) => Promise<AxiosResponse<T>>
    patch: <T = any>(path: string, data?: any) => Promise<AxiosResponse<T>>
    delete: <T = any>(path: string) => Promise<AxiosResponse<T>>
  }

  /**
   * Access to core Panel data (restricted by plugin permissions).
   * Calls go through /api/v1/plugins/{pluginId}/core/* proxy.
   */
  coreApi: CoreAPIProxy

  /**
   * Navigate within the plugin's route namespace.
   * Equivalent to useNavigate() but prefixed with the plugin's base path.
   */
  navigate: (path: string) => void

  /**
   * Show a toast notification in the host UI.
   */
  toast: {
    success: (message: string) => void
    error: (message: string) => void
    info: (message: string) => void
    warning: (message: string) => void
  }
}

// ── Context ──────────────────────────────────────────────────────

const PluginCtx = createContext<PluginSDK | null>(null)

interface PluginContextProviderProps {
  pluginId: string
  sdk: PluginSDK
  children: ReactNode
}

export function PluginContextProvider({
  pluginId,
  sdk,
  children,
}: PluginContextProviderProps) {
  return <PluginCtx.Provider value={sdk}>{children}</PluginCtx.Provider>
}

/**
 * Hook for plugin components to access the SDK.
 * Must be used within a <PluginLoader />.
 */
export function usePluginSDK(): PluginSDK {
  const sdk = useContext(PluginCtx)
  if (!sdk) {
    throw new Error(
      'usePluginSDK() must be used within a PluginLoader. ' +
      'This is a plugin component rendered outside its expected context.',
    )
  }
  return sdk
}
```

### 8.2 SDK Factory

```typescript
// frontend/src/plugins/PluginContext.tsx (continued)
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'  // or your toast library

/**
 * Create a PluginSDK instance for a specific plugin.
 * Called once per PluginLoader mount.
 */
export function createPluginSDK(pluginId: string): PluginSDK {
  const prefix = `/api/v1/p/${pluginId}`

  return {
    pluginId,

    api: {
      get: (path, params) => api.get(`${prefix}${path}`, { params }),
      post: (path, data) => api.post(`${prefix}${path}`, data),
      put: (path, data) => api.put(`${prefix}${path}`, data),
      patch: (path, data) => api.patch(`${prefix}${path}`, data),
      delete: (path) => api.delete(`${prefix}${path}`),
    },

    coreApi: new CoreAPIProxy(pluginId),

    navigate: (path: string) => {
      // Plugin base path is derived from the first sidebar item
      // or defaults to /p/{pluginId}
      window.history.pushState(null, '', `/p/${pluginId}${path}`)
      window.dispatchEvent(new PopStateEvent('popstate'))
    },

    toast: {
      success: (message) => toast.success(message),
      error: (message) => toast.error(message),
      info: (message) => toast.info(message),
      warning: (message) => toast.warning(message),
    },
  }
}
```

### 8.3 CoreAPIProxy

Provides restricted access to core data. The backend validates permissions based on manifest scopes.

```typescript
// frontend/src/plugins/CoreAPIProxy.ts
import { api } from '@/lib/api'

/**
 * Proxy for accessing core Panel data from plugins.
 *
 * All requests go through /api/v1/p/{pluginId}/core/* which the backend
 * validates against the plugin's declared core_api_scopes.
 */
export class CoreAPIProxy {
  private prefix: string

  constructor(pluginId: string) {
    this.prefix = `/api/v1/p/${pluginId}/core`
  }

  /** Get users (requires users:read scope) */
  async getUsers(params?: { page?: number; page_size?: number }) {
    return api.get(`${this.prefix}/users`, { params })
  }

  /** Get a specific user (requires users:read scope) */
  async getUser(userId: number) {
    return api.get(`${this.prefix}/users/${userId}`)
  }

  /** Get active bots (requires bots:read scope) */
  async getBots() {
    return api.get(`${this.prefix}/bots`)
  }

  /** Get messages for a conversation (requires messages:read scope) */
  async getMessages(userTelegramId: number, params?: { limit?: number }) {
    return api.get(`${this.prefix}/messages/${userTelegramId}`, { params })
  }

  /** Get groups (requires groups:read scope) */
  async getGroups() {
    return api.get(`${this.prefix}/groups`)
  }

  /** Get FAQ entries (requires faq:read scope) */
  async getFaqEntries(params?: { page?: number }) {
    return api.get(`${this.prefix}/faq`, { params })
  }

  /** Get Panel settings (requires settings:read scope) */
  async getSettings() {
    return api.get(`${this.prefix}/settings`)
  }
}
```

---

## 9. Error Boundary

Catches rendering errors from plugin components without crashing the host application.

### 9.1 Implementation

```tsx
// frontend/src/plugins/PluginErrorBoundary.tsx
import React, { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'

interface Props {
  pluginId: string
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

/**
 * Error boundary that catches rendering errors from plugin components.
 *
 * On error:
 * 1. Renders a fallback UI (not a full page crash)
 * 2. Reports the error to the backend PluginHealthMonitor
 * 3. Shows a retry button to attempt re-rendering
 * 4. Logs error details to the browser console
 */
export class PluginErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo })

    // Log to console with plugin context
    console.error(
      `[Plugin:${this.props.pluginId}] Render error:`,
      error,
      errorInfo,
    )

    // Report to backend health monitor (fire and forget)
    api.post(`/plugins/${this.props.pluginId}/error`, {
      type: 'render_error',
      message: error.message,
      stack: error.stack?.substring(0, 2000),
      componentStack: errorInfo.componentStack?.substring(0, 2000),
    }).catch(() => {
      // Silently ignore reporting errors
    })
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
          <div className="flex flex-col items-center max-w-md text-center">
            <div className="flex items-center justify-center w-12 h-12 rounded-full bg-[#FF4444]/10 mb-4">
              <AlertTriangle className="w-6 h-6 text-[#FF4444]" />
            </div>

            <h3 className="text-lg font-medium text-white mb-2 font-[Space_Grotesk]">
              Plugin Error
            </h3>

            <p className="text-sm text-[#8a8a8a] mb-1">
              The plugin <span className="text-[#00D9FF] font-mono text-xs">{this.props.pluginId}</span> encountered an error and could not render.
            </p>

            <p className="text-xs text-[#4a4a4a] mb-6 font-mono">
              {this.state.error?.message}
            </p>

            <button
              onClick={this.handleRetry}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#141414] border border-[#2f2f2f] rounded-lg hover:bg-[#1a1a1a] transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>

            <p className="text-xs text-[#4a4a4a] mt-4">
              If this error persists, try deactivating and reactivating the plugin.
            </p>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
```

---

## 10. WebSocket Integration

Real-time plugin state changes are communicated to the frontend via WebSocket, enabling instant sidebar/route updates without a page refresh.

### 10.1 Event Flow

```
Backend: PluginManager.activate("movie-request")
  │
  ├── ... activation steps ...
  │
  └── Broadcast WebSocket message:
      {
        "type": "plugin_changed",
        "data": {
          "action": "activated",
          "plugin_id": "movie-request",
          "name": "Movie Request",
          "version": "1.0.0"
        }
      }
      │
      ▼
Frontend: WebSocket handler receives message
  │
  ├── Invalidate TanStack Query: ['installed-plugins']
  │
  ├── React re-renders:
  │   ├── Sidebar adds "Movie Requests" nav item
  │   └── Router adds /p/movie-request/* route
  │
  └── User can immediately navigate to the new plugin
      (remoteEntry.js is fetched on first navigation)
```

### 10.2 Frontend WebSocket Handler

```typescript
// frontend/src/hooks/useWebSocket.ts (additions)
import { useQueryClient } from '@tanstack/react-query'

// Inside the existing WebSocket message handler:
function handleMessage(event: MessageEvent) {
  const message = JSON.parse(event.data)

  switch (message.type) {
    // ... existing handlers ...

    case 'plugin_changed':
      handlePluginChanged(message.data)
      break
  }
}

function handlePluginChanged(data: {
  action: string
  plugin_id: string
  name?: string
  version?: string
}) {
  const queryClient = useQueryClient()

  // Invalidate the installed-plugins query to trigger re-fetch
  queryClient.invalidateQueries({ queryKey: ['installed-plugins'] })

  // If a plugin was deactivated or uninstalled, also unregister the remote
  if (data.action === 'deactivated' || data.action === 'uninstalled') {
    unregisterPluginRemote(data.plugin_id)
  }

  // Show a toast notification
  const actionLabels: Record<string, string> = {
    activated: 'activated',
    deactivated: 'deactivated',
    updated: 'updated',
    uninstalled: 'uninstalled',
    error: 'encountered an error',
  }
  const label = actionLabels[data.action] || data.action
  toast.info(`Plugin "${data.name || data.plugin_id}" ${label}`)
}
```

### 10.3 Backend WebSocket Emission

```python
# In PluginManager, after state changes:
async def _emit_plugin_changed(self, action: str, plugin_id: str, name: str, version: str):
    """Broadcast plugin state change to all connected WebSocket clients."""
    from app.websocket.manager import ws_manager

    await ws_manager.broadcast({
        "type": "plugin_changed",
        "data": {
            "action": action,       # activated | deactivated | updated | uninstalled | error
            "plugin_id": plugin_id,
            "name": name,
            "version": version,
        },
    })
```

---

## 11. Icon Resolution

Plugins specify Lucide icon names as strings in their manifest. The host resolves these to React components at render time.

### 11.1 Implementation

```tsx
// frontend/src/plugins/iconResolver.tsx
import * as LucideIcons from 'lucide-react'
import type { LucideProps } from 'lucide-react'

// Type for lucide icon component names
type IconName = keyof typeof LucideIcons

// Cache for resolved icons (string name -> component)
const iconCache = new Map<string, React.ComponentType<LucideProps>>()

/**
 * Resolve a Lucide icon name string to a React component.
 *
 * @param name - PascalCase icon name (e.g., "Film", "LayoutDashboard")
 * @returns The Lucide icon component, or Puzzle as fallback
 */
export function resolveIcon(name: string): React.ComponentType<LucideProps> {
  // Check cache first
  if (iconCache.has(name)) {
    return iconCache.get(name)!
  }

  const Icon = (LucideIcons as Record<string, any>)[name]

  if (Icon && typeof Icon === 'function') {
    iconCache.set(name, Icon)
    return Icon
  }

  // Fallback to Puzzle icon for unrecognized names
  console.warn(`[PluginIcons] Unknown icon name: "${name}", using Puzzle fallback`)
  return LucideIcons.Puzzle
}

/**
 * Render a Lucide icon from a string name.
 *
 * @param name - PascalCase icon name
 * @param size - Icon size in pixels (default: 20)
 * @param className - Additional CSS classes
 */
export function getIcon(
  name: string,
  size: number = 20,
  className?: string,
): React.ReactNode {
  const Icon = resolveIcon(name)
  return <Icon size={size} className={className} />
}
```

### 11.2 Usage in Sidebar

```tsx
// In SidebarLink component:
function SidebarLink({ to, icon, label, isPlugin }: NavItem) {
  return (
    <NavLink to={to} className={/* ... */}>
      {getIcon(icon, 20)}
      <span>{label}</span>
    </NavLink>
  )
}
```

---

## 12. CSS and Theming

### 12.1 CSS Variable Contract

The host application exposes CSS custom properties that plugins use for consistent theming. These variables are defined on `:root` and correspond to the design system.

```css
/* frontend/src/styles/plugin-vars.css */
:root {
  /* Backgrounds */
  --acp-bg-page: #0C0C0C;
  --acp-bg-sidebar: #080808;
  --acp-bg-card: #0A0A0A;
  --acp-bg-elevated: #141414;
  --acp-bg-hover: #1A1A1A;

  /* Primary accent */
  --acp-primary: #00D9FF;
  --acp-primary-hover: #00C4E6;
  --acp-primary-muted: rgba(0, 217, 255, 0.1);

  /* Status colors */
  --acp-success: #059669;
  --acp-warning: #FF8800;
  --acp-error: #FF4444;
  --acp-purple: #8B5CF6;

  /* Text */
  --acp-text-primary: #FFFFFF;
  --acp-text-secondary: #8a8a8a;
  --acp-text-muted: #6a6a6a;
  --acp-text-placeholder: #4a4a4a;

  /* Borders */
  --acp-border: #2f2f2f;
  --acp-border-subtle: #1A1A1A;

  /* Typography */
  --acp-font-heading: 'Space Grotesk', sans-serif;
  --acp-font-body: 'Inter', sans-serif;
  --acp-font-mono: 'JetBrains Mono', monospace;

  /* Spacing / Radius */
  --acp-radius-sm: 4px;
  --acp-radius-md: 6px;
  --acp-radius-lg: 10px;
}
```

### 12.2 Plugin CSS Strategy

Plugins are built with their own Tailwind configuration that references the host's CSS variables. The `@acp/plugin-sdk` package provides a Tailwind preset:

```typescript
// In plugin's tailwind.config.ts:
import acpPreset from '@acp/plugin-sdk/tailwind-preset'

export default {
  presets: [acpPreset],
  content: ['./src/**/*.{ts,tsx}'],
}
```

The preset maps the `--acp-*` variables to Tailwind utilities:

```typescript
// @acp/plugin-sdk/tailwind-preset.ts
export default {
  theme: {
    extend: {
      colors: {
        'acp-primary': 'var(--acp-primary)',
        'acp-success': 'var(--acp-success)',
        'acp-warning': 'var(--acp-warning)',
        'acp-error': 'var(--acp-error)',
        'acp-bg-page': 'var(--acp-bg-page)',
        'acp-bg-card': 'var(--acp-bg-card)',
        'acp-bg-elevated': 'var(--acp-bg-elevated)',
        'acp-text': 'var(--acp-text-primary)',
        'acp-text-secondary': 'var(--acp-text-secondary)',
        'acp-text-muted': 'var(--acp-text-muted)',
        'acp-border': 'var(--acp-border)',
      },
      fontFamily: {
        heading: 'var(--acp-font-heading)',
        body: 'var(--acp-font-body)',
        mono: 'var(--acp-font-mono)',
      },
      borderRadius: {
        'acp-sm': 'var(--acp-radius-sm)',
        'acp-md': 'var(--acp-radius-md)',
        'acp-lg': 'var(--acp-radius-lg)',
      },
    },
  },
}
```

### 12.3 CSS Isolation

- Plugin CSS is built as part of the plugin's Vite build and bundled into the MF chunks.
- Each plugin's CSS is loaded when the plugin's remoteEntry.js is executed.
- No CSS-in-JS conflicts because both host and plugins use Tailwind with consistent configuration.
- Plugin-specific CSS classes are naturally scoped by chunk isolation.

---

## 13. Build Considerations

### 13.1 Host Build

- The Panel's Vite build (`npm run build`) does NOT include any plugin code.
- The output bundle size is unaffected by the number of installed plugins.
- Module Federation runtime (~15KB gzipped) is the only addition to the host bundle.

### 13.2 Plugin Builds

- Each plugin is built independently using its own Vite configuration.
- The plugin build produces a `remoteEntry.js` and associated chunks in `frontend/dist/`.
- These files are packaged into the plugin's zip bundle and served as static files by the backend.

### 13.3 Plugin Vite Configuration

```typescript
// Plugin's vite.config.ts (inside the plugin's repo, NOT the Panel)
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import federation from '@module-federation/vite'

export default defineConfig({
  plugins: [
    react(),
    federation({
      name: 'movie_request',  // Must match manifest.id (with underscores)
      filename: 'remoteEntry.js',

      // Modules exposed to the host
      exposes: {
        './pages/MainPage': './src/pages/MainPage.tsx',
        './pages/SettingsTab': './src/pages/SettingsTab.tsx',
        './components/RequestBadge': './src/components/RequestBadge.tsx',
      },

      // Shared dependencies (consumed from host, not bundled)
      shared: {
        'react': { singleton: true, requiredVersion: '^18.0.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
        'react-router-dom': { singleton: true, requiredVersion: '^6.0.0' },
        '@tanstack/react-query': { singleton: true, requiredVersion: '^5.0.0' },
        'lucide-react': { singleton: false },
        '@acp/plugin-sdk': { singleton: true },
      },
    }),
  ],

  build: {
    target: 'esnext',
    outDir: 'dist/frontend',
  },
})
```

### 13.4 Development Mode

During development, the Panel's Vite dev server proxies plugin static file requests to the backend:

```typescript
// In vite.config.ts server.proxy (already shown in section 2)
server: {
  proxy: {
    '/plugins': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

Plugin developers can run their plugin's Vite dev server separately and point the Panel to it for hot-reloading during development.

---

## 14. Directory Structure

### 14.1 New Frontend Files

```
frontend/src/plugins/
├── loadRemote.ts              # Dynamic MF remote registration + loading
├── PluginLoader.tsx           # Main component for loading plugin UIs
├── PluginContext.tsx           # PluginSDK context + provider + hook
├── PluginErrorBoundary.tsx    # Error boundary for plugin components
├── CoreAPIProxy.ts            # Restricted core data access proxy
├── iconResolver.tsx           # Lucide icon string → component resolver
├── navMerge.ts                # Merge core + plugin nav items with positioning
└── types.ts                   # Plugin-related TypeScript types
```

### 14.2 Modified Frontend Files

```
frontend/
├── vite.config.ts             # Add @module-federation/vite plugin
├── src/
│   ├── App.tsx                # Add dynamic plugin routes
│   ├── styles/
│   │   └── plugin-vars.css    # CSS custom properties for plugins (new)
│   ├── components/layout/
│   │   └── Sidebar.tsx        # Add dynamic plugin nav items
│   ├── pages/
│   │   └── Settings.tsx       # Add dynamic plugin settings tabs
│   └── hooks/
│       └── useWebSocket.ts    # Add plugin_changed handler
```

---

## 15. Sequence Diagrams

### 15.1 First Navigation to a Plugin Page

```
User clicks "Movie Requests" in sidebar
  │
  ▼
React Router matches /p/movie-request/*
  │
  ▼
Renders <PluginLoader pluginId="movie-request" module="./pages/MainPage" />
  │
  ├── PluginErrorBoundary wraps children
  ├── Suspense shows <PluginLoadingFallback />
  │
  ▼
loadPluginModule("movie-request", "./pages/MainPage", "/plugins/movie-request/remoteEntry.js")
  │
  ├── Register remote (first time only)
  │     registerRemote({ name: "movie-request", entry: "/plugins/movie-request/remoteEntry.js" })
  │
  ├── Fetch remoteEntry.js ─────────────────────────────► Backend static server
  │                                                        /data/plugins/movie-request/1.0.0/frontend/
  │   ◄──────────────────────────────────────────────────── remoteEntry.js
  │
  ├── Resolve shared dependencies (react, react-dom, etc.)
  │   Uses host's copies (singleton)
  │
  ├── Fetch MainPage chunk ─────────────────────────────► Backend static server
  │   ◄──────────────────────────────────────────────────── MainPage-abc123.js
  │
  └── Return MainPage component
      │
      ▼
Suspense resolves
  │
  ▼
<PluginContextProvider sdk={...}>
  <MainPage />    ← Plugin component renders within the host layout
</PluginContextProvider>
```

### 15.2 Plugin Activated via WebSocket (Live Update)

```
Admin activates "analytics" plugin via Settings UI
  │
  ├── POST /api/v1/plugins/analytics/activate
  │
  ▼
Backend: PluginManager.activate("analytics")
  │
  ├── ... backend activation steps ...
  │
  └── WebSocket broadcast: { type: "plugin_changed", data: { action: "activated", ... } }
      │
      ▼
Frontend: WebSocket handler
  │
  ├── queryClient.invalidateQueries(['installed-plugins'])
  │
  ▼
TanStack Query refetches GET /api/v1/plugins
  │
  ├── Response includes "analytics" with status="active"
  │
  ▼
React re-renders:
  ├── Sidebar: New "Analytics" nav item appears (with position hint)
  ├── Router: New /p/analytics/* route is registered
  └── Settings: New "Analytics Settings" tab appears (if configured)

User sees the new sidebar item immediately without page refresh.
remoteEntry.js is NOT fetched yet (lazy loaded on first navigation).
```

### 15.3 Plugin Error During Render

```
User navigates to /p/broken-plugin
  │
  ▼
PluginLoader loads and renders BrokenPlugin's MainPage
  │
  ▼
MainPage throws during render
  │
  ▼
PluginErrorBoundary.componentDidCatch(error, errorInfo)
  │
  ├── console.error("[Plugin:broken-plugin] Render error:", ...)
  │
  ├── POST /api/v1/plugins/broken-plugin/error  ──────► Backend health monitor
  │   { type: "render_error", message: "...", stack: "..." }
  │
  └── Render fallback UI:
      ┌──────────────────────────────────────────┐
      │         ⚠ Plugin Error                   │
      │                                          │
      │  The plugin "broken-plugin" encountered  │
      │  an error and could not render.          │
      │                                          │
      │  TypeError: Cannot read properties...    │
      │                                          │
      │         [ Try Again ]                    │
      │                                          │
      │  If this error persists, try             │
      │  deactivating and reactivating.          │
      └──────────────────────────────────────────┘

Host app remains fully functional.
Other plugins are unaffected.
```

---

## 16. Type Definitions

### 16.1 Plugin Types

```typescript
// frontend/src/plugins/types.ts

/** Plugin info as returned by GET /api/v1/plugins */
export interface PluginInfo {
  plugin_id: string
  name: string
  version: string
  previous_version: string | null
  status: 'installed' | 'active' | 'disabled' | 'error' | 'updating'
  manifest: PluginManifest
  config: Record<string, unknown>
  error_count: number
  last_error: string | null
  installed_at: string
  activated_at: string | null
  updated_at: string
}

/** Plugin manifest (from manifest.json) */
export interface PluginManifest {
  id: string
  name: string
  version: string
  description: string
  author: string
  license: string
  min_panel_version: string

  backend?: {
    entry_point: string
    has_bot_handler: boolean
    bot_handler_priority?: number
  }

  frontend?: {
    sidebar?: PluginSidebarItem[]
    settings_tabs?: PluginSettingsTab[]
  }

  permissions?: {
    core_api_scopes?: string[]
    bot_scopes?: string[]
  }

  dependencies?: string[]  // Other plugin IDs this plugin depends on
}

/** Sidebar navigation item from plugin manifest */
export interface PluginSidebarItem {
  path: string              // e.g., "/p/movie-request"
  label: string             // e.g., "Movie Requests"
  icon: string              // Lucide icon name, e.g., "Film"
  module: string            // MF exposed module, e.g., "./pages/MainPage"
  minRole?: string          // Minimum role required, default: "operator"
  position?: string         // Position hint, e.g., "after:chat"
  badge?: {
    module: string          // MF module exposing a badge component
    type: 'count' | 'dot'
  }
}

/** Settings tab from plugin manifest */
export interface PluginSettingsTab {
  key: string               // Unique key within the plugin
  label: string             // Tab label
  module: string            // MF exposed module for the tab content
  icon?: string             // Lucide icon name
  minRole?: string          // Minimum role required
}

/** Extended NavItem type for sidebar rendering */
export interface NavItem {
  to: string
  icon: string
  label: string
  minRole: string
  isPlugin?: boolean
  pluginId?: string
  position?: string
}

/** WebSocket plugin_changed event data */
export interface PluginChangedEvent {
  action: 'activated' | 'deactivated' | 'updated' | 'uninstalled' | 'error'
  plugin_id: string
  name: string
  version: string
}
```

### 16.2 Package Dependencies

New dependencies required for the host frontend:

```json
{
  "dependencies": {
    "@module-federation/vite": "^0.8.0",
    "@module-federation/runtime": "^0.8.0"
  }
}
```

These are added to `frontend/package.json`. No other new dependencies are required, as the host already includes React, React Router, TanStack Query, Lucide, and other shared libraries.
