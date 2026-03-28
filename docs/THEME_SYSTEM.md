# ADMINCHAT Panel — Theme System Design

> 开发文档：多主题支持 + 毛玻璃效果 + 流动渐变

## 目标

1. **保留当前暗色主题**（Dark）作为默认
2. **新增明亮主题**（Light）— 白色底 + 宝蓝色字 + 毛玻璃 + 流动渐变
3. **主题切换器** — 用户可在 Dark / Light 之间切换，记忆选择
4. **可扩展** — 未来可轻松添加更多主题

---

## Phase 1: CSS 变量化（工程改造）

### 1.1 定义设计令牌

将所有硬编码 hex 值替换为 CSS 自定义属性。

**暗色主题（Dark — 当前）**

| 用途 | 当前 hex | CSS 变量名 |
|------|----------|-----------|
| 页面背景 | `#0C0C0C` | `--bg-page` |
| 侧栏背景 | `#080808` | `--bg-sidebar` |
| 卡片背景 | `#0A0A0A` | `--bg-card` |
| 高亮背景 | `#141414` | `--bg-elevated` |
| 主色 | `#00D9FF` | `--accent` |
| 主色悬停 | `#00D9FF10` | `--accent-muted` |
| 成功 | `#059669` | `--success` |
| 警告 | `#FF8800` | `--warning` |
| 错误 | `#FF4444` | `--error` |
| 紫色/角色 | `#8B5CF6` | `--purple` |
| 主文本 | `#FFFFFF` | `--text-primary` |
| 次文本 | `#8a8a8a` | `--text-secondary` |
| 弱文本 | `#6a6a6a` | `--text-muted` |
| 占位符 | `#4a4a4a` | `--text-placeholder` |
| 边框 | `#2f2f2f` | `--border` |
| 边框弱 | `#1A1A1A` | `--border-subtle` |

**明亮主题（Light — 新增）**

| 用途 | hex | CSS 变量名 |
|------|-----|-----------|
| 页面背景 | `#F8FAFC` | `--bg-page` |
| 侧栏背景 | `#FFFFFF` | `--bg-sidebar` |
| 卡片背景 | `#FFFFFF` | `--bg-card` |
| 高亮背景 | `#F1F5F9` | `--bg-elevated` |
| 主色 | `#1E40AF` | `--accent`（宝蓝） |
| 主色悬停 | `#1E40AF10` | `--accent-muted` |
| 成功 | `#059669` | `--success` |
| 警告 | `#D97706` | `--warning` |
| 错误 | `#DC2626` | `--error` |
| 紫色/角色 | `#7C3AED` | `--purple` |
| 主文本 | `#0F172A` | `--text-primary` |
| 次文本 | `#475569` | `--text-secondary` |
| 弱文本 | `#94A3B8` | `--text-muted` |
| 占位符 | `#CBD5E1` | `--text-placeholder` |
| 边框 | `#E2E8F0` | `--border` |
| 边框弱 | `#F1F5F9` | `--border-subtle` |

### 1.2 Tailwind 配置

在 `tailwind.config.ts` 中将 CSS 变量映射为 Tailwind 类名：

```ts
theme: {
  extend: {
    colors: {
      page: 'var(--bg-page)',
      sidebar: 'var(--bg-sidebar)',
      card: 'var(--bg-card)',
      elevated: 'var(--bg-elevated)',
      accent: 'var(--accent)',
      'accent-muted': 'var(--accent-muted)',
      'text-primary': 'var(--text-primary)',
      'text-secondary': 'var(--text-secondary)',
      'text-muted': 'var(--text-muted)',
      'text-placeholder': 'var(--text-placeholder)',
      'border-default': 'var(--border)',
      'border-subtle': 'var(--border-subtle)',
    },
  },
}
```

### 1.3 替换策略

全局搜索替换，逐类处理：

| 原始 Tailwind class | 新 class |
|---------------------|----------|
| `bg-[#0C0C0C]` | `bg-page` |
| `bg-[#080808]` | `bg-sidebar` |
| `bg-[#0A0A0A]` | `bg-card` |
| `bg-[#141414]` | `bg-elevated` |
| `text-[#00D9FF]` | `text-accent` |
| `text-white` | `text-primary` |
| `text-[#8a8a8a]` | `text-secondary` |
| `text-[#6a6a6a]` | `text-muted` |
| `text-[#4a4a4a]` | `text-placeholder` |
| `border-[#2f2f2f]` | `border-default` |
| `border-[#1A1A1A]` | `border-subtle` |

### 1.4 涉及文件

所有前端页面和组件（约 30+ 文件）：
- `src/pages/*.tsx`（16+ 页面）
- `src/components/layout/*.tsx`（Sidebar, AppLayout, Header）
- `src/components/chat/*.tsx`
- `src/components/ui/*.tsx`
- `src/plugins/*.tsx`

---

## Phase 2: 主题切换器

### 2.1 Zustand Store

```ts
// stores/themeStore.ts
interface ThemeStore {
  theme: 'dark' | 'light';
  setTheme: (theme: 'dark' | 'light') => void;
  toggleTheme: () => void;
}
```

- 持久化到 `localStorage('theme-preference')`
- 初始值：检测系统偏好 `prefers-color-scheme`，默认 `dark`

### 2.2 切换器 UI

在 Sidebar 底部或 Header 右侧添加：
- 太阳/月亮图标按钮
- 点击切换 `document.documentElement.dataset.theme`

### 2.3 CSS 变量注入

```css
:root, [data-theme="dark"] {
  --bg-page: #0C0C0C;
  /* ... dark vars ... */
}

[data-theme="light"] {
  --bg-page: #F8FAFC;
  /* ... light vars ... */
}
```

---

## Phase 3: 毛玻璃 + 流动渐变

### 3.1 毛玻璃效果（Glass Morphism）

应用位置：
- **侧栏** — `backdrop-blur-xl bg-sidebar/80`
- **卡片** — `backdrop-blur-md bg-card/70 border border-white/10`
- **Modal 背景** — `backdrop-blur-sm bg-black/60`
- **Header** — `backdrop-blur-lg bg-page/80 sticky`

亮色主题特有：
```css
/* 亮色下毛玻璃效果更明显 */
.glass-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08);
}
```

### 3.2 流动渐变（Flowing Gradient）

应用位置：
- **页面背景** — 低透明度全屏渐变动画
- **侧栏高亮条** — 选中菜单项的左侧光条
- **卡片 hover** — 边框渐变光效

```css
@keyframes gradient-flow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.flowing-gradient {
  background: linear-gradient(-45deg,
    var(--accent),
    #8B5CF6,
    #EC4899,
    var(--accent)
  );
  background-size: 400% 400%;
  animation: gradient-flow 8s ease infinite;
}
```

### 3.3 亮色主题专属效果

- **背景光斑** — 页面右上角和左下角各一个大的模糊光斑（`radial-gradient`），缓慢移动
- **卡片悬停光效** — hover 时边框出现渐变流光
- **侧栏底部渐变** — 从 `transparent` 到 `bg-sidebar` 的淡出效果

---

## Phase 4: Pencil 设计稿（可选）

如需精确视觉效果，在 Pencil 中画以下页面：

| 页面 | Dark | Light + Glass |
|------|------|---------------|
| Dashboard | 保持现有 | 新设计 |
| Chat | 保持现有 | 新设计 |
| Sidebar | 保持现有 | 新设计 |

---

## 实施顺序

| 步骤 | 内容 | 预计改动 |
|------|------|---------|
| **Step 1** | CSS 变量定义 + Tailwind 配置 | 2 文件 |
| **Step 2** | 全局替换硬编码 hex → CSS 变量类名 | 30+ 文件 |
| **Step 3** | 主题切换器 Store + UI | 3 文件 |
| **Step 4** | 明亮主题色板定义 | 1 文件 |
| **Step 5** | 毛玻璃效果（侧栏、卡片、Header） | 5-8 文件 |
| **Step 6** | 流动渐变（背景、hover、高亮） | 5-8 文件 |
| **Step 7** | 测试 + 微调两主题下的视觉效果 | 全部 |

---

## 注意事项

- Step 2（全局替换）是工作量最大的一步，但是纯机械操作
- 每一步完成后都能正常运行，不会出现中间状态破坏 UI
- 暗色主题效果不变，只是从硬编码 hex 变成 CSS 变量
- 插件也会自动继承主题（因为用的是同一个 CSS 变量空间）
- 字体不变：Space Grotesk（标题）、Inter（正文）、JetBrains Mono（数据）
