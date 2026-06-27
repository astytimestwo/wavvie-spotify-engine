from PySide6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from ui.theme import Theme

class Toast(QFrame):
    def __init__(self, message: str, level: str = "info", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip | Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Color based on level
        border_color = Theme.BORDER
        bg_color = Theme.SECONDARY_SURFACE
        text_color = Theme.STRONG_TEXT
        
        if level == "success":
            border_color = Theme.SPOTIFY_GREEN
            text_color = Theme.SOFT_MINT
        elif level == "error":
            border_color = Theme.ERROR
            text_color = Theme.ERROR
        elif level == "warning":
            border_color = Theme.WARNING
            text_color = Theme.WARNING
            
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QLabel {{
                color: {text_color};
                font-family: {Theme.FONT_BODY};
                font-size: 13px;
                font-weight: 500;
                background-color: transparent;
                border: none;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        self.label = QLabel(message)
        layout.addWidget(self.label)
        
        # Animation: Opacity fade in/out
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        
        # Auto close timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)

    def show_toast(self, duration_ms: int = 3000):
        self.show()
        self.anim.start()
        self.timer.start(duration_ms)
        self.position_toast()

    def position_toast(self):
        if self.parentWidget():
            # Align top right of parent
            parent_geom = self.parentWidget().geometry()
            parent_pos = self.parentWidget().mapToGlobal(QPoint(0, 0))
            
            x = parent_pos.x() + parent_geom.width() - self.width() - 24
            y = parent_pos.y() + 48
            self.move(x, y)
        self.adjustSize()

    def fade_out(self):
        self.anim.setDirection(QPropertyAnimation.Backward)
        self.anim.finished.connect(self.close)
        self.anim.start()
