from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """Single-line catalog text with a readable overflow indicator and full tooltip."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.full_text = text
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):
        self.full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.refresh_text()

    def refresh_text(self):
        super().setText(self.fontMetrics().elidedText(self.full_text, Qt.ElideRight,
                                                    max(0, self.contentsRect().width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_text()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_text()
