import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QGridLayout
from PySide6.QtGui import QFont, QPixmap
from ui.theme import Theme
from ui.resources import resource_path
from main import load_environment

class AuthPage(QWidget):
    auth_requested = Signal()
    recheck_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 60, 40, 60)
        self.main_layout.setAlignment(Qt.AlignCenter)
        
        # 1. Logo area
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedSize(280, 104)
        logo_pixmap = QPixmap(str(resource_path("wavvie_wordmark_white.png")))
        self.logo_label.setPixmap(logo_pixmap.scaled(280, 104, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.main_layout.addWidget(self.logo_label, 0, Qt.AlignCenter)
        
        # 2. Heading
        self.heading_label = QLabel("Your followed artists, filtered properly.")
        self.heading_label.setAlignment(Qt.AlignCenter)
        self.heading_label.setStyleSheet(f"""
            color: {Theme.STRONG_TEXT};
            font-family: {Theme.FONT_HEADINGS};
            font-size: 22px;
            font-weight: bold;
            margin-bottom: 12px;
        """)
        self.main_layout.addWidget(self.heading_label)
        
        # 3. Subtitle / Explanation
        self.sub_label = QLabel("Discover new albums, singles, EPs, and collaborations from artists you follow. Skip trashy compilations and ghost producer credits automatically.")
        self.sub_label.setAlignment(Qt.AlignCenter)
        self.sub_label.setWordWrap(True)
        self.sub_label.setMaximumWidth(550)
        self.sub_label.setStyleSheet(f"""
            color: {Theme.SECONDARY_TEXT};
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 40px;
        """)
        self.main_layout.addWidget(self.sub_label)
        
        # 4. Connection State Frame
        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.content_frame)
        
        # Connect button & Setup card slots
        self.btn_connect = None
        self.setup_card = None
        
        self.update_ui_state()

    def update_ui_state(self):
        # Refresh env variables
        load_environment()
        
        client_id = os.getenv('SPOTIPY_CLIENT_ID')
        client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
        redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')
        
        # Clear current content layout
        for i in reversed(range(self.content_layout.count())): 
            widget = self.content_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
                
        if client_id and client_secret:
            # Credentials exist, show normal Connect button
            self.show_connect_view(redirect_uri)
        else:
            # Missing credentials, show setup card
            self.show_setup_view(client_id, client_secret, redirect_uri)

    def show_connect_view(self, redirect_uri: str):
        button_text = "Connected" if self.is_connected else "Connect Spotify Account"
        self.btn_connect = QPushButton(button_text)
        self.btn_connect.setProperty("class", "primary")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.setMinimumSize(240, 50)
        self.btn_connect.setEnabled(not self.is_connected)
        if self.is_connected:
            self.btn_connect.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Theme.POPPY};
                    border: 1px solid {Theme.POPPY};
                    color: {Theme.STRONG_TEXT};
                    border-radius: 16px;
                    font-family: {Theme.FONT_BODY};
                    font-weight: 800;
                }}
            """)
        else:
            self.btn_connect.clicked.connect(self.auth_requested.emit)
        
        self.content_layout.addWidget(self.btn_connect, 0, Qt.AlignCenter)
        
        status_label = QLabel(f"Redirect URI status: Listening on {redirect_uri}")
        status_label.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px; margin-top: 16px;")
        status_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(status_label)
        
        privacy_label = QLabel("Credentials remain local inside your environment variables (.env file).")
        privacy_label.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 12px; margin-top: 4px;")
        privacy_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(privacy_label)

    def show_setup_view(self, client_id, client_secret, redirect_uri):
        self.setup_card = QFrame()
        self.setup_card.setProperty("class", "card")
        self.setup_card.setFixedWidth(550)
        self.setup_card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.ELEVATED_SURFACE};
                border: 1px solid {Theme.ERROR};
                border-radius: 20px;
            }}
        """)
        
        setup_layout = QVBoxLayout(self.setup_card)
        setup_layout.setContentsMargins(24, 24, 24, 24)
        setup_layout.setSpacing(12)
        
        title = QLabel("Configuration Required")
        title.setStyleSheet(f"color: {Theme.ERROR}; font-family: {Theme.FONT_HEADINGS}; font-size: 18px; font-weight: bold;")
        setup_layout.addWidget(title)
        
        desc = QLabel("Your Spotify developer credentials are missing or incomplete. Please create a `.env` file in the application folder with the following variables:")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-size: 13px; line-height: 1.5;")
        setup_layout.addWidget(desc)
        
        # Grid of variables status
        grid = QWidget()
        grid_layout = QGridLayout(grid)
        grid_layout.setContentsMargins(0, 8, 0, 8)
        grid_layout.setSpacing(10)
        
        vars_check = [
            ("SPOTIPY_CLIENT_ID", bool(client_id)),
            ("SPOTIPY_CLIENT_SECRET", bool(client_secret)),
            ("SPOTIPY_REDIRECT_URI", bool(redirect_uri))
        ]
        
        for row, (name, exists) in enumerate(vars_check):
            name_label = QLabel(name)
            name_label.setStyleSheet(f"font-family: {Theme.FONT_MONO}; font-size: 12px; color: {Theme.STRONG_TEXT};")
            
            status = QLabel("✓ Configured" if exists else "✗ Missing")
            status.setStyleSheet(f"color: {Theme.SPOTIFY_GREEN if exists else Theme.ERROR}; font-weight: bold; font-size: 12px;")
            
            grid_layout.addWidget(name_label, row, 0)
            grid_layout.addWidget(status, row, 1)
            
        setup_layout.addWidget(grid)
        
        # Example copy card
        example_box = QFrame()
        example_box.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.APP_BG};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
            }}
        """)
        example_layout = QVBoxLayout(example_box)
        example_layout.setContentsMargins(14, 14, 14, 14)
        
        example_text = QLabel(
            "SPOTIPY_CLIENT_ID='your_client_id'\n"
            "SPOTIPY_CLIENT_SECRET='your_client_secret'\n"
            "SPOTIPY_REDIRECT_URI='http://127.0.0.1:8888/callback'"
        )
        example_text.setStyleSheet(f"font-family: {Theme.FONT_MONO}; font-size: 11px; color: {Theme.SECONDARY_TEXT};")
        example_layout.addWidget(example_text)
        
        setup_layout.addWidget(example_box)
        
        # Recheck button
        btn_recheck = QPushButton("Recheck Configuration")
        btn_recheck.setProperty("class", "primary")
        btn_recheck.setCursor(Qt.PointingHandCursor)
        btn_recheck.setMinimumHeight(40)
        btn_recheck.clicked.connect(self.recheck_requested.emit)
        setup_layout.addWidget(btn_recheck)
        
        self.content_layout.addWidget(self.setup_card)

    def set_connecting(self, connecting: bool):
        if self.btn_connect:
            self.btn_connect.setEnabled(not connecting)
            self.btn_connect.setText("Connecting Spotify..." if connecting else "Connect Spotify Account")

    def set_connected(self, connected: bool):
        self.is_connected = connected
        self.update_ui_state()
