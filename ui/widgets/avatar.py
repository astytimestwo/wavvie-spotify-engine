"""Round account picture, or the account's initial when Spotify has no picture."""
from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from ui.theme import Theme


class Avatar(QWidget):
    def __init__(self, size=30, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.image: Optional[QImage] = None
        self.initial = ""

    def set_user(self, name, image=None):
        self.initial = (name or "").strip()[:1].upper()
        self.image = image
        self.setToolTip(name or "")
        self.setAccessibleName(f"Signed in as {name}" if name else "Not signed in")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(QRectF(self.rect()))
        painter.setClipPath(clip)
        if self.image is not None and not self.image.isNull():
            # Draw straight from the full-size picture so high-density displays get every pixel.
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            side = min(self.image.width(), self.image.height())
            square = QRectF((self.image.width() - side) / 2, (self.image.height() - side) / 2, side, side)
            painter.drawImage(QRectF(self.rect()), self.image, square)
            return
        painter.fillRect(self.rect(), QColor(Theme.RAISED))
        font = painter.font()
        font.setFamily(Theme.FONT_BODY)
        font.setPixelSize(max(10, int(self.height() * 0.45)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(Theme.FOAM))
        painter.drawText(self.rect(), Qt.AlignCenter, self.initial)
