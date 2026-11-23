# XEditor 功能演示

这是一份用于体验 XEditor 的示例文档。你可以在左侧修改文字，右侧会**实时预览**效果。

![XEditor 图标](images/xeditor.png){ width=140 }

## 格式一览

**加粗**、*斜体*、~~删除线~~、==高亮==、`行内代码`，以及 [外部链接](https://www.python.org/)。裸链接 https://www.python.org 也会自动识别。

> 好的工具应当安静地待在幕后，让文字本身成为主角。
>
> 支持多行引用，以及引用中的 **Markdown** 语法。

### 任务清单

- [x] 完成项目骨架
- [x] 实现实时预览
- [x] 添加语法高亮
- [ ] 写下今天的第一行字
- [ ] 把文档导出为 PDF

### 表格

| 功能 | 快捷键 | 状态 |
| --- | --- | --- |
| 查找 | `Ctrl+F` | 已完成 |
| 替换 | `Ctrl+H` | 已完成 |
| 阅读模式 | `Ctrl+Shift+R` | 已完成 |
| 导出 PDF | — | 已完成 |

### 代码

```python
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Document:
    path: Path
    content: str

    @property
    def title(self) -> str:
        return self.path.stem

    def word_count(self) -> int:
        return len(self.content.split())


doc = Document(Path("demo.md"), "# Hello\n\nMarkdown makes writing simple.")
print(doc.title, doc.word_count())
```

### 列表

1. 打开一个 Markdown 文件
2. 在大纲中点击标题快速跳转
3. 按 `Ctrl+Shift+P` 收起预览，专注写作
4. 按 `Ctrl+Shift+R` 进入阅读模式

### 脚注

PySide6 是 Qt for Python 的官方绑定[^1]。

[^1]: 详见 [Qt for Python 文档](https://doc.qt.io/qtforpython/)。

---

*用 XEditor 写下你的下一篇文章。*
