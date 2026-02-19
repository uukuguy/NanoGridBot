# NanoGridBot TUI 架构重构设计方案

> **基于成熟组件的 TUI 架构重新设计**

**日期**: 2026-02-20
**状态**: 已批准

---

## 1. 组件选型

| 层级 | 组件 | 用途 |
|------|------|------|
| **输入框** | tui-textarea | 多行输入 + Emacs 快捷键 + 撤销重做 |
| **消息显示** | ratatui List (保持现有) | 消息列表 + 滚动 |
| **代码块** | tui-markdown | Markdown + 语法高亮 |
| **确认对话框** | tui-confirm-dialog | 退出确认等 |
| **历史搜索** | 自定义 List 面板 | Ctrl+R 历史搜索 |

---

## 2. 架构设计

```
App (状态管理)
├── ChatArea (tui-chat)
│   └── 消息列表 + 自定义渲染器
├── InputArea (tui-chat)
│   └── 多行输入 + 快捷键处理
├── SpecialRenderer (混合层 - 自定义)
│   ├── CodeBlock → tui-markdown
│   ├── ToolCall → 状态行
│   └── Thinking → 折叠块Layer (弹出
└── Popup层)
    ├── SearchOverlay (Ctrl+R 历史搜索)
    └── ConfirmDialog (tui-confirm-dialog)
```

---

## 3. 关键设计决策

### 3.1 输入处理
- 使用 tui-chat InputArea，内置完整编辑功能
- Emacs 快捷键：C-n/C-p/C-f/C-b, M-f/M-b, C-a/C-e, C-h/C-d, C-k 等
- 撤销/重做：C-u / C-r
- 无需手写光标位置、折行等复杂逻辑

### 3.2 消息渲染
- 基础列表使用 tui-chat ChatArea
- 特殊消息类型（代码块、工具调用、Thinking）使用自定义渲染器
- 代码块使用 tui-markdown 渲染 Markdown（含语法高亮）

### 3.3 弹出层
- Ctrl+R 历史搜索：自定义 List 面板（需要更精细的控制）
- 确认对话框：使用 tui-confirm-dialog
- 其他弹出：自定义实现

---

## 4. 依赖变更

### 新增依赖
```toml
tui-textarea = "0.x"      # 底层 textarea 组件
tui-chat = "0.x"          # 聊天组件（ChatArea + InputArea）
tui-markdown = "0.x"      # Markdown 渲染 + 语法高亮
tui-confirm-dialog = "0.x" # 确认对话框（可选）
```

### 可能移除
- syntect（由 tui-markdown 替代）
- 手写的 textarea 相关代码（约 300 行）

---

## 5. 实施计划

### Phase 1: 核心替换
1. 添加 tui-chat 依赖
2. 替换 InputArea 为 tui-chat InputArea
3. 替换 ChatArea 为 tui-chat ChatArea
4. 移除手写输入逻辑

### Phase 2: 渲染增强
1. 添加 tui-markdown 依赖
2. 实现自定义消息渲染器
3. 代码块使用 tui-markdown

### Phase 3: 弹出层
1. 实现 Ctrl+R 历史搜索面板
2. 添加确认对话框支持

---

## 6. 预期收益

| 指标 | 当前 | 重构后 |
|------|------|--------|
| 输入组件代码 | ~300 行 | ~50 行 |
| 折行/光标 bug | 多个 | 0 (组件自带) |
| Emacs 快捷键 | 部分实现 | 完整支持 |
| 撤销/重做 | 无 | 支持 |
| 代码高亮 | syntect | tui-markdown |

---

## 7. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 组件 API 变更 | 使用稳定版本 |
| 主题定制复杂 | 保持现有主题系统 |
| 特殊消息渲染 | 混合方案，自定义部分 |

---

## 8. 参考

- tui-chat: https://crates.io/crates/tui-chat
- tui-textarea: https://crates.io/crates/tui-textarea
- tui-markdown: https://crates.io/crates/tui-markdown
- tui-confirm-dialog: https://crates.io/crates/tui-confirm-dialog
