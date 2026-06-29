from typing import Optional
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QImage, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel, QWidget, QHBoxLayout
from ui.theme import Theme
from ui.resources import resource_path

class NavButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 10px;
                padding: 8px 12px;
                color: {Theme.SECONDARY_TEXT};
                font-family: {Theme.FONT_BODY};
                font-size: 12px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: rgba(29, 36, 48, 0.65);
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
        self.setFixedWidth(188)
        self.setStyleSheet(f"""
            QFrame#Sidebar {{
                background-color: {Theme.ELEVATED_SURFACE};
                border-right: 1px solid {Theme.BORDER};
                border-top-left-radius: 22px;
                border-bottom-left-radius: 22px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(6)
        
        # 1. Logo area
        logo_text = QLabel(self)
        logo_text.setAlignment(Qt.AlignCenter)
        logo_text.setFixedSize(150, 52)
        logo_pixmap = QPixmap(str(resource_path("wavvie_wordmark_white.png")))
        logo_text.setPixmap(logo_pixmap.scaled(150, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(logo_text, 0, Qt.AlignHCenter)
        layout.addSpacing(14)
        
        # 2. Navigation items
        nav_items = [
            ("Home", 1),
            ("New Release Scan", 2),
            ("Results", 3),
            ("Activity", 4),
            ("Settings", 5),
        ]
        
        self.button_group = []
        self.button_page_indexes = []
        for label, page_index in nav_items:
            btn = NavButton(label)
            layout.addWidget(btn)
            btn.clicked.connect(lambda checked, idx=page_index: self.on_nav_clicked(idx))
            self.button_group.append(btn)
            self.button_page_indexes.append(page_index)
            
        # Select first page by default
        self.button_group[0].setChecked(True)
        
        layout.addSpacing(12)

        self.tip_card = QFrame()
        self.tip_card.setObjectName("TipCard")
        self.tip_card.setMinimumHeight(170)
        self.tip_card.setStyleSheet(f"""
            QFrame#TipCard {{
                background-color: rgba(8, 10, 13, 0.35);
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)
        tip_layout = QVBoxLayout(self.tip_card)
        tip_layout.setContentsMargins(14, 14, 14, 14)
        tip_layout.setSpacing(8)

        self.tip_label = QLabel("wavvie tip")
        self.tip_label.setStyleSheet(f"""
            color: {Theme.STRONG_TEXT};
            font-family: {Theme.FONT_HEADINGS};
            font-size: 17px;
            font-weight: 800;
        """)
        tip_layout.addWidget(self.tip_label)

        self.tip_body = QLabel()
        self.tip_body.setWordWrap(True)
        self.tip_body.setStyleSheet(f"""
            color: {Theme.SECONDARY_TEXT};
            font-family: {Theme.FONT_BODY};
            font-size: 13px;
            line-height: 1.45;
        """)
        tip_layout.addWidget(self.tip_body)
        layout.addWidget(self.tip_card)

        self.tips = [
            ("Cleaner finds", "wavvie skips compilation clutter and duplicate releases before they hit your playlist."),
            ("Scan window", "Use the artist index range to test a smaller slice before running through everyone you follow."),
            ("Local first", "Credentials stay in your local .env file; the app only talks to Spotify during auth, scans, and playlist creation."),
            ("Collab aware", "Featured roles are kept separate so guest spots do not drown out main-artist releases."),
        ]
        self.tip_index = 0
        self.update_tip()
        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self.next_tip)
        self.tip_timer.start(9000)

        layout.addStretch()
        
        # 3. User profile indicator at bottom
        self.profile_widget = QFrame()
        self.profile_widget.setObjectName("ProfileWidget")
        self.profile_widget.setStyleSheet(f"""
            QFrame#ProfileWidget {{
                background-color: rgba(8, 10, 13, 0.35);
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)
        self.profile_layout = QHBoxLayout(self.profile_widget)
        self.profile_layout.setContentsMargins(8, 8, 8, 8)
        self.profile_layout.setSpacing(10)
        
        # Circle Avatar (custom widget or label with drawing override)
        self.avatar_label = AvatarLabel()
        self.profile_layout.addWidget(self.avatar_label, 0, Qt.AlignVCenter)
        
        # Name
        self.name_label = QLabel("Not Connected")
        self.name_label.setStyleSheet(f"""
            color: {Theme.STRONG_TEXT};
            font-family: {Theme.FONT_BODY};
            font-weight: 700;
            font-size: 11px;
        """)
        self.name_label.setWordWrap(True)
        self.profile_layout.addWidget(self.name_label, 1, Qt.AlignVCenter)
        
        layout.addWidget(self.profile_widget)

    def on_nav_clicked(self, selected_idx):
        for page_index, btn in zip(self.button_page_indexes, self.button_group):
            btn.setChecked(page_index == selected_idx)
        self.nav_changed.emit(selected_idx)

    def set_active_index(self, index):
        for page_index, btn in zip(self.button_page_indexes, self.button_group):
            btn.setChecked(page_index == index)

    def update_user_profile(self, name: str, image: Optional[QImage] = None):
        connected = bool(name and name.lower() != "not connected")
        self.name_label.setText(name if connected else "Not connected")
        self.avatar_label.set_avatar(image, name)
        self.set_status("Connected" if connected else "Not connected")

    def set_status(self, status: str):
        self.current_status = status.replace("Status:", "").strip()

    def update_tip(self):
        title, body = self.tips[self.tip_index]
        self.tip_label.setText(title)
        self.tip_body.setText(body)

    def next_tip(self):
        self.tip_index = (self.tip_index + 1) % len(self.tips)
        self.update_tip()

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
