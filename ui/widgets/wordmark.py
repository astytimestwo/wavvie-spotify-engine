"""The wavvie wordmark, drawn from its vector outline so it stays sharp at any size or display scale."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ui.resources import resource_path


class Wordmark(QWidget):
    def __init__(self, height, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(str(resource_path("wavvie_wordmark.svg")), self)
        artwork = self.renderer.defaultSize()
        self.aspect = artwork.width() / artwork.height()
        self.setFixedSize(round(height * self.aspect), height)
        self.setAccessibleName("wavvie")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.renderer.render(painter, QRectF(0, 0, self.height() * self.aspect, self.height()))
