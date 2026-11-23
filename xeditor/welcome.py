"""Built-in welcome document and Markdown cheat sheet."""

WELCOME_MD = """# 欢迎使用 XEditor

**XEditor** 是一款使用 Python + PySide6 编写的 Markdown 阅读与编辑器。左侧编写，右侧实时预览，专注、轻快、无需联网。

> 提示：从「文件 → 打开」载入你的 Markdown 文档，或直接把 `.md` 文件拖进窗口。

## 主要功能

- [x] 实时预览与双向滚动同步
- [x] Markdown 语法高亮、行号与当前行提示
- [x] 标题大纲，一键跳转到任意章节
- [x] 查找 / 替换，支持正则、区分大小写、全词匹配
- [x] 浅色 / 深色主题，可跟随系统
- [x] 自动保存已有文件，保留原编码与换行符
- [x] 导出 HTML（图片内嵌）与 PDF
- [ ] 更多功能，等你来发现……

## 常用快捷键

| 操作 | 快捷键 |
| --- | --- |
| 新建 / 打开 / 保存 | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` |
| 查找 / 替换 | `Ctrl+F` / `Ctrl+H` |
| 加粗 / 斜体 / 行内代码 | `Ctrl+B` / `Ctrl+I` / `Ctrl+E` |
| 插入链接 | `Ctrl+K` |
| 切换预览 / 大纲 | `Ctrl+Shift+P` / `Ctrl+Shift+O` |
| 阅读模式 | `Ctrl+Shift+R` |
| 放大 / 缩小 | `Ctrl+=` / `Ctrl+-` |

## 代码高亮示例

```python
from pathlib import Path

def read_markdown(path: str) -> str:
    \"\"\"读取一个 Markdown 文件。\"\"\"
    return Path(path).read_text(encoding="utf-8")

print(read_markdown("README.md"))
```

## 小技巧

1. 选中文字后按 `Ctrl+B` 可以快速加粗。
2. 在列表项末尾按回车，会自动延续列表；空列表项再按回车即可退出。
3. 按 `Ctrl+Shift+R` 进入沉浸式阅读模式，只保留预览。
4. 使用 `==高亮文字==` 标记重点，直接粘贴的网址会自动变成链接。
5. 在预览中点击站内链接会跳转到对应位置，点击本地文件链接则用 XEditor 打开。

---

祝你写作愉快！更多语法请查看「帮助 → Markdown 语法速查」。
"""


CHEATSHEET_MD = """# Markdown 语法速查

## 标题

```markdown
# 一级标题
## 二级标题
### 三级标题
```

## 文字样式

| 写法 | 效果 |
| --- | --- |
| `**加粗**` | **加粗** |
| `*斜体*` | *斜体* |
| `~~删除线~~` | ~~删除线~~ |
| `` `行内代码` `` | `行内代码` |

## 列表

```markdown
- 无序列表
- 第二项
  - 嵌套项

1. 有序列表
2. 第二项

- [ ] 待办事项
- [x] 已完成事项
```

## 链接与图片

```markdown
[链接文字](https://example.com)
![图片说明](images/picture.png)
```

## 引用与分隔线

```markdown
> 这是一段引用文字。

---
```

## 代码块

在三个反引号后写上语言名称即可获得语法高亮：

```python
def hello(name: str) -> str:
    return f"Hello, {name}!"
```

## 表格

```markdown
| 姓名 | 年龄 |
| --- | --- |
| 小明 | 18 |
| 小红 | 20 |
```

## 脚注

```markdown
这是带脚注的文字[^1]。

[^1]: 脚注的内容。
```

> 提示：XEditor 支持大部分 GitHub 风格 Markdown，包括表格、任务列表、删除线、脚注等。
"""
