import logging
from PySide6.QtCore import Qt, QObject, Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QComboBox, QLineEdit, QFrame, QLabel
from PySide6.QtGui import QFont, QGuiApplication
from ui.theme import Theme

class SignallingLogHandler(logging.Handler, QObject):
    log_emitted = Signal(str, int)  # message, level

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        msg = self.format(record)
        self.log_emitted.emit(msg, record.levelno)


class ActivityPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("System Activity Log")
        title.setProperty("class", "heading")
        title.setStyleSheet("font-size: 24px;")
        header.addWidget(title)
        
        header.addStretch()
        
        # Copy Actions
        self.btn_copy_all = QPushButton("Copy All")
        self.btn_copy_all.setCursor(Qt.PointingHandCursor)
        self.btn_copy_all.clicked.connect(self.copy_all)
        header.addWidget(self.btn_copy_all)
        
        self.btn_clear = QPushButton("Clear Log")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_log)
        header.addWidget(self.btn_clear)
        
        layout.addLayout(header)
        
        # Toolbar filters
        toolbar = QHBoxLayout()
        
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter logs... (type to search)")
        self.txt_filter.textChanged.connect(self.refilter_logs)
        toolbar.addWidget(self.txt_filter, 1)
        
        self.combo_level = QComboBox()
        self.combo_level.addItems(["All Levels", "Info", "Warning", "Error", "Debug"])
        self.combo_level.currentIndexChanged.connect(self.refilter_logs)
        self.combo_level.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                padding: 8px 12px;
                color: {Theme.STRONG_TEXT};
            }}
        """)
        toolbar.addWidget(self.combo_level)
        
        layout.addLayout(toolbar)
        
        # Log Text Box
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont(Theme.FONT_MONO, 10))
        self.txt_log.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 18px;
                color: {Theme.STRONG_TEXT};
                padding: 12px;
            }}
        """)
        layout.addWidget(self.txt_log, 1)
        
        # Store full log cache for filtering
        self.all_log_records: list[tuple[str, int]] = []
        
        # Wire standard library logging to this page
        self.handler = SignallingLogHandler()
        self.handler.log_emitted.connect(self.append_log_record)
        
        # Add to root logger to capture all application logs
        logging.getLogger().addHandler(self.handler)

    @Slot(str, int)
    def append_log_record(self, formatted_msg: str, level: int):
        self.all_log_records.append((formatted_msg, level))
        self.refilter_logs()

    def clear_log(self):
        self.all_log_records.clear()
        self.txt_log.clear()

    def copy_all(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.txt_log.toPlainText())

    def refilter_logs(self):
        filter_text = self.txt_filter.text().lower()
        filter_level = self.combo_level.currentIndex()
        
        # Level mapping: ["All Levels", "Info", "Warning", "Error", "Debug"]
        level_map = {
            1: logging.INFO,
            2: logging.WARNING,
            3: logging.ERROR,
            4: logging.DEBUG
        }
        
        filtered_lines = []
        for msg, lvl in self.all_log_records:
            # Check level
            if filter_level != 0:
                target_level = level_map[filter_level]
                if target_level == logging.ERROR and lvl < logging.ERROR:
                    continue
                elif target_level == logging.WARNING and lvl != logging.WARNING and lvl != logging.ERROR:
                    # Show warnings and errors for Warning filter
                    if lvl < logging.WARNING:
                        continue
                elif target_level == logging.INFO and lvl < logging.INFO:
                    continue
                elif target_level == logging.DEBUG and lvl < logging.DEBUG:
                    continue
            
            # Check text
            if filter_text and filter_text not in msg.lower():
                continue
                
            filtered_lines.append(msg)
            
        self.txt_log.setPlainText("\n".join(filtered_lines))
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
