"""A record of what wavvie did, for when something needs explaining."""
import logging

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout

from ui.widgets.controls import button


class SignallingLogHandler(logging.Handler, QObject):
    log_emitted = Signal(str, int)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        self.log_emitted.emit(self.format(record), record.levelno)


class ActivityLog(QObject):
    changed = Signal()

    def __init__(self, parent=None, limit=2000):
        super().__init__(parent)
        self.lines = []
        self.limit = limit
        self.handler = SignallingLogHandler()
        self.handler.log_emitted.connect(self.append)
        logging.getLogger().addHandler(self.handler)

    @Slot(str, int)
    def append(self, message, level):
        self.lines.append(message)
        del self.lines[:-self.limit]
        self.changed.emit()

    def text(self):
        return "\n".join(self.lines)

    def detach(self):
        logging.getLogger().removeHandler(self.handler)


class ActivityLogDialog(QDialog):
    def __init__(self, log, parent=None):
        super().__init__(parent)
        self.log = log
        self.setWindowTitle("Activity log")
        self.resize(720, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setAccessibleName("Activity log")
        layout.addWidget(self.view, 1)
        actions = QHBoxLayout()
        actions.setSpacing(24)
        actions.addStretch()
        self.btn_copy = button("Copy log", "quiet", "copyLog")
        self.btn_close = button("Close", "primary", "closeLog")
        actions.addWidget(self.btn_copy)
        actions.addWidget(self.btn_close)
        layout.addLayout(actions)
        self.btn_copy.clicked.connect(self.copy)
        self.btn_close.clicked.connect(self.close)
        log.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.view.setPlainText(self.log.text() or "Nothing has happened yet.")
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def copy(self):
        QGuiApplication.clipboard().setText(self.log.text())
        self.btn_copy.setText("Copied")
        QTimer.singleShot(2000, self, lambda: self.btn_copy.setText("Copy log"))
