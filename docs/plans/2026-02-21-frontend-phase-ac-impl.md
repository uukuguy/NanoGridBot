# NanoGridBot 前端改造实施计划 — Phase A + Phase C

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成 NanoGridBot 前端的品牌清理（Phase A）和页面整合/导航精简（Phase C），清除所有 HappyClaw 引用并简化为桌面优先的开发工具导航。

**Architecture:** Phase A 是纯文本替换，不改功能和布局。Phase C 删除 GroupsPage、MonitorPage 独立页面（功能后续合并到 Debug Console），移除移动端底部导航和滑动切换，简化 NavRail 为 Console/Settings/Admin 三项。

**Tech Stack:** React 19 + TypeScript + Vite 6 + Tailwind CSS 4 + Zustand 5 + React Router 7

**设计文档:** `docs/plans/2026-02-21-frontend-redesign.md`

---

## Phase A：品牌清理

### Task 1: index.html 品牌替换

**Files:**
- Modify: `frontend/index.html:13,25`

**Step 1: 替换 HappyClaw 文本**

将 `index.html` 中两处 HappyClaw 替换为 NanoGridBot：

```html
<!-- 第 13 行: apple-mobile-web-app-title -->
<meta name="apple-mobile-web-app-title" content="NanoGridBot" />

<!-- 第 25 行: title -->
<title>NanoGridBot</title>
```

**Step 2: 验证**

Run: `grep -n "HappyClaw" frontend/index.html`
Expected: 无输出（0 matches）

**Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "brand: replace HappyClaw with NanoGridBot in index.html"
```

---

### Task 2: main.tsx + vite-env.d.ts + url.ts 全局变量名替换

**Files:**
- Modify: `frontend/src/main.tsx:8`
- Modify: `frontend/src/vite-env.d.ts:9`
- Modify: `frontend/src/utils/url.ts:48`

**Step 1: 替换全局变量名**

三个文件中将 `__HAPPYCLAW_HASH_ROUTER__` 替换为 `__NGB_HASH_ROUTER__`：

`main.tsx` 第 8 行：
```typescript
window.__NGB_HASH_ROUTER__ = shouldUseHashRouter();
```

`vite-env.d.ts` 第 9 行：
```typescript
__NGB_HASH_ROUTER__?: boolean;
```

`url.ts` 第 48 行：
```typescript
if (window.__NGB_HASH_ROUTER__) {
```

**Step 2: 验证**

Run: `grep -rn "HAPPYCLAW" frontend/src/`
Expected: 无输出（0 matches）

**Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过，无错误

**Step 4: Commit**

```bash
git add frontend/src/main.tsx frontend/src/vite-env.d.ts frontend/src/utils/url.ts
git commit -m "brand: rename __HAPPYCLAW_HASH_ROUTER__ to __NGB_HASH_ROUTER__"
```

---

### Task 3: LoginPage.tsx 品牌替换

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx:85,91,152-155`

**Step 1: 替换品牌文本**

三处替换：

第 85 行 — logo alt：
```tsx
alt="NanoGridBot"
```

第 91 行 — 欢迎语：
```tsx
欢迎使用 NanoGridBot
```

第 152-155 行 — footer：
```tsx
<p className="text-center text-sm text-slate-500 mt-4">
  NanoGridBot — Agent Dev Console
</p>
```

**Step 2: 验证**

Run: `grep -n "HappyClaw\|riba2534" frontend/src/pages/LoginPage.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "brand: replace HappyClaw branding in LoginPage"
```

---

### Task 4: RegisterPage.tsx 品牌替换

**Files:**
- Modify: `frontend/src/pages/RegisterPage.tsx:118,146,238-241`

**Step 1: 替换品牌文本**

第 118 行和第 146 行 — logo alt：
```tsx
alt="NanoGridBot"
```

第 238-241 行 — footer：
```tsx
<p className="text-center text-sm text-slate-500 mt-4">
  NanoGridBot — Agent Dev Console
</p>
```

**Step 2: 验证**

Run: `grep -n "HappyClaw\|riba2534" frontend/src/pages/RegisterPage.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/pages/RegisterPage.tsx
git commit -m "brand: replace HappyClaw branding in RegisterPage"
```

---

### Task 5: SetupPage.tsx 品牌替换

**Files:**
- Modify: `frontend/src/pages/SetupPage.tsx:60,63,64`

**Step 1: 替换品牌文本**

第 60 行 — logo alt：
```tsx
alt="NanoGridBot"
```

第 63 行 — 标题：
```tsx
NanoGridBot 初始设置
```

第 64 行 — 副标题（去掉飞书 Token 引用，改为通用描述）：
```tsx
配置 Claude API Key 和系统参数
```

**Step 2: 验证**

Run: `grep -n "HappyClaw\|飞书 Token" frontend/src/pages/SetupPage.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/pages/SetupPage.tsx
git commit -m "brand: replace HappyClaw branding in SetupPage"
```

---

### Task 6: ChatPage.tsx 品牌替换

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx:68,71`

**Step 1: 替换品牌文本**

第 68 行 — logo alt：
```tsx
alt="NanoGridBot"
```

第 71 行 — 欢迎语 fallback：
```tsx
欢迎使用 {appearance?.appName || 'NanoGridBot'}
```

**Step 2: 验证**

Run: `grep -n "HappyClaw" frontend/src/pages/ChatPage.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "brand: replace HappyClaw branding in ChatPage"
```

---

### Task 7: NavRail.tsx 品牌替换

**Files:**
- Modify: `frontend/src/components/layout/NavRail.tsx:31`

**Step 1: 替换 logo alt**

第 31 行：
```tsx
alt="NanoGridBot"
```

**Step 2: 验证**

Run: `grep -n "HappyClaw" frontend/src/components/layout/NavRail.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/components/layout/NavRail.tsx
git commit -m "brand: replace HappyClaw logo alt in NavRail"
```

---

### Task 8: ChatSidebar.tsx 品牌替换

**Files:**
- Modify: `frontend/src/components/chat/ChatSidebar.tsx:104`

**Step 1: 替换 fallback name**

第 104 行：
```tsx
const appName = appearance?.appName || 'NanoGridBot';
```

**Step 2: 验证**

Run: `grep -n "HappyClaw" frontend/src/components/chat/ChatSidebar.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/components/chat/ChatSidebar.tsx
git commit -m "brand: replace HappyClaw fallback in ChatSidebar"
```

---

### Task 9: AppearanceSection.tsx 品牌替换

**Files:**
- Modify: `frontend/src/components/settings/AppearanceSection.tsx:95,109,124`

**Step 1: 替换 placeholder 和 fallback**

第 95 行 — AI 名称 fallback：
```tsx
<div className="text-sm font-medium text-slate-900">{aiName || 'NanoGridBot'}</div>
```

第 109 行 — 项目名称 placeholder：
```tsx
placeholder="NanoGridBot"
```

第 124 行 — AI 名称 placeholder：
```tsx
placeholder="NanoGridBot"
```

**Step 2: 验证**

Run: `grep -n "HappyClaw" frontend/src/components/settings/AppearanceSection.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/components/settings/AppearanceSection.tsx
git commit -m "brand: replace HappyClaw placeholders in AppearanceSection"
```

---

### Task 10: AboutSection.tsx 品牌替换

**Files:**
- Modify: `frontend/src/components/settings/AboutSection.tsx` (全文重写)

**Step 1: 替换 About 页面内容**

将整个 AboutSection 组件内容替换为 NanoGridBot 项目信息：

```tsx
import { Github, ExternalLink, Heart, Code2 } from 'lucide-react';

export function AboutSection() {
  return (
    <div className="space-y-6">
      {/* 项目信息 */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-1">NanoGridBot</h2>
        <p className="text-sm text-slate-500">Agent Dev Console & Lightweight Runtime</p>
      </div>

      {/* 开源地址 */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Github className="w-4 h-4 text-slate-400 shrink-0" />
          <a
            href="https://github.com/nickerso/NanoGridBot"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-teal-600 hover:text-teal-700 inline-flex items-center gap-1"
          >
            NanoGridBot
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        <div className="flex items-center gap-3">
          <Code2 className="w-4 h-4 text-slate-400 shrink-0" />
          <span className="text-sm text-slate-700">Agent Development Console</span>
        </div>
      </div>

      <hr className="border-slate-100" />

      {/* 设计哲学 */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Heart className="w-4 h-4 text-rose-500" />
          <h3 className="text-sm font-medium text-slate-900">设计哲学</h3>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed">
          站在巨人的肩膀上，基于 Claude Code（全世界最好的 Agent）构建。
          提供轻量、快速、功能强大的 Agent 开发调试控制台。
        </p>
      </div>
    </div>
  );
}
```

**Step 2: 验证**

Run: `grep -n "HappyClaw\|riba2534\|happyclaw" frontend/src/components/settings/AboutSection.tsx`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/components/settings/AboutSection.tsx
git commit -m "brand: rewrite AboutSection for NanoGridBot"
```

---

### Task 11: adapter.ts 品牌替换

**Files:**
- Modify: `frontend/src/api/adapter.ts:1-6,164`

**Step 1: 替换注释和默认值**

第 1-6 行 — 模块注释：
```typescript
/**
 * NanoGridBot API Adapter
 *
 * This adapter maps frontend API calls to NanoGridBot backend responses.
 * It handles endpoint mapping and response transformation.
 */
```

第 164 行 — 默认 appName（已经是 NanoGridBot，确认无需更改）。

第 12 行的类型注释 `// Type Definitions (matching HappyClaw frontend expectations)` 改为：
```typescript
// Type Definitions
```

**Step 2: 验证**

Run: `grep -n "HappyClaw\|happyclaw" frontend/src/api/adapter.ts`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/src/api/adapter.ts
git commit -m "brand: clean HappyClaw references in adapter.ts"
```

---

### Task 12: package.json 品牌替换

**Files:**
- Modify: `frontend/package.json:48-49,51`

**Step 1: 替换 repository 和 author**

```json
"repository": {
  "type": "git",
  "url": "git+https://github.com/nickerso/NanoGridBot.git",
  "directory": "frontend"
},
"author": "NanoGridBot Team"
```

**Step 2: 验证**

Run: `grep -n "happyclaw\|riba2534" frontend/package.json`
Expected: 无输出

**Step 3: Commit**

```bash
git add frontend/package.json
git commit -m "brand: update package.json repository and author"
```

---

### Task 13: 全面验证 Phase A 品牌清理

**Step 1: 全局搜索残留的 HappyClaw 引用**

Run: `grep -rn "HappyClaw\|happyclaw\|HAPPYCLAW\|riba2534" frontend/src/ frontend/index.html frontend/package.json`
Expected: 无输出（0 matches）

**Step 2: TypeScript 编译检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过

**Step 3: 开发服务器启动测试**

Run: `cd frontend && npx vite --host 0.0.0.0 &`
Expected: 服务器正常启动，无编译错误。验证后 `kill %1` 关闭。

**Step 4: Commit（如有遗漏修复）**

```bash
git add -A frontend/
git commit -m "brand: Phase A complete - all HappyClaw references removed"
```

---

## Phase C：页面整合 + 导航精简

### Task 14: 简化 NavRail 导航项

**Files:**
- Modify: `frontend/src/components/layout/NavRail.tsx:1-12`

**Step 1: 更新导航项**

将 navItems 从 4 项改为 3 项（移除监控，工作台改名为 Console）：

```typescript
import { NavLink, useNavigate } from 'react-router-dom';
import { Terminal, Settings, Users, LogOut } from 'lucide-react';
import { useAuthStore } from '../../stores/auth';
import { EmojiAvatar } from '../common/EmojiAvatar';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const navItems = [
  { path: '/chat', icon: Terminal, label: 'Console' },
  { path: '/settings', icon: Settings, label: '设置' },
];
```

**Step 2: 添加 Admin 导航项（仅管理员可见）**

在 NavRail 组件内部，在现有 navItems 渲染之后、spacer 之前，添加条件渲染的 Admin 项：

```tsx
{/* Admin — only visible to users with admin permissions */}
{user?.role === 'admin' && (
  <Tooltip>
    <TooltipTrigger asChild>
      <NavLink
        to="/users"
        className={({ isActive }) =>
          `w-12 h-12 rounded-lg flex flex-col items-center justify-center gap-0.5 transition-colors ${
            isActive
              ? 'bg-brand-50 text-primary'
              : 'text-muted-foreground hover:bg-accent'
          }`
        }
      >
        <Users className="w-5 h-5" />
        <span className="text-xs">Admin</span>
      </NavLink>
    </TooltipTrigger>
    <TooltipContent side="right">
      用户管理
    </TooltipContent>
  </Tooltip>
)}
```

**Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过

**Step 4: Commit**

```bash
git add frontend/src/components/layout/NavRail.tsx
git commit -m "nav: simplify NavRail to Console/Settings/Admin"
```

---

### Task 15: 移除 BottomTabBar 和 SwipeablePages

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.tsx` (大幅简化)
- Delete: `frontend/src/components/layout/BottomTabBar.tsx`
- Delete: `frontend/src/components/layout/SwipeablePages.tsx`

**Step 1: 简化 AppLayout**

将 AppLayout.tsx 替换为纯桌面布局（无 SwipeablePages，无 BottomTabBar）：

```tsx
import { Outlet } from 'react-router-dom';
import { NavRail } from './NavRail';

export function AppLayout() {
  return (
    <div className="h-screen supports-[height:100dvh]:h-dvh flex flex-row overflow-hidden">
      <div className="h-full">
        <NavRail />
      </div>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

**Step 2: 删除 BottomTabBar.tsx**

Run: `rm frontend/src/components/layout/BottomTabBar.tsx`

**Step 3: 删除 SwipeablePages.tsx**

Run: `rm frontend/src/components/layout/SwipeablePages.tsx`

**Step 4: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过。如果有其他文件导入 BottomTabBar 或 SwipeablePages，需要清理这些引用。

**Step 5: Commit**

```bash
git add frontend/src/components/layout/AppLayout.tsx
git rm frontend/src/components/layout/BottomTabBar.tsx
git rm frontend/src/components/layout/SwipeablePages.tsx
git commit -m "nav: remove BottomTabBar and SwipeablePages, desktop-first layout"
```

---

### Task 16: 移除 MonitorPage 路由

**Files:**
- Modify: `frontend/src/App.tsx:9,19,59`

**Step 1: 从 App.tsx 中移除 MonitorPage 相关代码**

删除 MonitorPage 的 lazy import（第 19 行）：
```typescript
// 删除这行:
// const MonitorPage = lazy(() => import('./pages/MonitorPage').then(m => ({ default: m.MonitorPage })));
```

删除 `/monitor` 路由（第 59 行）：
```tsx
// 删除这行:
// <Route path="/monitor" element={<Suspense fallback={null}><MonitorPage /></Suspense>} />
```

**Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "route: remove /monitor route from App.tsx"
```

---

### Task 17: 移除 GroupsPage 路由

**Files:**
- Modify: `frontend/src/App.tsx:57`

**Step 1: 移除 /groups 重定向路由**

删除第 57 行的 groups 路由：
```tsx
// 删除这行:
// <Route path="/groups" element={<Navigate to="/settings?tab=groups" replace />} />
```

同时确认 `GroupsPage` 没有在 App.tsx 中被 import（当前已不在 import 中）。

**Step 2: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "route: remove /groups redirect from App.tsx"
```

---

### Task 18: 更新默认路由 `/` 指向

**Files:**
- Modify: `frontend/src/App.tsx:74-75`
- Modify: `frontend/vite.config.ts:28`

**Step 1: 默认路由保持 `/chat`**

当前 `App.tsx` 中 `/` 已经 Navigate 到 `/chat`，保持不变。

**Step 2: 更新 vite.config.ts PWA start_url**

`vite.config.ts` 第 28 行，`APP_START_URL` 已经是 `${APP_BASE}chat`，保持不变。

**Step 3: 验证**

Run: `grep "start_url\|APP_START_URL" frontend/vite.config.ts`
Expected: 确认 start_url 指向 chat

**Step 4: Commit（如有修改）**

如无修改则跳过。

---

### Task 19: 清理未使用的 hooks

**Files:**
- 检查: `frontend/src/hooks/useScrollDirection.ts`
- 检查: `frontend/src/hooks/useSwipeBack.ts`

**Step 1: 检查 useScrollDirection 是否还有其他引用**

Run: `grep -rn "useScrollDirection" frontend/src/ --include="*.tsx" --include="*.ts"`

如果唯一引用是已删除的 BottomTabBar.tsx，则删除此 hook：
Run: `rm frontend/src/hooks/useScrollDirection.ts`

**Step 2: 检查 useSwipeBack 引用**

Run: `grep -rn "useSwipeBack" frontend/src/ --include="*.tsx" --include="*.ts"`

useSwipeBack 在 ChatPage.tsx 中使用（移动端左滑返回），目前保留。

**Step 3: 检查 useMediaQuery 引用**

Run: `grep -rn "useMediaQuery" frontend/src/ --include="*.tsx" --include="*.ts"`

如果 SwipeablePages 删除后仍有其他引用，保留。否则删除。

**Step 4: 验证编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过

**Step 5: Commit**

```bash
git add -A frontend/src/hooks/
git commit -m "cleanup: remove unused hooks after navigation simplification"
```

---

### Task 20: 验证 AppLayout 中无残留导入

**Files:**
- 检查: `frontend/src/components/layout/AppLayout.tsx`

**Step 1: 确认 AppLayout 不再导入已删除的组件**

Run: `grep -n "BottomTabBar\|SwipeablePages\|useMediaQuery\|navItems" frontend/src/components/layout/AppLayout.tsx`
Expected: 无输出

**Step 2: 确认全局无残留的已删除组件引用**

Run: `grep -rn "BottomTabBar\|SwipeablePages" frontend/src/`
Expected: 无输出

**Step 3: Commit（如有修复）**

---

### Task 21: 全面验证 Phase C

**Step 1: TypeScript 编译检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 编译通过，无错误

**Step 2: 全局搜索残留引用**

```bash
grep -rn "MonitorPage\|GroupsPage\|BottomTabBar\|SwipeablePages" frontend/src/ --include="*.tsx" --include="*.ts"
```
Expected: 无输出（MonitorPage.tsx 和 GroupsPage.tsx 文件本身还存在，但不被引用）

**Step 3: 开发服务器启动测试**

Run: `cd frontend && npx vite --host 0.0.0.0 &`
Expected: 服务器正常启动。验证后关闭。

**Step 4: 验证路由**

通过浏览器访问以下路由确认正常：
- `/login` — 显示 NanoGridBot 登录页
- `/` — 跳转到 `/chat`
- `/chat` — Console 主页
- `/settings` — 设置页
- `/monitor` — 应显示 404 或跳转到 `/chat`

**Step 5: 最终 Commit**

```bash
git add -A frontend/
git commit -m "phase-c: complete page integration and navigation simplification"
```

---

## 注意事项

### 不删除的文件（保留但不路由）

以下文件在 Phase C 中**不路由**但**不删除**（Phase B Debug Console 可能复用其组件或 store）：

- `frontend/src/pages/MonitorPage.tsx` — 监控数据组件可在 Debug Console 底部 Metrics Tab 复用
- `frontend/src/pages/GroupsPage.tsx` — 已有 `/settings?tab=groups` 替代
- `frontend/src/stores/monitor.ts` — 监控 store 保留，Debug Console 会使用
- `frontend/src/stores/groups.ts` — groups store 保留
- `frontend/src/components/monitor/*.tsx` — 监控组件保留
- `frontend/src/components/groups/*.tsx` — groups 组件保留

### Phase B 预备

Phase C 完成后，下一步是 Phase B（Debug Console 核心改造），将 ChatPage 改造为四面板布局。该阶段需要单独的设计和实施计划。
