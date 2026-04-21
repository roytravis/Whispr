import os
import re
import ctypes
import threading
import fitz  # PyMuPDF — for reading PDF files
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QTextBrowser, QPushButton, QLabel,
    QFileDialog, QSizeGrip, QFrame,
    QSystemTrayIcon, QMenu, QRubberBand, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QBuffer, QIODeviceBase, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QAction, QScreen


# Windows API constant for hiding window from screen capture
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class ScreenshotOverlay(QWidget):
    """Fullscreen transparent overlay for selecting a screen region to capture."""

    screenshot_taken = pyqtSignal(bytes)  # emits PNG bytes of captured region
    cancelled = pyqtSignal()

    def __init__(self, full_screenshot: QPixmap):
        super().__init__()
        self._origin = QPoint()
        self._full_screenshot = full_screenshot

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Cover all screens
        virtual_geo = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geo)

        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._dimmed = self._create_dimmed(full_screenshot)

    @staticmethod
    def _create_dimmed(pixmap: QPixmap) -> QPixmap:
        dimmed = pixmap.copy()
        painter = QPainter(dimmed)
        painter.fillRect(dimmed.rect(), QColor(0, 0, 0, 120))
        painter.setPen(QColor("#cdd6f4"))
        painter.setFont(QFont("Segoe UI", 14))
        painter.drawText(dimmed.rect(), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                         "\n  Drag to select area  |  ESC to cancel  ")
        painter.end()
        return dimmed

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._dimmed)
        painter.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._rubber_band.setGeometry(QRect(self._origin, QSize()))
            self._rubber_band.show()

    def mouseMoveEvent(self, event):
        if self._rubber_band.isVisible():
            self._rubber_band.setGeometry(QRect(self._origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._rubber_band.isVisible():
            self._rubber_band.hide()
            rect = QRect(self._origin, event.position().toPoint()).normalized()
            if rect.width() > 10 and rect.height() > 10:
                # Crop from the original (un-dimmed) full screenshot
                cropped = self._full_screenshot.copy(rect)
                buf = QBuffer()
                buf.open(QIODeviceBase.OpenModeFlag.WriteOnly)
                cropped.save(buf, "PNG")
                self.screenshot_taken.emit(bytes(buf.data()))
                buf.close()
            else:
                self.cancelled.emit()
            self.close()


class OverlayWindow(QWidget):
    """Main overlay window — always-on-top, draggable, hidden from screen share."""

    # Signals for thread-safe UI updates from background threads
    ai_response_signal = pyqtSignal(str)
    ai_thinking_signal = pyqtSignal()
    transcript_signal = pyqtSignal(str)
    interim_signal = pyqtSignal(str, str)  # (final_text, interim_text)
    status_signal = pyqtSignal(str)

    EDGE_MARGIN = 6  # pixels from edge to trigger resize

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._resize_edge = None
        self._pre_maximize_geometry = None

        self._screenshot_overlay = None

        # External callbacks (set by main.py)
        self.on_ask_ai = None
        self.on_clear = None
        self.on_screenshot_solve = None  # callback(image_bytes)
        self._code_blocks = []  # plain text of code blocks for copy feature

        self._init_window()
        self._init_ui()
        self._init_tray_icon()
        self._connect_signals()
        self._hide_from_screen_share()

    # ── Window Setup ──────────────────────────────────────────

    def _init_window(self):
        self.setWindowTitle("Parakeet Clone")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool  # Hides from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(320, 400)
        self.resize(420, 520)

        # Position at bottom-right of screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 30,
                  screen.height() - self.height() - 60)

    def _hide_from_screen_share(self):
        """Use Win32 API to hide window from screen capture / sharing."""
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            print(f"Warning: Could not hide from screen share: {e}")

    # ── System Tray Icon ─────────────────────────────────────

    def _init_tray_icon(self):
        """Create a system tray icon for restore-from-minimize."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._create_tray_icon())
        self.tray_icon.setToolTip("Parakeet Clone")

        # Tray context menu
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_from_tray)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # Single click on tray icon restores the window
        self.tray_icon.activated.connect(self._on_tray_activated)

    @staticmethod
    def _create_tray_icon():
        """Generate a simple colored icon (no external file needed)."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#89b4fa"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#1e1e2e"))
        font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P")
        painter.end()
        return QIcon(pixmap)

    def _minimize_to_tray(self):
        """Hide the window and show the tray icon."""
        self.hide()
        self.tray_icon.show()

    def _restore_from_tray(self):
        """Restore the window from the tray."""
        self.tray_icon.hide()
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_from_tray(self):
        """Quit the application from the tray menu."""
        self.tray_icon.hide()
        self.close()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # single click
            self._restore_from_tray()

    # ── UI Construction ───────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet(self._build_stylesheet())

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Title bar
        root_layout.addWidget(self._build_title_bar())

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._build_assistant_tab()
        self._build_cv_tab()
        self._build_jd_tab()
        root_layout.addWidget(self.tabs, stretch=1)

        # Resize grip (bottom-right corner)
        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 2, 2)
        grip_layout.addStretch()
        grip_layout.addWidget(QSizeGrip(self))
        root_layout.addLayout(grip_layout)

    def _build_title_bar(self):
        bar = QFrame()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(36)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 8, 0)

        title = QLabel("Parakeet Clone")
        title.setObjectName("titleLabel")
        layout.addWidget(title)
        layout.addStretch()

        # Minimize button
        btn_min = QPushButton("\u2013")  # en-dash as minimize icon
        btn_min.setObjectName("titleBtn")
        btn_min.setFixedSize(28, 28)
        btn_min.clicked.connect(self._minimize_to_tray)
        layout.addWidget(btn_min)

        # Maximize / Restore button
        self.btn_max = QPushButton("\u25A1")  # □ square as maximize icon
        self.btn_max.setObjectName("titleBtn")
        self.btn_max.setFixedSize(28, 28)
        self.btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.btn_max)

        # Close button
        btn_close = QPushButton("\u2715")
        btn_close.setObjectName("closeTitleBtn")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

        return bar

    # ── Tab: Assistant ────────────────────────────────────────

    def _build_assistant_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Status indicator
        self.status_label = QLabel("Status: Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        # AI response area
        self.ai_output = QTextBrowser()
        self.ai_output.setReadOnly(True)
        self.ai_output.setOpenLinks(False)
        self.ai_output.anchorClicked.connect(self._on_anchor_clicked)
        self.ai_output.setPlaceholderText(
            "AI responses will appear here.\n\n"
            "1. Start a meeting/interview\n"
            "2. Press Ctrl+Enter or click 'Ask AI'\n"
            "3. Get instant suggestions based on your CV, JD & conversation"
        )
        layout.addWidget(self.ai_output, stretch=1)

        # Live transcript preview
        transcript_label = QLabel("Live Transcript (last 5 min)")
        transcript_label.setObjectName("sectionLabel")
        layout.addWidget(transcript_label)

        self.transcript_preview = QTextEdit()
        self.transcript_preview.setReadOnly(True)
        self.transcript_preview.setMaximumHeight(100)
        self.transcript_preview.setPlaceholderText("Listening for audio...")
        layout.addWidget(self.transcript_preview)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_ask = QPushButton("Ask AI  (Ctrl+Enter)")
        self.btn_ask.setObjectName("primaryBtn")
        self.btn_ask.clicked.connect(self._on_ask_clicked)
        btn_layout.addWidget(self.btn_ask)

        self.btn_screenshot = QPushButton("Screenshot  (Ctrl+Shift+S)")
        self.btn_screenshot.setObjectName("screenshotBtn")
        self.btn_screenshot.clicked.connect(self.start_screenshot)
        btn_layout.addWidget(self.btn_screenshot)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("secondaryBtn")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.btn_clear)

        layout.addLayout(btn_layout)

        self.tabs.addTab(tab, "Assistant")

    # ── Tab: CV ───────────────────────────────────────────────

    def _build_cv_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.cv_status = QLabel("No CV")
        self.cv_status.setObjectName("statusLabel")
        layout.addWidget(self.cv_status)

        self.cv_text = QTextEdit()
        self.cv_text.setPlaceholderText("Paste your CV here or load from file...")
        layout.addWidget(self.cv_text, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_load = QPushButton("Load File")
        btn_load.setObjectName("secondaryBtn")
        btn_load.clicked.connect(lambda: self._load_file(self.cv_text, "cv.txt"))
        btn_layout.addWidget(btn_load)

        btn_save = QPushButton("Save")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(lambda: self._save_file(self.cv_text, "cv.txt", "CV"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        self.tabs.addTab(tab, "CV")

        # Auto-load existing CV
        self._auto_load_file(self.cv_text, "cv.txt", "CV")

    # ── Tab: Job Description ──────────────────────────────────

    def _build_jd_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.jd_status = QLabel("No JD")
        self.jd_status.setObjectName("statusLabel")
        layout.addWidget(self.jd_status)

        self.jd_text = QTextEdit()
        self.jd_text.setPlaceholderText("Paste the Job Description here or load from file...")
        layout.addWidget(self.jd_text, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_load = QPushButton("Load File")
        btn_load.setObjectName("secondaryBtn")
        btn_load.clicked.connect(lambda: self._load_file(self.jd_text, "jd.txt"))
        btn_layout.addWidget(btn_load)

        btn_save = QPushButton("Save")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(lambda: self._save_file(self.jd_text, "jd.txt", "JD"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        self.tabs.addTab(tab, "Job Desc")

        # Auto-load existing JD
        self._auto_load_file(self.jd_text, "jd.txt", "JD")

    # ── Signal Connections ────────────────────────────────────

    def _connect_signals(self):
        self.ai_response_signal.connect(self._display_ai_response)
        self.ai_thinking_signal.connect(self._display_thinking)
        self.transcript_signal.connect(self._update_transcript_preview)
        self.interim_signal.connect(self._update_transcript_with_interim)
        self.status_signal.connect(self._update_status)

    # ── Slots (thread-safe via signals) ───────────────────────

    # ── Keyword sets for syntax highlighting (no external deps) ──

    _KW = {
        "python": r'\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|yield|lambda|pass|break|continue|raise|and|or|not|in|is|None|True|False|self|async|await|print)\b',
        "javascript": r'\b(function|const|let|var|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|new|this|class|extends|import|export|from|default|async|await|yield|typeof|instanceof|null|undefined|true|false|console|require)\b',
        "typescript": r'\b(function|const|let|var|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|new|this|class|extends|import|export|from|default|async|await|yield|typeof|instanceof|null|undefined|true|false|console|require|interface|type|enum|implements|private|public|protected|readonly|static|abstract)\b',
        "java": r'\b(public|private|protected|static|final|abstract|class|interface|extends|implements|import|package|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|throws|new|this|super|void|int|long|double|float|boolean|char|String|null|true|false|System)\b',
        "cpp": r'\b(include|define|int|long|double|float|char|void|bool|class|struct|public|private|protected|virtual|override|return|if|else|for|while|do|switch|case|break|continue|try|catch|throw|new|delete|this|nullptr|true|false|const|static|auto|using|namespace|std|cout|cin|endl|template|typename)\b',
        "go": r'\b(func|package|import|return|if|else|for|range|switch|case|break|continue|defer|go|select|chan|map|struct|interface|type|var|const|nil|true|false|fmt|err|string|int|bool|error|make|append|len)\b',
        "rust": r'\b(fn|let|mut|const|if|else|for|while|loop|match|return|use|mod|pub|struct|enum|impl|trait|where|self|Self|super|crate|async|await|move|ref|type|true|false|None|Some|Ok|Err|println|vec|String|i32|u32|f64|bool|usize)\b',
        "sql": r'\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|ALTER|DROP|INDEX|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|NULL|PRIMARY|KEY|FOREIGN|REFERENCES|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|AS|DISTINCT|COUNT|SUM|AVG|MAX|MIN|LIKE|IN|BETWEEN|EXISTS|UNION|ALL|CASE|WHEN|THEN|ELSE|END|INTEGER|TEXT|BOOLEAN|DEFAULT|AUTOINCREMENT|IF)\b',
    }

    @staticmethod
    def _html_escape(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _highlight_code(self, code, lang):
        """Apply syntax highlighting to code using regex — VS Code-like colors."""
        escaped = self._html_escape(code)

        # Pick keyword pattern based on language, fall back to a generic set
        lang_lower = (lang or "").lower().strip()
        alias_map = {"py": "python", "js": "javascript", "ts": "typescript",
                      "c++": "cpp", "c": "cpp", "golang": "go", "rs": "rust"}
        lang_key = alias_map.get(lang_lower, lang_lower)
        kw_pattern = self._KW.get(lang_key)

        # Placeholder system to prevent regex interference between passes
        _ph_list = []
        def _ph(match, color, italic=False):
            idx = len(_ph_list)
            style = f'color:{color}'
            if italic:
                style += ';font-style:italic'
            _ph_list.append(f'<span style="{style}">{match.group(0)}</span>')
            return f'\x00PH{idx}\x00'

        # 1. Triple-quoted strings / docstrings (must come before single/double)
        escaped = re.sub(
            r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\')',
            lambda m: _ph(m, '#a6e3a1'), escaped)

        # 2. Single / double quoted strings and template literals
        escaped = re.sub(
            r'("[^\"\n]*"|\x27[^\x27\n]*\x27|`[^`]*`)',
            lambda m: _ph(m, '#a6e3a1'), escaped)

        # 3. Comments (// and #)
        escaped = re.sub(
            r'(//.*?$|#.*?$)',
            lambda m: _ph(m, '#6c7086', italic=True),
            escaped, flags=re.MULTILINE)

        # 4. Numbers
        escaped = re.sub(
            r'\b(\d+\.?\d*)\b',
            r'<span style="color:#fab387">\1</span>', escaped)

        # 5. Keywords
        if kw_pattern:
            escaped = re.sub(
                kw_pattern,
                r'<span style="color:#cba6f7;font-weight:bold">\1</span>', escaped)

        # 6. Decorators / annotations (@something)
        escaped = re.sub(
            r'(@\w+)',
            r'<span style="color:#f9e2af">\1</span>', escaped)

        # Restore placeholders
        for i, html in enumerate(_ph_list):
            escaped = escaped.replace(f'\x00PH{i}\x00', html)

        return escaped

    def _render_markdown(self, text):
        """Convert markdown to styled HTML with syntax-highlighted code blocks. No external deps."""
        parts = re.split(r'(```\w*\n.*?```)', text, flags=re.DOTALL)
        html_parts = []

        for part in parts:
            m = re.match(r'^```(\w*)\n(.*?)```$', part, flags=re.DOTALL)
            if m:
                lang, code = m.group(1), m.group(2).rstrip('\n')
                block_idx = len(self._code_blocks)
                self._code_blocks.append(code)
                lang_display = self._html_escape(lang or "code")
                highlighted = self._highlight_code(code, lang)

                # Generate line numbers
                num_lines = code.count('\n') + 1
                num_w = len(str(num_lines))
                line_nums = '\n'.join(str(i).rjust(num_w) for i in range(1, num_lines + 1))

                ps = ('margin:0;white-space:pre-wrap;font-family:Cascadia Code,Consolas,'
                      'Courier New,monospace;font-size:12px;line-height:1.5')
                html_parts.append(
                    # Header bar
                    f'<table cellspacing="0" cellpadding="0" width="100%" style="margin-top:8px">'
                    f'<tr>'
                    f'<td style="background:#11111b;padding:6px 12px;border:1px solid #313244">'
                    f'<span style="color:#6c7086;font-size:10px">{lang_display}</span></td>'
                    f'<td style="background:#11111b;padding:6px 12px;border:1px solid #313244;'
                    f'border-left:none;text-align:right">'
                    f'<a href="copy://{block_idx}" style="color:#89b4fa;font-size:10px;'
                    f'text-decoration:none">\U0001f4cb Copy</a></td></tr>'
                    # Code body with line numbers
                    f'<tr><td colspan="2" style="padding:0;border:1px solid #313244;'
                    f'border-top:none;background:#181825">'
                    f'<table cellspacing="0" cellpadding="0" width="100%"><tr>'
                    f'<td style="vertical-align:top;padding:10px 0 10px 10px;'
                    f'border-right:1px solid #313244">'
                    f'<pre style="{ps};color:#6c7086;text-align:right;'
                    f'padding-right:10px">{line_nums}</pre></td>'
                    f'<td style="vertical-align:top;padding:10px 10px 10px 12px">'
                    f'<pre style="{ps};color:#cdd6f4">{highlighted}</pre></td>'
                    f'</tr></table></td></tr></table>'
                )
            else:
                # Process non-code text as simple markdown
                lines = part.split('\n')
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        html_parts.append('<br>')
                    elif stripped.startswith('### '):
                        html_parts.append(f'<h3 style="color:#89b4fa;margin:8px 0 4px 0;font-size:13px">{self._html_escape(stripped[4:])}</h3>')
                    elif stripped.startswith('## '):
                        html_parts.append(f'<h2 style="color:#89b4fa;margin:8px 0 4px 0;font-size:14px">{self._html_escape(stripped[3:])}</h2>')
                    elif stripped.startswith('# '):
                        html_parts.append(f'<h1 style="color:#89b4fa;margin:8px 0 4px 0;font-size:15px">{self._html_escape(stripped[2:])}</h1>')
                    elif stripped.startswith('- ') or stripped.startswith('* '):
                        content = self._inline_format(stripped[2:])
                        html_parts.append(f'<div style="margin:2px 0;padding-left:12px">&#8226; {content}</div>')
                    elif re.match(r'^\d+\.\s', stripped):
                        content = self._inline_format(re.sub(r'^\d+\.\s', '', stripped))
                        num = re.match(r'^(\d+)', stripped).group(1)
                        html_parts.append(f'<div style="margin:2px 0;padding-left:12px">{num}. {content}</div>')
                    else:
                        html_parts.append(f'<div style="margin:3px 0">{self._inline_format(stripped)}</div>')

        body = '\n'.join(html_parts)
        return f"""<html><head><style>
            body {{ font-family: 'Segoe UI', sans-serif; font-size: 12px; color: #cdd6f4;
                    background-color: #11111b; margin: 4px; padding: 0; }}
        </style></head><body>{body}</body></html>"""

    def _inline_format(self, text):
        """Handle bold, italic, inline code within a line."""
        escaped = self._html_escape(text)
        # Inline code `...`
        escaped = re.sub(r'`([^`]+)`',
            r'<code style="background:#181825;padding:1px 4px;border-radius:3px;font-family:Consolas,monospace;font-size:11px;color:#a6e3a1">\1</code>', escaped)
        # Bold **...**
        escaped = re.sub(r'\*\*(.+?)\*\*', r'<b style="color:#f9e2af">\1</b>', escaped)
        # Italic *...*
        escaped = re.sub(r'\*(.+?)\*', r'<i style="color:#a6e3a1">\1</i>', escaped)
        return escaped

    def _on_anchor_clicked(self, url):
        """Handle clicks on internal links (e.g., copy:// for code blocks)."""
        if url.scheme() == "copy":
            try:
                block_idx = int(url.host())
                if 0 <= block_idx < len(self._code_blocks):
                    QApplication.clipboard().setText(self._code_blocks[block_idx])
                    self.status_signal.emit("Code copied to clipboard \u2713")
            except (ValueError, IndexError):
                pass

    def _display_ai_response(self, response):
        self._code_blocks = []
        self.ai_output.clear()
        self.ai_output.setHtml(self._render_markdown(response))
        self.ai_output.verticalScrollBar().setValue(0)
        self.btn_ask.setEnabled(True)
        self.btn_ask.setText("Ask AI  (Ctrl+Enter)")

    def _display_thinking(self):
        self.btn_ask.setEnabled(False)
        self.btn_ask.setText("Thinking...")

    def _update_transcript_preview(self, text):
        self.transcript_preview.setPlainText(text)
        self.transcript_preview.verticalScrollBar().setValue(
            self.transcript_preview.verticalScrollBar().maximum()
        )

    def _update_transcript_with_interim(self, final_text, interim_text):
        html = ""
        if final_text:
            html += f'<span style="color: #cdd6f4;">{final_text}</span>'
        if interim_text:
            if final_text:
                html += "<br>"
            html += f'<span style="color: #6c7086; font-style: italic;">{interim_text}...</span>'
        self.transcript_preview.setHtml(html)
        self.transcript_preview.verticalScrollBar().setValue(
            self.transcript_preview.verticalScrollBar().maximum()
        )

    def _update_status(self, status):
        self.status_label.setText(f"Status: {status}")

    # ── Button Handlers ───────────────────────────────────────

    def _on_ask_clicked(self):
        self.transcript_preview.clear()
        if self.on_ask_ai:
            self.on_ask_ai()

    def _on_clear_clicked(self):
        # Show confirmation dialog before clearing
        msg = QMessageBox(self)
        msg.setWindowTitle("Clear Conversation")
        msg.setText("Are you sure you want to clear everything?")
        msg.setInformativeText(
            "This will reset all conversation history, transcript, and AI responses. "
            "A new interview session will start."
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 12px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
        """)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.ai_output.clear()
            self.transcript_preview.clear()
            self.status_label.setText("Status: Ready — New Session")
            if self.on_clear:
                self.on_clear()

    # ── Screenshot Capture ───────────────────────────────────

    def start_screenshot(self):
        """Hide overlay, capture full screen, show selection overlay."""
        self.hide()
        # Small delay to let the window fully hide before capturing
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._do_screenshot_capture)

    def _do_screenshot_capture(self):
        screen = QApplication.primaryScreen()
        full_pixmap = screen.grabWindow(0)

        self._screenshot_overlay = ScreenshotOverlay(full_pixmap)
        self._screenshot_overlay.screenshot_taken.connect(self._on_screenshot_taken)
        self._screenshot_overlay.cancelled.connect(self._on_screenshot_cancelled)
        self._screenshot_overlay.showFullScreen()

    def _on_screenshot_taken(self, image_bytes: bytes):
        self._screenshot_overlay = None
        self.show()
        self.activateWindow()
        self.raise_()
        self.tabs.setCurrentIndex(0)  # switch to Assistant tab

        if self.on_screenshot_solve:
            self.ai_thinking_signal.emit()
            self.on_screenshot_solve(image_bytes)

    def _on_screenshot_cancelled(self):
        self._screenshot_overlay = None
        self.show()
        self.activateWindow()
        self.raise_()

    # ── File I/O ──────────────────────────────────────────────

    def _load_file(self, text_edit, default_save_name):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "Text Files (*.txt);;PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return

        try:
            if path.lower().endswith(".pdf"):
                content = self._read_pdf(path)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            text_edit.setPlainText(content)
            # Also auto-save to the persistent file
            self._save_file(text_edit, default_save_name,
                            default_save_name.replace(".txt", "").upper())
        except Exception as e:
            text_edit.setPlainText(f"Error loading file: {e}")

    @staticmethod
    def _read_pdf(path):
        """Extract text from a PDF file using PyMuPDF."""
        doc = fitz.open(path)
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages).strip()

    def _save_file(self, text_edit, filename, label):
        content = text_edit.toPlainText().strip()
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            if label == "CV":
                self.cv_status.setText("CV Loaded \u2713")
                self.cv_status.setStyleSheet("color: #4CAF50;")
            elif label == "JD":
                self.jd_status.setText("JD Loaded \u2713")
                self.jd_status.setStyleSheet("color: #4CAF50;")
        except Exception as e:
            print(f"Error saving {filename}: {e}")

    def _auto_load_file(self, text_edit, filename, label):
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    text_edit.setPlainText(content)
                    if label == "CV":
                        self.cv_status.setText("CV Loaded \u2713")
                        self.cv_status.setStyleSheet("color: #4CAF50;")
                    elif label == "JD":
                        self.jd_status.setText("JD Loaded \u2713")
                        self.jd_status.setStyleSheet("color: #4CAF50;")
            except Exception:
                pass

    # ── Maximize / Restore ─────────────────────────────────────

    def _toggle_maximize(self):
        if self._pre_maximize_geometry:
            # Restore
            self.setGeometry(self._pre_maximize_geometry)
            self._pre_maximize_geometry = None
            self.btn_max.setText("\u25A1")  # □
        else:
            # Maximize to available screen area
            self._pre_maximize_geometry = self.geometry()
            screen = QApplication.primaryScreen().availableGeometry()
            self.setGeometry(screen)
            self.btn_max.setText("\u2752")  # ❒ overlapping squares as restore icon

    # ── Edge detection for resize ────────────────────────────

    def _get_resize_edge(self, pos):
        """Return a tuple of edges (left, top, right, bottom) hit by pos."""
        if self._pre_maximize_geometry:
            return None  # no resize when maximized
        m = self.EDGE_MARGIN
        rect = self.rect()
        left = pos.x() < m
        right = pos.x() > rect.width() - m
        top = pos.y() < m
        bottom = pos.y() > rect.height() - m
        if left or right or top or bottom:
            return (left, top, right, bottom)
        return None

    @staticmethod
    def _edge_to_cursor(edge):
        left, top, right, bottom = edge
        if (left and top) or (right and bottom):
            return Qt.CursorShape.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    # ── Dragging & Resizing (frameless window) ───────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        edge = self._get_resize_edge(event.position().toPoint())
        if edge:
            self._resize_edge = edge
            self._resize_origin = event.globalPosition().toPoint()
            self._resize_geom = self.geometry()
        else:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._resize_edge and event.buttons() == Qt.MouseButton.LeftButton:
            self._perform_resize(event.globalPosition().toPoint())
            event.accept()
            return
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        # Hover — update cursor shape
        edge = self._get_resize_edge(event.position().toPoint())
        if edge:
            self.setCursor(self._edge_to_cursor(edge))
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = None
        self.unsetCursor()

    def mouseDoubleClickEvent(self, event):
        """Double-click on title bar area to maximize / restore."""
        if event.position().toPoint().y() <= 36:
            self._toggle_maximize()

    def _perform_resize(self, global_pos):
        left, top, right, bottom = self._resize_edge
        dx = global_pos.x() - self._resize_origin.x()
        dy = global_pos.y() - self._resize_origin.y()
        g = self._resize_geom
        new_x, new_y = g.x(), g.y()
        new_w, new_h = g.width(), g.height()
        min_w, min_h = self.minimumWidth(), self.minimumHeight()

        if right:
            new_w = max(g.width() + dx, min_w)
        if bottom:
            new_h = max(g.height() + dy, min_h)
        if left:
            delta = min(dx, g.width() - min_w)
            new_x = g.x() + delta
            new_w = g.width() - delta
        if top:
            delta = min(dy, g.height() - min_h)
            new_y = g.y() + delta
            new_h = g.height() - delta

        self.setGeometry(new_x, new_y, new_w, new_h)

    # ── Stylesheet ────────────────────────────────────────────

    @staticmethod
    def _build_stylesheet():
        return """
        QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: "Segoe UI", sans-serif;
            font-size: 13px;
        }

        #titleBar {
            background-color: #181825;
            border-bottom: 1px solid #313244;
        }

        #titleLabel {
            color: #cdd6f4;
            font-weight: bold;
            font-size: 13px;
        }

        #titleBtn {
            background: transparent;
            color: #a6adc8;
            border: none;
            border-radius: 4px;
            font-size: 16px;
        }
        #titleBtn:hover {
            background-color: #313244;
        }

        #closeTitleBtn {
            background: transparent;
            color: #a6adc8;
            border: none;
            border-radius: 4px;
            font-size: 14px;
        }
        #closeTitleBtn:hover {
            background-color: #f38ba8;
            color: #1e1e2e;
        }

        QTabWidget::pane {
            border: none;
            background-color: #1e1e2e;
        }

        QTabBar::tab {
            background-color: #181825;
            color: #a6adc8;
            padding: 8px 16px;
            border: none;
            border-bottom: 2px solid transparent;
        }
        QTabBar::tab:selected {
            color: #89b4fa;
            border-bottom: 2px solid #89b4fa;
        }
        QTabBar::tab:hover {
            color: #cdd6f4;
            background-color: #313244;
        }

        QTextEdit {
            background-color: #11111b;
            color: #cdd6f4;
            border: 1px solid #313244;
            border-radius: 6px;
            padding: 8px;
            font-size: 12px;
        }

        #statusLabel {
            color: #a6adc8;
            font-size: 11px;
            padding: 2px 0;
        }

        #sectionLabel {
            color: #a6adc8;
            font-size: 11px;
            font-weight: bold;
            padding-top: 4px;
        }

        #primaryBtn {
            background-color: #89b4fa;
            color: #1e1e2e;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 13px;
        }
        #primaryBtn:hover {
            background-color: #b4d0fb;
        }
        #primaryBtn:disabled {
            background-color: #45475a;
            color: #6c7086;
        }

        #screenshotBtn {
            background-color: #a6e3a1;
            color: #1e1e2e;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 12px;
        }
        #screenshotBtn:hover {
            background-color: #c6f0c1;
        }
        #screenshotBtn:disabled {
            background-color: #45475a;
            color: #6c7086;
        }

        #secondaryBtn {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
        }
        #secondaryBtn:hover {
            background-color: #45475a;
        }

        QSizeGrip {
            width: 12px;
            height: 12px;
        }
        """
