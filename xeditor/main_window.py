"""XEditor main window."""

from __future__ import annotations

import math
import re
from pathlib import Path

from PySide6.QtCore import (
    QIODevice,
    QMarginsF,
    QSaveFile,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QKeySequence,
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFontDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, __author__, __author_email__, __version__
from .dialogs import MarkdownCheatSheet, show_about
from .editor import MarkdownEditor, pick_mono_font
from .findbar import FindBar
from .highlighter import MarkdownHighlighter
from .icons import app_icon, icon
from .outline import OutlinePanel
from .preview import MarkdownPreview
from .renderer import render_document
from .settings import Settings
from .themes import THEMES, Theme, apply_theme, resolve_theme
from .welcome import WELCOME_MD

MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mkd", ".txt"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self._theme_preference = self.settings.text("ui/theme", "system")
        self._theme: Theme = resolve_theme(self._theme_preference)
        self._icon_actions: list[tuple[QAction, str]] = []
        self._format_buttons: list[tuple[QToolButton, str]] = []
        self._theme_actions: dict[str, QAction] = {}
        self._current_path: Path | None = None
        self._encoding = "utf-8"
        self._newline = "\n"
        self._reading_mode = False
        self._reading_restore: dict[str, bool] = {}
        self._syncing = False
        self._closing = False
        self._dock_width_applied = False
        self._cheat_sheet: MarkdownCheatSheet | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(900, 580)
        self.resize(1220, 820)
        self.setAcceptDrops(True)

        self._build_widgets()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()
        self._restore_settings()
        self._apply_theme(self._theme_preference, rerender=False)
        self._load_welcome()
        self._center_if_needed()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _editor_font(self) -> QFont:
        family = self.settings.text("editor/font_family", "")
        size = self.settings.int("editor/font_size", 11)
        families = set(QFontDatabase.families())
        if family and family in families:
            font = QFont(family)
            font.setPointSize(max(8, min(36, size)))
            font.setStyleHint(QFont.StyleHint.Monospace)
            return font
        return pick_mono_font(size)

    def _build_widgets(self) -> None:
        font = self._editor_font()
        self._mono_family = font.family()

        self.editor = MarkdownEditor(self._theme, font)
        self.highlighter = MarkdownHighlighter(self.editor.document(), self._theme, self._mono_family)
        self.find_bar = FindBar(self.editor, self._theme)

        self.editor_container = QWidget(self)
        self.editor_container.setObjectName("EditorContainer")
        container_layout = QVBoxLayout(self.editor_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(self.find_bar)
        container_layout.addWidget(self.editor, 1)

        self.preview = MarkdownPreview(self._theme, self)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.editor_container)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([620, 600])
        self.setCentralWidget(self.splitter)

        self.outline_panel = OutlinePanel(self)
        self.outline_dock = QDockWidget("大纲", self)
        self.outline_dock.setObjectName("OutlineDock")
        self.outline_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.outline_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.outline_dock.setWidget(self.outline_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.outline_dock)

    def _action(
        self,
        text: str,
        slot=None,
        *,
        shortcut: str | None = None,
        shortcuts: list[str] | None = None,
        icon_kind: str | None = None,
        checkable: bool = False,
        tip: str | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if shortcuts:
            action.setShortcuts([QKeySequence(item) for item in shortcuts])
        elif shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if icon_kind:
            self._icon_actions.append((action, icon_kind))
            action.setProperty("iconKind", icon_kind)
        if checkable:
            action.setCheckable(True)
        action.setToolTip(tip or text)
        action.setStatusTip(tip or text)
        if slot is not None:
            action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        # File -----------------------------------------------------------
        self.new_action = self._action(
            "新建", self._new_file, shortcut="Ctrl+N", icon_kind="new", tip="新建文档 (Ctrl+N)"
        )
        self.open_action = self._action(
            "打开…", self._open_file_dialog, shortcut="Ctrl+O", icon_kind="open", tip="打开 Markdown 文件 (Ctrl+O)"
        )
        self.save_action = self._action(
            "保存", self._save, shortcut="Ctrl+S", icon_kind="save", tip="保存 (Ctrl+S)"
        )
        self.save_as_action = self._action(
            "另存为…", self._save_as, shortcut="Ctrl+Shift+S", tip="另存为 (Ctrl+Shift+S)"
        )
        self.autosave_action = self._action(
            "自动保存",
            checkable=True,
            tip="停止输入约 2 秒后自动保存已有文件（未命名文档仍需手动保存）",
        )
        self.export_html_action = self._action(
            "导出为 HTML…", self._export_html, icon_kind="export", tip="导出为独立 HTML 文件"
        )
        self.export_pdf_action = self._action("导出为 PDF…", self._export_pdf, tip="导出为 PDF 文件")
        self.quit_action = self._action("退出", self.close, shortcut="Ctrl+Q", tip="退出 XEditor (Ctrl+Q)")

        self.recent_menu = QMenu("最近打开", self)

        # Edit -----------------------------------------------------------
        self.undo_action = self._action(
            "撤销", self.editor.undo, shortcut="Ctrl+Z", icon_kind="undo", tip="撤销 (Ctrl+Z)"
        )
        self.redo_action = self._action(
            "重做",
            self.editor.redo,
            shortcuts=["Ctrl+Y", "Ctrl+Shift+Z"],
            icon_kind="redo",
            tip="重做 (Ctrl+Y)",
        )
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.cut_action = self._action("剪切", self.editor.cut, shortcut="Ctrl+X")
        self.copy_action = self._action("复制", self.editor.copy, shortcut="Ctrl+C")
        self.paste_action = self._action("粘贴", self.editor.paste, shortcut="Ctrl+V")
        self.select_all_action = self._action("全选", self.editor.selectAll, shortcut="Ctrl+A")
        self.find_action = self._action(
            "查找…", self._open_find, shortcut="Ctrl+F", icon_kind="find", tip="查找 (Ctrl+F)"
        )
        self.replace_action = self._action(
            "替换…", self._open_replace, shortcut="Ctrl+H", tip="查找并替换 (Ctrl+H)"
        )

        # Format ---------------------------------------------------------
        self.bold_action = self._action(
            "加粗", lambda: self.editor.toggle_inline("**", "加粗文字"), shortcut="Ctrl+B", tip="加粗 (Ctrl+B)"
        )
        self.italic_action = self._action(
            "斜体", lambda: self.editor.toggle_inline("*", "斜体文字"), shortcut="Ctrl+I", tip="斜体 (Ctrl+I)"
        )
        self.strike_action = self._action(
            "删除线",
            lambda: self.editor.toggle_inline("~~", "删除线文字"),
            shortcut="Ctrl+Shift+X",
            tip="删除线 (Ctrl+Shift+X)",
        )
        self.inline_code_action = self._action(
            "行内代码", lambda: self.editor.toggle_inline("`", "代码"), shortcut="Ctrl+E", tip="行内代码 (Ctrl+E)"
        )
        self.code_block_action = self._action(
            "代码块", self.editor.insert_code_block, shortcut="Ctrl+Shift+C", tip="插入代码块"
        )
        self.link_action = self._action(
            "插入链接", self.editor.insert_link, shortcut="Ctrl+K", icon_kind="link", tip="插入链接 (Ctrl+K)"
        )
        self.image_action = self._action("插入图片", self.editor.insert_image)
        self.heading_actions: list[QAction] = []
        for level in range(1, 7):
            self.heading_actions.append(
                self._action(
                    f"{level} 级标题",
                    lambda checked=False, lv=level: self.editor.apply_heading(lv),
                    shortcut=f"Ctrl+{level}",
                )
            )
        self.clear_heading_action = self._action(
            "清除标题", lambda: self.editor.apply_heading(0)
        )
        self.bullet_action = self._action(
            "无序列表", lambda: self.editor.toggle_line_prefix("- ")
        )
        self.numbered_action = self._action(
            "有序列表", lambda: self.editor.toggle_line_prefix("1. ")
        )
        self.task_action = self._action("任务列表", self.editor.toggle_task_list)
        self.quote_action = self._action("引用", lambda: self.editor.toggle_line_prefix("> "))
        self.hr_action = self._action("分隔线", self.editor.insert_horizontal_rule)
        self.table_action = self._action("表格", self.editor.insert_table)
        self.date_action = self._action("插入日期", self.editor.insert_date)

        # View -----------------------------------------------------------
        self.preview_action = self._action(
            "预览面板",
            checkable=True,
            icon_kind="eye",
            shortcut="Ctrl+Shift+P",
            tip="显示或隐藏预览 (Ctrl+Shift+P)",
        )
        self.preview_action.setChecked(True)
        self.outline_action = self._action(
            "大纲面板",
            checkable=True,
            icon_kind="outline",
            shortcut="Ctrl+Shift+O",
            tip="显示或隐藏大纲 (Ctrl+Shift+O)",
        )
        self.outline_action.setChecked(True)
        self.sync_action = self._action(
            "同步滚动", checkable=True, tip="编辑区与预览区滚动同步"
        )
        self.sync_action.setChecked(True)
        self.wrap_action = self._action(
            "自动换行", checkable=True, tip="编辑器自动换行"
        )
        self.wrap_action.setChecked(True)
        self.reading_action = self._action(
            "阅读模式",
            checkable=True,
            icon_kind="book",
            shortcut="Ctrl+Shift+R",
            tip="进入沉浸式阅读模式 (Ctrl+Shift+R)",
        )
        self.font_action = self._action("编辑器字体…", self._choose_font)
        self.zoom_in_action = self._action(
            "放大", lambda: self.editor.zoom(1), shortcuts=["Ctrl+=", "Ctrl++"], tip="放大 (Ctrl+=)"
        )
        self.zoom_out_action = self._action(
            "缩小", lambda: self.editor.zoom(-1), shortcut="Ctrl+-", tip="缩小 (Ctrl+-)"
        )
        self.zoom_reset_action = self._action("重置缩放", self._reset_zoom, shortcut="Ctrl+0")
        self.fullscreen_action = self._action(
            "全屏", checkable=True, shortcut="F11", tip="切换全屏 (F11)"
        )

        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        for key, label in (("system", "跟随系统"), ("light", "浅色"), ("dark", "深色")):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(key)
            action.triggered.connect(
                lambda checked=False, k=key: self._apply_theme(k)
            )
            self.theme_group.addAction(action)
            self._theme_actions[key] = action

        # Help -----------------------------------------------------------
        self.cheatsheet_action = self._action(
            "Markdown 语法速查", self._show_cheatsheet
        )
        self.about_action = self._action("关于 XEditor", lambda: show_about(self))
        self._set_theme_checks()

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        file_menu = menu_bar.addMenu("文件(&F)")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addMenu(self.recent_menu)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.autosave_action)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("导出")
        export_menu.addAction(self.export_html_action)
        export_menu.addAction(self.export_pdf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        edit_menu = menu_bar.addMenu("编辑(&E)")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addAction(self.select_all_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)
        edit_menu.addAction(self.replace_action)

        format_menu = menu_bar.addMenu("格式(&O)")
        heading_menu = format_menu.addMenu("标题")
        for action in self.heading_actions:
            heading_menu.addAction(action)
        heading_menu.addSeparator()
        heading_menu.addAction(self.clear_heading_action)
        format_menu.addSeparator()
        format_menu.addAction(self.bold_action)
        format_menu.addAction(self.italic_action)
        format_menu.addAction(self.strike_action)
        format_menu.addAction(self.inline_code_action)
        format_menu.addAction(self.code_block_action)
        format_menu.addSeparator()
        format_menu.addAction(self.link_action)
        format_menu.addAction(self.image_action)
        format_menu.addSeparator()
        format_menu.addAction(self.bullet_action)
        format_menu.addAction(self.numbered_action)
        format_menu.addAction(self.task_action)
        format_menu.addAction(self.quote_action)
        format_menu.addSeparator()
        format_menu.addAction(self.hr_action)
        format_menu.addAction(self.table_action)
        format_menu.addAction(self.date_action)

        view_menu = menu_bar.addMenu("视图(&V)")
        view_menu.addAction(self.preview_action)
        view_menu.addAction(self.outline_action)
        view_menu.addSeparator()
        view_menu.addAction(self.sync_action)
        view_menu.addAction(self.wrap_action)
        view_menu.addAction(self.reading_action)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("主题")
        for action in self._theme_actions.values():
            theme_menu.addAction(action)
        view_menu.addSeparator()
        view_menu.addAction(self.font_action)
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_reset_action)
        view_menu.addSeparator()
        view_menu.addAction(self.fullscreen_action)

        help_menu = menu_bar.addMenu("帮助(&H)")
        help_menu.addAction(self.cheatsheet_action)
        help_menu.addAction(self.about_action)

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("工具栏", self)
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setIconSize(QSize(18, 18))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        self.toolbar.addAction(self.new_action)
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addSeparator()

        self._format_button("bold", "加粗 (Ctrl+B)", lambda: self.editor.toggle_inline("**", "加粗文字"))
        self._format_button("italic", "斜体 (Ctrl+I)", lambda: self.editor.toggle_inline("*", "斜体文字"))
        self._format_button(
            "strike", "删除线 (Ctrl+Shift+X)", lambda: self.editor.toggle_inline("~~", "删除线文字")
        )
        self._format_button("code", "行内代码 (Ctrl+E)", lambda: self.editor.toggle_inline("`", "代码"))
        self.toolbar.addAction(self.link_action)

        self.toolbar.addSeparator()
        self.toolbar.addAction(self.find_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.preview_action)
        self.toolbar.addAction(self.outline_action)
        self.toolbar.addAction(self.reading_action)

        spacer = QWidget(self.toolbar)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.theme_button = QToolButton(self.toolbar)
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setIconSize(QSize(18, 18))
        self.theme_button.clicked.connect(self._toggle_theme)
        self.toolbar.addWidget(self.theme_button)

    def _format_button(self, kind: str, tip: str, slot) -> None:
        button = QToolButton(self.toolbar)
        button.setToolTip(tip)
        button.setFixedSize(30, 30)
        button.setIconSize(QSize(20, 20))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False: slot())
        self._format_buttons.append((button, kind))
        self.toolbar.addWidget(button)

    def _build_statusbar(self) -> None:
        status = self.statusBar()
        self.position_label = QLabel("行 1, 列 1", self)
        self.counts_label = QLabel("0 字 · 0 字符", self)
        self.reading_label = QLabel("", self)
        self.encoding_label = QLabel("UTF-8", self)
        self.encoding_label.setToolTip("文件编码")
        self.brand_label = QLabel(f"{APP_NAME} v{__version__} · {__author__}", self)
        self.brand_label.setToolTip(
            f"作者：{__author__}\n联系邮箱：{__author_email__}\n版本：{__version__}"
        )
        status.addWidget(self.position_label)
        status.addWidget(self.counts_label)
        status.addWidget(self.reading_label)
        status.addPermanentWidget(self.brand_label)
        status.addPermanentWidget(self.encoding_label)
        status.showMessage("就绪", 2500)

    # ==================================================================
    # Signals / settings
    # ==================================================================
    def _connect_signals(self) -> None:
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.selectionChanged.connect(self._on_selection_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_changed)
        self.editor.document().modificationChanged.connect(self._on_modified_changed)
        self.editor.fileDropped.connect(self._open_path)
        self.editor.zoomChanged.connect(self._on_editor_zoom_changed)
        self.editor.undoAvailable.connect(self.undo_action.setEnabled)
        self.editor.redoAvailable.connect(self.redo_action.setEnabled)
        self.editor.verticalScrollBar().valueChanged.connect(self._on_editor_scrolled)

        self.find_bar.closed.connect(self._on_find_closed)

        self.preview.fileLinkClicked.connect(self._on_preview_file_link)
        self.preview.zoomChanged.connect(self._on_preview_zoom_changed)

        self.outline_panel.headingActivated.connect(self._on_heading_activated)
        self.outline_dock.visibilityChanged.connect(self._on_outline_visibility_changed)

        self.preview_action.toggled.connect(self._set_preview_visible)
        self.outline_action.toggled.connect(self._set_outline_visible)
        self.sync_action.toggled.connect(self._on_sync_toggled)
        self.wrap_action.toggled.connect(self._set_word_wrap)
        self.reading_action.toggled.connect(self._set_reading_mode)
        self.fullscreen_action.toggled.connect(self._set_fullscreen)

        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(280)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._stats_timer = QTimer(self)
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(320)
        self._stats_timer.timeout.connect(self._update_stats)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(2000)
        self._autosave_timer.timeout.connect(self._autosave)
        self.autosave_action.toggled.connect(self._on_autosave_toggled)

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    def _restore_settings(self) -> None:
        geometry = self.settings.byte_array("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter = self.settings.byte_array("splitter/state")
        if splitter is not None:
            self.splitter.restoreState(splitter)

        outline_visible = self.settings.bool("view/outline_visible", True)
        preview_visible = self.settings.bool("view/preview_visible", True)
        word_wrap = self.settings.bool("view/word_wrap", True)
        self.sync_action.setChecked(self.settings.bool("view/sync_scroll", True))
        self.wrap_action.setChecked(word_wrap)
        self.preview_action.setChecked(preview_visible)
        self.outline_action.setChecked(outline_visible)
        self.autosave_action.setChecked(self.settings.bool("files/auto_save", True))

        self.preview.setVisible(preview_visible)
        self.outline_dock.setVisible(outline_visible)
        self._set_word_wrap(word_wrap)
        self.preview.set_zoom_steps(self.settings.int("preview/zoom_steps", 0))

    def _save_settings(self) -> None:
        self.settings.set_value("window/geometry", self.saveGeometry())
        self.settings.set_value("splitter/state", self.splitter.saveState())
        self.settings.set_value("view/outline_visible", self.outline_action.isChecked())
        if self._reading_mode:
            preview_visible = self._reading_restore.get("preview", True)
        else:
            preview_visible = self.preview_action.isChecked()
        self.settings.set_value("view/preview_visible", preview_visible)
        self.settings.set_value("view/word_wrap", self.wrap_action.isChecked())
        self.settings.set_value("view/sync_scroll", self.sync_action.isChecked())
        self.settings.set_value("files/auto_save", self.autosave_action.isChecked())
        self.settings.set_value("view/outline_width", self.outline_dock.width())
        self.settings.set_value("editor/font_size", self.editor.font().pointSize())
        self.settings.sync()

    def _center_if_needed(self) -> None:
        if self.settings.byte_array("window/geometry") is not None:
            return
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    # ==================================================================
    # Theme
    # ==================================================================
    def _apply_theme(self, preference: str, rerender: bool = True) -> None:
        self._theme_preference = preference
        theme = resolve_theme(preference)
        self._theme = theme
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme)
        self.editor.set_theme(theme)
        self.highlighter.set_theme(theme, self._mono_family)
        self.preview.set_theme(theme)
        self.find_bar.set_theme(theme)
        for action, kind in self._icon_actions:
            action.setIcon(icon(kind, theme.text))
        for button, kind in self._format_buttons:
            button.setIcon(icon(kind, theme.text))
        self._update_theme_button()
        self._set_theme_checks()
        self.settings.set_value("ui/theme", preference)
        if rerender:
            self._refresh_preview()
            if self._cheat_sheet is not None and self._cheat_sheet.isVisible():
                self._cheat_sheet.close()
                self._cheat_sheet = None

    def _update_theme_button(self) -> None:
        if self._theme.is_dark:
            self.theme_button.setIcon(icon("sun", self._theme.text))
            self.theme_button.setToolTip("切换到浅色主题")
        else:
            self.theme_button.setIcon(icon("moon", self._theme.text))
            self.theme_button.setToolTip("切换到深色主题")

    def _toggle_theme(self) -> None:
        self._apply_theme("light" if self._theme.is_dark else "dark")

    def _set_theme_checks(self) -> None:
        preference = getattr(self, "_theme_preference", "system")
        for key, action in self._theme_actions.items():
            action.blockSignals(True)
            action.setChecked(key == preference)
            action.blockSignals(False)

    def _on_system_scheme_changed(self, _scheme=None) -> None:
        if self._theme_preference != "system":
            return
        theme = resolve_theme("system")
        if theme.key != self._theme.key:
            self._apply_theme("system", rerender=True)

    # ==================================================================
    # Documents
    # ==================================================================
    def _load_welcome(self) -> None:
        self._set_document_text(WELCOME_MD, None, "utf-8", "\n")
        self.editor.document().setModified(False)
        self._update_title()
        self.statusBar().showMessage("欢迎使用 XEditor", 4000)

    def _set_document_text(
        self, text: str, path: Path | None, encoding: str, newline: str
    ) -> None:
        self._preview_timer.stop()
        self._stats_timer.stop()
        self._autosave_timer.stop()
        self.find_bar.close_bar()
        self._current_path = Path(path) if path else None
        self._encoding = encoding
        self._newline = newline

        self.editor.setPlainText(text)
        self.editor.document().clearUndoRedoStacks()
        self.editor.document().setModified(False)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        self.preview.verticalScrollBar().setValue(0)

        self._update_title()
        self._update_encoding_label()
        self._update_position()
        self._update_stats()
        self._refresh_preview()

    def _new_file(self) -> None:
        if not self._maybe_save():
            return
        self._set_document_text("", None, "utf-8", "\n")
        self.editor.setFocus()
        self.statusBar().showMessage("已新建空白文档", 2500)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 Markdown 文件",
            str(self._start_directory()),
            "Markdown 文件 (*.md *.markdown *.mdown *.mkd *.txt);;所有文件 (*.*)",
        )
        if path:
            self._open_path(path)

    def open_path(self, path: str, anchor: str = "") -> bool:
        """Public entry point for the launcher / command line."""
        return self._open_path(path, anchor)

    def _open_path(self, path: str, anchor: str = "") -> bool:
        file_path = Path(path)
        try:
            if not file_path.is_file():
                self.settings.remove_recent_file(str(file_path))
                QMessageBox.warning(self, "无法打开", f"文件不存在：\n{file_path}")
                return False
            if file_path.stat().st_size > 30 * 1024 * 1024:
                QMessageBox.warning(self, "文件过大", "该文件超过 30 MB，XEditor 可能无法流畅预览。")
            if not self._maybe_save():
                return False
            data = file_path.read_bytes()
        except OSError as exc:
            QMessageBox.critical(self, "打开失败", f"无法读取文件：\n{exc}")
            return False

        if b"\x00" in data[:8192]:
            QMessageBox.warning(
                self, "无法打开", "该文件看起来是二进制文件，不能作为 Markdown 文本打开。"
            )
            return False

        text, encoding = self._decode_bytes(data)
        newline = "\r\n" if b"\r\n" in data else ("\r" if b"\r" in data else "\n")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self._set_document_text(text, file_path, encoding, newline)
        self._remember_path(file_path)
        self.editor.setFocus()
        self.statusBar().showMessage(f"已打开 {file_path.name}", 3000)
        if anchor:
            QTimer.singleShot(120, lambda: self.preview.scroll_to_anchor(anchor))
        return True

    @staticmethod
    def _decode_bytes(data: bytes) -> tuple[str, str]:
        if data.startswith(b"\xef\xbb\xbf"):
            return data.decode("utf-8-sig"), "utf-8-sig"
        for encoding in ("utf-8", "gb18030", "big5"):
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace"), "utf-8"

    def _remember_path(self, path: Path) -> None:
        self.settings.set_value("files/last_dir", str(path.parent))
        self.settings.add_recent_file(str(path))

    def _maybe_save(self) -> bool:
        if not self.editor.document().isModified():
            return True
        name = self._current_path.name if self._current_path else "未命名"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("未保存的更改")
        box.setText(f"是否保存对“{name}”的更改？")
        box.setInformativeText("如果不保存，更改将会丢失。")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.button(QMessageBox.StandardButton.Save).setText("保存")
        box.button(QMessageBox.StandardButton.Discard).setText("不保存")
        box.button(QMessageBox.StandardButton.Cancel).setText("取消")
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        if result == QMessageBox.StandardButton.Save:
            return self._save()
        if result == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _save(self) -> bool:
        if self._current_path is None:
            return self._save_as()
        return self._write_to(self._current_path)

    def _save_as(self) -> bool:
        default_name = (
            self._current_path.name
            if self._current_path
            else "未命名.md"
        )
        default_path = self._start_directory() / default_name
        path, _ = QFileDialog.getSaveFileName(
            self,
            "另存为",
            str(default_path),
            "Markdown 文件 (*.md *.markdown);;所有文件 (*.*)",
        )
        if not path:
            return False
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".md")
        old_dir = self._current_path.parent if self._current_path else None
        if not self._write_to(target):
            return False
        if old_dir != target.parent:
            self._refresh_preview()
        return True

    def _write_to(self, target: Path, quiet: bool = False) -> bool:
        text = self.editor.toPlainText()
        payload_text = text.replace("\n", self._newline)
        encoding = self._encoding
        try:
            payload = payload_text.encode(encoding)
        except UnicodeEncodeError:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("编码无法保存")
            box.setText(f"当前编码 {encoding.upper()} 无法保存文档中的部分字符。")
            box.setInformativeText("是否改用 UTF-8 编码保存？")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.button(QMessageBox.StandardButton.Yes).setText("改用 UTF-8")
            box.button(QMessageBox.StandardButton.No).setText("取消")
            if box.exec() != QMessageBox.StandardButton.Yes:
                return False
            encoding = "utf-8"
            payload = payload_text.encode(encoding)

        old_dir = self._current_path.parent if self._current_path else None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            save_file = QSaveFile(str(target))
            if not save_file.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError(save_file.errorString())
            written = save_file.write(payload)
            if written != len(payload):
                raise OSError(save_file.errorString() or "写入不完整")
            if not save_file.commit():
                raise OSError(save_file.errorString())
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", f"无法保存文件：\n{exc}")
            return False

        self._current_path = target
        self._encoding = encoding
        self.editor.document().setModified(False)
        self._remember_path(target)
        self._update_title()
        self._update_encoding_label()
        if not quiet:
            self.statusBar().showMessage(f"已保存 {target.name}", 3000)
        if old_dir != target.parent:
            self._refresh_preview()
        return True

    def _on_autosave_toggled(self, enabled: bool) -> None:
        self.settings.set_value("files/auto_save", enabled)
        if enabled and self._current_path is not None and self.editor.document().isModified():
            self._autosave_timer.start()
        else:
            self._autosave_timer.stop()
        self.statusBar().showMessage(
            "自动保存已开启（仅针对已有文件）" if enabled else "自动保存已关闭", 2500
        )

    def _autosave(self) -> None:
        if (
            not self.autosave_action.isChecked()
            or self._current_path is None
            or self._reading_mode
            or not self.editor.document().isModified()
        ):
            return
        self._write_to(self._current_path, quiet=True)

    # ==================================================================
    # Export
    # ==================================================================
    def _export_html(self) -> None:
        name = self._current_path.stem if self._current_path else "未命名"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 HTML",
            str(self._start_directory() / f"{name}.html"),
            "HTML 文件 (*.html *.htm);;所有文件 (*.*)",
        )
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".html")
        rendered = render_document(
            self.editor.toPlainText(),
            self._theme,
            base_dir=self._base_dir() or str(Path.cwd()),
            font_size=15,
            max_image_width=760,
            embed_images=True,
        )
        try:
            target.write_text(rendered.html, encoding="utf-8", newline="\n")
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", f"无法写入 HTML 文件：\n{exc}")
            return
        self._show_export_result(target, "HTML 导出完成")

    def _export_pdf(self) -> None:
        name = self._current_path.stem if self._current_path else "未命名"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 PDF",
            str(self._start_directory() / f"{name}.pdf"),
            "PDF 文件 (*.pdf);;所有文件 (*.*)",
        )
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".pdf")
        rendered = render_document(
            self.editor.toPlainText(),
            THEMES["light"],
            base_dir=self._base_dir() or str(Path.cwd()),
            font_size=15,
            max_image_width=700,
        )
        try:
            writer = QPdfWriter(str(target))
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
            writer.setResolution(96)
            document = QTextDocument()
            document.setDocumentMargin(0)
            base_dir = self._base_dir() or str(Path.cwd())
            document.setBaseUrl(QUrl.fromLocalFile(str(Path(base_dir)) + "/"))
            document.setHtml(rendered.html)
            document.print_(writer)
        except Exception as exc:  # pragma: no cover - export backend failures
            QMessageBox.critical(self, "导出失败", f"无法生成 PDF：\n{exc}")
            return
        self._show_export_result(target, "PDF 导出完成")

    def _show_export_result(self, path: Path, title: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(title)
        box.setText("文件已成功导出：")
        box.setInformativeText(str(path))
        open_button = box.addButton("打开文件", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("确定", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self.statusBar().showMessage(f"{title}：{path.name}", 3000)

    def _base_dir(self) -> str | None:
        if self._current_path is not None:
            return str(self._current_path.parent)
        return None

    def _start_directory(self) -> Path:
        saved = self.settings.text("files/last_dir", "")
        if saved:
            path = Path(saved)
            if path.is_dir():
                return path
        if self._current_path is not None:
            return self._current_path.parent
        return Path.home()

    def _show_cheatsheet(self) -> None:
        if self._cheat_sheet is not None and self._cheat_sheet.isVisible():
            self._cheat_sheet.raise_()
            self._cheat_sheet.activateWindow()
            return
        self._cheat_sheet = MarkdownCheatSheet(self._theme, self)
        self._cheat_sheet.finished.connect(self._on_cheatsheet_closed)
        self._cheat_sheet.show()
        self._cheat_sheet.raise_()

    def _on_cheatsheet_closed(self, _result: int) -> None:
        self._cheat_sheet = None

    # ==================================================================
    # Rendering / stats
    # ==================================================================
    def _on_text_changed(self) -> None:
        if hasattr(self, "_preview_timer"):
            self._preview_timer.start()
        if hasattr(self, "_stats_timer"):
            self._stats_timer.start()
        if (
            hasattr(self, "_autosave_timer")
            and self.autosave_action.isChecked()
            and self._current_path is not None
            and not self._reading_mode
        ):
            self._autosave_timer.start()

    def _on_selection_changed(self) -> None:
        if hasattr(self, "_stats_timer"):
            self._stats_timer.start()

    def _on_cursor_changed(self) -> None:
        self._update_position()
        self.outline_panel.set_current_line(self.editor.textCursor().blockNumber())

    def _on_modified_changed(self, _modified: bool) -> None:
        self._update_title()

    def _on_editor_zoom_changed(self, size: int) -> None:
        self.settings.set_value("editor/font_size", size)

    def _on_preview_zoom_changed(self, steps: int) -> None:
        self.settings.set_value("preview/zoom_steps", steps)

    def _update_title(self) -> None:
        name = self._current_path.name if self._current_path is not None else "未命名"
        modified = self.editor.document().isModified()
        self.setWindowModified(modified)
        marker = " *" if modified else ""
        self.setWindowTitle(f"{name}{marker} — {APP_NAME}")

    def _update_encoding_label(self) -> None:
        labels = {
            "utf-8": "UTF-8",
            "utf-8-sig": "UTF-8 BOM",
            "gb18030": "GB18030",
            "big5": "Big5",
        }
        encoding = labels.get(self._encoding, self._encoding.upper())
        self.encoding_label.setText(encoding)
        newline = "CRLF" if self._newline == "\r\n" else ("CR" if self._newline == "\r" else "LF")
        self.encoding_label.setToolTip(f"文件编码：{encoding}\n换行符：{newline}")

    def _update_position(self) -> None:
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        self.position_label.setText(f"行 {line}, 列 {column}")

    def _update_stats(self) -> None:
        text = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        selected = cursor.selection().toPlainText() if cursor.hasSelection() else ""
        words = self._count_words(text)
        chars = len(text)
        read_minutes = max(1, math.ceil(words / 300)) if words else 0
        if selected:
            selection_words = self._count_words(selected)
            self.counts_label.setText(
                f"选中 {selection_words:,} 字 / 共 {words:,} 字 · {chars:,} 字符"
            )
        else:
            self.counts_label.setText(f"{words:,} 字 · {chars:,} 字符")
        self.reading_label.setText(f"约 {read_minutes} 分钟阅读" if words else "")

    @staticmethod
    def _count_words(text: str) -> int:
        cjk = len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff]", text))
        latin = len(re.findall(r"[A-Za-z0-9]+(?:['’_-][A-Za-z0-9]+)*", text))
        return cjk + latin

    def _refresh_preview(self) -> None:
        self._preview_timer.stop()
        text = self.editor.toPlainText()
        base_dir = self._base_dir() or str(Path.cwd())
        toc = self.preview.set_markdown(text, base_dir)
        self.outline_panel.set_content(text, toc)
        self.outline_panel.set_current_line(self.editor.textCursor().blockNumber())
        if self.sync_action.isChecked() and self.preview.isVisible():
            first_line = self.editor.firstVisibleBlock().blockNumber()
            total = max(1, self.editor.blockCount())
            QTimer.singleShot(0, lambda l=first_line, t=total: self.preview.scroll_to_line_ratio(l, t))

    def _on_editor_scrolled(self, _value: int) -> None:
        if self._syncing or not self.sync_action.isChecked() or not self.preview.isVisible():
            return
        bar = self.editor.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        self._syncing = True
        try:
            self.preview.set_scroll_ratio(bar.value() / bar.maximum())
        finally:
            self._syncing = False

    def _on_heading_activated(self, line: int, anchor: str) -> None:
        if not self._reading_mode:
            self.editor.goto_line(line + 1)
        if self.preview.isVisible():
            if anchor:
                self.preview.scroll_to_anchor(anchor)
            else:
                total = max(1, self.editor.blockCount())
                self.preview.scroll_to_line_ratio(line, total)
        if not self._reading_mode:
            self.editor.setFocus()

    def _on_preview_file_link(self, path: str, fragment: str) -> None:
        self._open_path(path, fragment)

    # ==================================================================
    # View state
    # ==================================================================
    def _set_preview_visible(self, visible: bool) -> None:
        self.preview.setVisible(visible)
        self.settings.set_value("view/preview_visible", visible and not self._reading_mode)
        if visible:
            self._refresh_preview()

    def _set_outline_visible(self, visible: bool) -> None:
        self.outline_dock.setVisible(visible)
        self.settings.set_value("view/outline_visible", visible)

    def _on_outline_visibility_changed(self, visible: bool) -> None:
        if self._closing or not self.isVisible():
            return
        if self.outline_action.isChecked() != visible:
            self.outline_action.blockSignals(True)
            self.outline_action.setChecked(visible)
            self.outline_action.blockSignals(False)
        self.settings.set_value("view/outline_visible", visible)

    def _on_sync_toggled(self, enabled: bool) -> None:
        self.settings.set_value("view/sync_scroll", enabled)
        if enabled and self.preview.isVisible():
            bar = self.editor.verticalScrollBar()
            if bar.maximum() > 0:
                self.preview.set_scroll_ratio(bar.value() / bar.maximum())

    def _set_word_wrap(self, enabled: bool) -> None:
        self.editor.setLineWrapMode(
            self.editor.LineWrapMode.WidgetWidth
            if enabled
            else self.editor.LineWrapMode.NoWrap
        )
        self.wrap_action.blockSignals(True)
        self.wrap_action.setChecked(enabled)
        self.wrap_action.blockSignals(False)
        self.settings.set_value("view/word_wrap", enabled)

    def _set_reading_mode(self, enabled: bool) -> None:
        if enabled == self._reading_mode:
            return
        self._reading_mode = enabled
        if enabled:
            self._reading_restore = {
                "preview": self.preview_action.isChecked(),
                "toolbar": self.toolbar.isVisible(),
            }
            self.find_bar.close_bar()
            self._refresh_preview()
            self.preview.show()
            self.preview_action.blockSignals(True)
            self.preview_action.setChecked(True)
            self.preview_action.blockSignals(False)
            self.preview_action.setEnabled(False)
            self.position_label.hide()
            self.editor_container.hide()
            self.toolbar.hide()
            self.preview.setFocus(Qt.FocusReason.OtherFocusReason)
            self.statusBar().showMessage("阅读模式 · 按 Ctrl+Shift+R 退出", 4000)
        else:
            self.toolbar.setVisible(self._reading_restore.get("toolbar", True))
            self.editor_container.show()
            self.position_label.show()
            preview_visible = self._reading_restore.get("preview", True)
            self.preview.setVisible(preview_visible)
            self.preview_action.setEnabled(True)
            self.preview_action.blockSignals(True)
            self.preview_action.setChecked(preview_visible)
            self.preview_action.blockSignals(False)
            self.editor.setFocus()
            self.statusBar().showMessage("已退出阅读模式", 2000)

    def _set_fullscreen(self, enabled: bool) -> None:
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()

    def _reset_zoom(self) -> None:
        font = QFont(self.editor.font())
        font.setPointSize(11)
        self.editor.set_editor_font(font)
        self.settings.set_value("editor/font_size", 11)
        self.preview.reset_zoom()

    def _choose_font(self) -> None:
        result = QFontDialog.getFont(self.editor.font(), self, "选择编辑器字体")
        # PySide6 returns (ok, font) while some bindings return (font, ok).
        if isinstance(result[0], bool):
            accepted, font = result
        else:
            font, accepted = result
        if not accepted:
            return
        if font.pointSize() <= 0:
            font.setPointSize(11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.set_editor_font(font)
        self._mono_family = font.family()
        self.highlighter.set_theme(self._theme, self._mono_family)
        self.settings.set_value("editor/font_family", font.family())
        self.settings.set_value("editor/font_size", font.pointSize())

    def _on_find_closed(self) -> None:
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_find(self) -> None:
        if self._reading_mode:
            self.reading_action.setChecked(False)
        self.find_bar.open_find()

    def _open_replace(self) -> None:
        if self._reading_mode:
            self.reading_action.setChecked(False)
        self.find_bar.open_replace()

    # ==================================================================
    # Recent files
    # ==================================================================
    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = self.settings.recent_files()
        if not files:
            empty = self.recent_menu.addAction("（无最近文件）")
            empty.setEnabled(False)
            return
        for index, item in enumerate(files[:10], start=1):
            path = Path(item)
            label = f"{index}. {path.name}"
            action = self.recent_menu.addAction(label)
            action.setToolTip(item)
            action.setStatusTip(f"打开 {item}")
            action.triggered.connect(
                lambda checked=False, p=item: self._open_path(p)
            )
        self.recent_menu.addSeparator()
        clear_action = self.recent_menu.addAction("清除最近记录")
        clear_action.triggered.connect(self._clear_recent_files)

    def _clear_recent_files(self) -> None:
        self.settings.set_recent_files([])
        self._rebuild_recent_menu()

    # ==================================================================
    # Drag & drop / window events
    # ==================================================================
    @staticmethod
    def _first_dropped_file(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if url.isLocalFile():
                return url.toLocalFile()
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._first_dropped_file(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._first_dropped_file(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        path = self._first_dropped_file(event)
        if path:
            event.acceptProposedAction()
            self._open_path(path)
            return
        super().dropEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._dock_width_applied:
            self._dock_width_applied = True
            width = max(180, self.settings.int("view/outline_width", 230))
            self.resizeDocks(
                [self.outline_dock], [width], Qt.Orientation.Horizontal
            )

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._maybe_save():
            event.ignore()
            return
        self._closing = True
        self._save_settings()
        event.accept()
