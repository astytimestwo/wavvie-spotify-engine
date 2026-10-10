"""The one moving thing in wavvie: a line that ripples over the share of the check already done."""
import math

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ui.theme import Theme


class WaveLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.progress = 0.0
        self.phase = 0.0
        self.active = False
        self.reduced_motion = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)

    def set_progress(self, fraction):
        self.progress = max(0.0, min(1.0, float(fraction)))
        self.update()

    def set_active(self, active):
        self.active = active
        self.sync_timer()
        self.update()

    def set_reduced_motion(self, enabled):
        self.reduced_motion = enabled
        self.sync_timer()
        self.update()

    def sync_timer(self):
        if self.active and self.isVisible() and not self.reduced_motion:
            self.timer.start(40)
        else:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def advance(self):
        self.phase = (self.phase + 0.35) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        middle = self.height() / 2
        done = self.width() * max(self.progress, 0.04 if self.active else 0.0)
        painter.setPen(QPen(QColor(Theme.LINE), 2))
        painter.drawLine(QPointF(done, middle), QPointF(self.width(), middle))
        if done <= 0:
            return
        path = QPainterPath()
        path.moveTo(0, middle + 5 * math.sin(-self.phase))
        x = 0.0
        while x < done:
            x = min(done, x + 2.0)
            path.lineTo(x, middle + 5 * math.sin(x / 14.0 - self.phase))
        painter.setPen(QPen(QColor(Theme.SUN), 2.5))
        painter.drawPath(path)
