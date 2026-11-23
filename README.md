# XEditor

<p align="center">
  <img src="samples/images/xeditor.png" width="96" alt="XEditor 图标">
</p>

<p align="center">
  <b>一款轻量的 Markdown 阅读与编辑器</b><br>
  Python + PySide6 · 本地优先 · 实时预览
</p>

<p align="center">
  <b>版本 1.0.0</b> &nbsp;·&nbsp; 作者：eein &nbsp;·&nbsp;
  联系邮箱：<a href="mailto:eein@163.com">eein@163.com</a>
</p>

XEditor 使用 Python 与 PySide6 编写，面向日常的 Markdown 阅读和写作。左侧编辑、右侧实时预览，支持大纲导航、语法高亮、查找替换、双主题、沉浸式阅读以及 HTML / PDF 导出。所有内容都在本地处理，不需要联网。

## 功能特性

- **实时预览**：边写边看，支持标题锚点、表格、任务列表、脚注、删除线、围栏代码块等常用 Markdown 扩展。
- **Markdown 语法高亮**：标题、强调、链接、引用、列表、代码块分别着色，带行号与当前行提示。
- **代码高亮**：基于 Pygments，内置浅色与深色两套配色。
- **标题大纲**：自动解析标题层级，点击即可跳转到对应章节。
- **查找 / 替换**：支持区分大小写、全词匹配、正则表达式、全部替换与匹配高亮。
- **双主题**：浅色 / 深色 / 跟随系统，可随时切换。
- **阅读模式**：`Ctrl+Shift+R` 隐藏编辑区，专注阅读。
- **导出**：导出为独立 HTML（图片内嵌为 Base64）或 PDF。
- **文件处理**：自动保存（可开关，针对已有文件）、最近文件、拖拽打开、命令行打开；自动识别 UTF-8 / UTF-8 BOM / GB18030 / Big5，保留原换行符与编码。
- **编辑体验**：自动延续列表/引用、Tab 缩进、快捷键插入格式、自定义编辑器字体、`Ctrl+滚轮` 缩放。
- **安全渲染**：过滤 `<script>`、`<iframe>`、事件处理器、`javascript:` 等危险 HTML；裸 `http(s)://` 与 `www.` 链接自动识别。
- **状态栏**：行列位置、字数、字符数、预计阅读时间与文件编码。
- **可持久化**：窗口布局、主题、字体、大纲宽度和最近文件会被记住。

## 截图

| 浅色主题 | 深色主题 |
| --- | --- |
| ![浅色主题](docs/screenshot-light.png) | ![深色主题](docs/screenshot-dark.png) |

| 查找 | 阅读模式 |
| --- | --- |
| ![查找替换](docs/screenshot-find.png) | ![阅读模式](docs/screenshot-reading.png) |

## 环境要求

- Python **3.10+**
- PySide6 **6.6+**
- Python-Markdown **3.5+**
- Pygments **2.16+**

开发环境为 Windows 11 + Python 3.12 + PySide6 6.7.2；代码本身可运行于 Linux 与 macOS，字体和快捷键会自动回退。

## 安装与运行

```powershell
# 在项目目录中
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 启动
python main.py

# 或者
python -m xeditor

# 直接打开某个文件
python main.py samples\demo.md
```

也可以作为包安装：

```powershell
pip install -e .
xeditor samples\demo.md
```

## 使用说明

- **打开文件**：`文件 → 打开`、`Ctrl+O`，或把 `.md` / `.txt` 文件直接拖进窗口。
- **保存**：`Ctrl+S`；首次保存会询问路径。打开已有文件时会保留原编码和换行符。已有文件默认在停止输入约 2 秒后自动保存，可在「文件 → 自动保存」中关闭；未命名文档仍需手动保存。
- **预览与大纲**：`Ctrl+Shift+P` 显示/隐藏预览，`Ctrl+Shift+O` 显示/隐藏大纲；可拖动分隔条调整宽度。
- **阅读模式**：`Ctrl+Shift+R`。在大纲中点击章节会同步滚动预览，再次按 `Ctrl+Shift+R` 退出。
- **查找替换**：`Ctrl+F` / `Ctrl+H`，`Enter` 下一个，`Shift+Enter` 上一个，`Esc` 关闭。
- **主题**：菜单「视图 → 主题」或点击工具栏右侧的月亮/太阳图标。选择「跟随系统」后会随系统外观变化。
- **导出**：`文件 → 导出`。HTML 会把本地图片内嵌到文件中，便于单独分享；PDF 固定使用浅色排版。
- **字体与缩放**：`视图 → 编辑器字体…`；`Ctrl+=` / `Ctrl+-` / `Ctrl+0` 缩放编辑区；在预览中按住 `Ctrl` 滚动滚轮缩放预览。

## 快捷键

| 功能 | 快捷键 |
| --- | --- |
| 新建 / 打开 / 保存 / 另存为 | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` |
| 撤销 / 重做 | `Ctrl+Z` / `Ctrl+Y` |
| 查找 / 替换 | `Ctrl+F` / `Ctrl+H` |
| 加粗 / 斜体 / 删除线 / 行内代码 | `Ctrl+B` / `Ctrl+I` / `Ctrl+Shift+X` / `Ctrl+E` |
| 插入链接 | `Ctrl+K` |
| 1–6 级标题 | `Ctrl+1` … `Ctrl+6` |
| 显示/隐藏预览 / 大纲 | `Ctrl+Shift+P` / `Ctrl+Shift+O` |
| 阅读模式 | `Ctrl+Shift+R` |
| 放大 / 缩小 / 重置缩放 | `Ctrl+=` / `Ctrl+-` / `Ctrl+0` |
| 全屏 | `F11` |
| 退出 | `Ctrl+Q` |

编辑器中按 `Tab` 缩进、`Shift+Tab` 反缩进；在列表或引用行末按回车会自动延续。

## Markdown 支持范围

基于 Python-Markdown 的 `extra`、`toc`、`codehilite`、`sane_lists`、`meta` 扩展，并额外支持：

- 表格、任务列表、围栏代码块、脚注
- 删除线（`~~文本~~`）与高亮（`==文本==`）
- 裸链接自动识别与标题锚点、`[TOC]`
- YAML Front Matter（预览中隐藏）
- 原始 HTML（自动过滤危险标签与属性，仅使用 Qt 富文本引擎支持的标签）

预览使用 `QTextBrowser` 而非浏览器内核，因此复杂 HTML/CSS 的渲染结果可能与浏览器存在差异；不支持 JavaScript、Mermaid 图表与数学公式。外部图片不会自动下载，本地图片按文档所在目录解析。

## 项目结构

```
XEditor/
├─ main.py                 # 启动入口
├─ xeditor/
│  ├─ app.py               # QApplication 初始化
│  ├─ main_window.py       # 主窗口与功能编排
│  ├─ editor.py            # 编辑器、行号、缩进与自动列表
│  ├─ highlighter.py       # Markdown 语法高亮
│  ├─ renderer.py          # Markdown → HTML
│  ├─ html_process.py      # HTML 安全过滤与裸链接识别
│  ├─ preview.py           # 预览面板、滚动同步、链接/图片处理
│  ├─ outline.py           # 标题大纲
│  ├─ findbar.py           # 查找 / 替换
│  ├─ themes.py            # 主题、QSS、预览 CSS
│  ├─ icons.py             # 矢量图标
│  ├─ settings.py          # QSettings 封装
│  ├─ dialogs.py           # 语法速查 / 关于
│  └─ welcome.py           # 欢迎文档与语法速查内容
├─ samples/demo.md         # 功能演示文档
├─ samples/images/         # 演示图片
├─ assets/xeditor.ico      # 应用图标（打包用）
├─ packaging/version_info.txt # Windows EXE 版本信息
├─ build_exe.ps1           # 单文件 EXE 构建脚本
├─ docs/                   # 截图
├─ tests/test_functional.py# 端到端功能测试
├─ requirements.txt
└─ pyproject.toml
```

## 测试

```powershell
python tests\test_functional.py
```

测试覆盖打开/保存/自动保存、编码识别、查找替换、格式化、自动列表、HTML 安全过滤、裸链接识别、导出、主题、阅读模式、滚动同步等流程。测试默认使用 `offscreen` 平台，不会弹出窗口。

## 打包

项目已提供 **单文件 EXE** 构建脚本、应用图标和 Windows 版本信息。当前已构建并验证：

- 文件：**`dist\XEditor.exe`**
- 大小：约 **66 MB**（Windows 10/11 x64）
- 版本：**1.0.0**
- 作者 / 邮箱：**eein / eein@163.com**

```powershell
pip install pyinstaller
.\build_exe.ps1
```

或直接执行：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name XEditor --icon assets\xeditor.ico `
  --version-file packaging\version_info.txt `
  --collect-submodules markdown main.py
```

生成的文件位于 **`dist\XEditor.exe`**。单文件版首次启动需要解压 Qt 运行库，通常会比源码启动慢几秒；启动后不依赖当前源码目录。EXE 属性页中包含版本 1.0.0、作者 eein 与联系邮箱信息。

> EXE 未进行代码签名，Windows SmartScreen 可能提示“未知发布者”；如需正式分发，建议使用代码签名证书签名。

## 关于

- 软件：**XEditor 1.0.0**
- 作者：**eein**
- 联系邮箱：**eein@163.com**
- 版权：Copyright (c) 2026 eein
- 许可证：MIT

<p>
  <img src="docs/screenshot-about.png" width="440" alt="关于 XEditor">
</p>

## 已知限制

- 预览不是完整浏览器，复杂 HTML/CSS、JavaScript、Mermaid、KaTeX 不支持。
- PDF 由 Qt 文档引擎打印生成；超长代码块等复杂内容可能跨页拆分。
- 暂不支持 DOCX / EPUB 导出、多标签页、文件外部修改监听与跨文件全文搜索。
- 应用界面目前为简体中文。

## License

MIT
