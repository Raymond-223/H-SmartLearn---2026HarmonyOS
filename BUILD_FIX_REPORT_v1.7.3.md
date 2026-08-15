# H-SmartLearn v1.7.3 DevEco 编译修复报告

## 真实构建错误

DevEco Studio 在 `CompileArkTS` 阶段报告：

```text
Property 'fontColor' does not exist on type 'HyperlinkAttribute'.
ResourceViewPage.ets:733
```

## 根因

`Hyperlink` 是独立的 ArkUI 组件，其属性集合不是 `TextAttribute`。上一版把 `Text` 的 `.fontColor()` 链式属性错误地应用到了 `Hyperlink`，因此 ArkTS 严格类型检查失败。

## 修改

文件：`entry/src/main/ets/pages/ResourceViewPage.ets`

修改前：

```typescript
Hyperlink(citation.source_url, '打开原始证据 ↗').fontColor(C.skyDeep)
```

修改后：

```typescript
Hyperlink(citation.source_url, '打开原始证据 ↗')
```

链接仍然可点击并由 `Hyperlink` 组件负责跳转；相邻 URL 文本继续使用 `Text.fontColor()` 展示主题颜色并支持长按复制。

## 同类扫描

- 项目内 `Hyperlink` 调用：1 处。
- `Hyperlink.fontColor`：0 处。
- `Hyperlink.fontSize`：0 处。
- `Hyperlink.fontWeight`：0 处。
- `Hyperlink.fontStyle`：0 处。
- `Hyperlink.decoration`：0 处。

## 验证边界

本环境没有 DevEco Studio，因此本报告确认的是源码修复和同类模式清零。最终是否编译成功，以开发机重新执行 `assembleHap --analyze=normal` 的结果为准。
