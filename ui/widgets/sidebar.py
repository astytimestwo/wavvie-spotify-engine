from typing import Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QImage, QPainterPath
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel, QWidget, QHBoxLayout, QSpacerItem, QSizePolicy
from ui.theme import Theme

class NavButton(QPushButton):
    def __init__(self, text, icon_text="", parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                color: {Theme.SECONDARY_TEXT};
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: rgba(29, 36, 48, 0.5);
                color: {Theme.STRONG_TEXT};
            }}
            QPushButton:checked {{
                background-color: rgba(139, 115, 255, 0.15);
                color: {Theme.STRONG_TEXT};
                font-weight: bold;
            }}
        """)

class Sidebar(QFrame):
    nav_changed = Signal(int)  # index of page

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)
        self.setStyleSheet(f"""
            QFrame#Sidebar {{
                background-color: {Theme.ELEVATED_SURFACE};
                border-right: 1px solid {Theme.BORDER};
                border-top-left-radius: 26px;
                border-bottom-left-radius: 26px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(12)
        
        # 1. Logo area
        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 16)
        logo_layout.setSpacing(8)
        
        # Draw waveform logo icon using drawing or simple text
        logo_text = QLabel("WAVEFEED")
        logo_text.setStyleSheet(f"""
            color: {Theme.CYAN_ACCENT};
            font-family: {Theme.FONT_HEADINGS};
            font-size: 20px;
            font-weight: bold;
            letter-spacing: -3px;
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        
        layout.addWidget(logo_widget)
        
        # 2. Navigation items
        self.buttons = [
            NavButton("Home"),
            NavButton("New Release Scan"),
            NavButton("Results"),
            NavButton("Activity"),
            NavButton("Settings")
        ]
        
        self.button_group = []
        for i, btn in enumerate(self.buttons):
            layout.addWidget(btn)
            btn.clicked.connect(lambda checked, idx=i: self.on_nav_clicked(idx))
            self.button_group.append(btn)
            
        # Select first page by default
        self.button_group[0].setChecked(True)
        
        layout.addStretch()
        
        # 3. User profile indicator at bottom
        self.profile_widget = QWidget()
        self.profile_layout = QHBoxLayout(self.profile_widget)
        self.profile_layout.setContentsMargins(4, 8, 4, 8)
        self.profile_layout.setSpacing(12)
        
        # Circle Avatar (custom widget or label with drawing override)
        self.avatar_label = AvatarLabel()
        self.profile_layout.addWidget(self.avatar_label)
        
        # Name
        self.name_label = QLabel("Not Connected")
        self.name_label.setStyleSheet(f"""
            color: {Theme.STRONG_TEXT};
            font-weight: 500;
            font-size: 13px;
        """)
        self.profile_layout.addWidget(self.name_label)
        
        layout.addWidget(self.profile_widget)

    def on_nav_clicked(self, selected_idx):
        for i, btn in enumerate(self.button_group):
            btn.setChecked(i == selected_idx)
        self.nav_changed.emit(selected_idx)

    def set_active_index(self, index):
        if 0 <= index < len(self.button_group):
            self.on_nav_clicked(index)

    def update_user_profile(self, name: str, image: Optional[QImage] = None):
        self.name_label.setText(name if name else "Spotify User")
        self.avatar_label.set_avatar(image, name)

class AvatarLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.image: Optional[QImage] = None
        self.initials = "?"
        
    def set_avatar(self, image: Optional[QImage], name: str):
        self.image = image
        if name:
            words = name.split()
            self.initials = "".join([w[0].upper() for w in words[:2]])
        else:
            self.initials = "SU"
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.save()
        
        rect = self.rect()
        path = QPainterPath()
        path.addEllipse(rect)
        
        painter.setClipPath(path)
        
        if self.image and not self.image.isNull():
            # Draw QImage
            scaled = self.image.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawImage(rect, scaled)
        else:
            # Draw initials on gradient background
            painter.setPen(Qt.NoPen)
            # Simple gradient from violet to cyan
            grad = QColor(Theme.VIOLET_ACCENT)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(rect)
            
            painter.setPen(QPen(QColor(Theme.STRONG_TEXT)))
            font = painter.font()
            font.setFamily(Theme.FONT_HEADINGS)
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, self.initials)
            
        # Draw clean border outline
        painter.restore()
        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(0, 0, 31, 31)
