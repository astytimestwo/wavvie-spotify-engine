"""A low tide along the bottom of each page: three calm waves in the palette's teals."""
import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from ui.theme import Theme


class Tide(QWidget):
    """Scroll content that paints a low tide along its bottom edge.

    Short pages see it at the foot of the window; long ones reach it after their last row. Pages keep
    HEIGHT pixels clear at the bottom, so nothing is ever drawn over it.
    """
    HEIGHT = 112
    # colour, crest height above the bottom edge, swell, wavelength, phase; farthest first
    LAYERS = ((Theme.SURFACE, 92, 10, 620, 0.4),
              (Theme.SHALLOW, 60, 8, 430, 2.6),
              (Theme.RAISED, 30, 6, 300, 1.2))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bottom = self.height()
        for colour, crest, swell, wavelength, phase in self.LAYERS:
            path = QPainterPath(QPointF(0, bottom))
            for x in range(0, self.width() + 8, 6):
                angle = 2 * math.pi * x / wavelength + phase
                path.lineTo(x, bottom - crest + swell * math.sin(angle) + 0.35 * swell * math.sin(2.7 * angle + 1.3))
            path.lineTo(self.width(), bottom)
            path.closeSubpath()
            painter.fillPath(path, QColor(colour))
