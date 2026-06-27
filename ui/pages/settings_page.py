from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QGridLayout, QSpinBox, 
                               QCheckBox, QLineEdit, QComboBox)
from ui.theme import Theme

class SettingsPage(QWidget):
    disconnect_requested = Signal()
    clear_cache_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Settings")
        title.setProperty("class", "heading")
        title.setStyleSheet("font-size: 24px;")
        layout.addWidget(title)
        
        # 1. Spotify Connection Card
        conn_card = QFrame()
        conn_card.setProperty("class", "card")
        conn_layout = QVBoxLayout(conn_card)
        conn_layout.setContentsMargins(20, 20, 20, 20)
        conn_layout.setSpacing(12)
        
        conn_title = QLabel("Spotify Connection")
        conn_title.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-weight: bold; font-size: 15px;")
        conn_layout.addWidget(conn_title)
        
        self.lbl_status = QLabel("Connection status: Unknown")
        self.lbl_status.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 13px;")
        conn_layout.addWidget(self.lbl_status)
        
        self.lbl_redirect = QLabel("Redirect URI: http://127.0.0.1:8888/callback")
        self.lbl_redirect.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 11px;")
        conn_layout.addWidget(self.lbl_redirect)
        
        self.btn_disconnect = QPushButton("Disconnect Spotify Account")
        self.btn_disconnect.setProperty("class", "danger")
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.clicked.connect(self.disconnect_requested.emit)
        conn_layout.addWidget(self.btn_disconnect)
        
        layout.addWidget(conn_card)
        
        # 2. Preferences Card
        pref_card = QFrame()
        pref_card.setProperty("class", "card")
        pref_layout = QGridLayout(pref_card)
        pref_layout.setContentsMargins(20, 20, 20, 20)
        pref_layout.setSpacing(16)
        
        pref_title = QLabel("Default Preferences")
        pref_title.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-weight: bold; font-size: 15px;")
        pref_layout.addWidget(pref_title, 0, 0, 1, 2)
        
        # Cutoff Days
        pref_layout.addWidget(QLabel("Default Cutoff Period:"), 1, 0)
        self.combo_cutoff = QComboBox()
        self.combo_cutoff.addItems(["Last 7 Days", "Last 30 Days", "Last 90 Days", "Last 180 Days"])
        self.combo_cutoff.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                padding: 8px 12px;
                color: {Theme.STRONG_TEXT};
            }}
        """)
        self.combo_cutoff.currentIndexChanged.connect(self.save_settings)
        pref_layout.addWidget(self.combo_cutoff, 1, 1)
        
        # Worker count
        pref_layout.addWidget(QLabel("Default Worker Count:"), 2, 0)
        self.spin_workers = QSpinBox()
        self.spin_workers.setMinimum(1)
        self.spin_workers.setMaximum(20)
        self.spin_workers.valueChanged.connect(self.save_settings)
        pref_layout.addWidget(self.spin_workers, 2, 1)
        
        # Default Playlist Name
        pref_layout.addWidget(QLabel("Default Playlist Name:"), 3, 0)
        self.txt_playlist_name = QLineEdit()
        self.txt_playlist_name.textChanged.connect(self.save_settings)
        pref_layout.addWidget(self.txt_playlist_name, 3, 1)
        
        # Default Playlist Desc
        pref_layout.addWidget(QLabel("Default Playlist Desc:"), 4, 0)
        self.txt_playlist_desc = QLineEdit()
        self.txt_playlist_desc.textChanged.connect(self.save_settings)
        pref_layout.addWidget(self.txt_playlist_desc, 4, 1)
        
        # Checkboxes
        toggles = QHBoxLayout()
        self.chk_export = QCheckBox("Automatically Export JSON")
        self.chk_export.stateChanged.connect(self.save_settings)
        toggles.addWidget(self.chk_export)
        
        self.chk_create_pl = QCheckBox("Automatically Create Playlist")
        self.chk_create_pl.stateChanged.connect(self.save_settings)
        toggles.addWidget(self.chk_create_pl)
        
        self.chk_reduced_motion = QCheckBox("Reduced Motion Option")
        self.chk_reduced_motion.stateChanged.connect(self.save_settings)
        toggles.addWidget(self.chk_reduced_motion)
        
        pref_layout.addLayout(toggles, 5, 0, 1, 2)
        
        layout.addWidget(pref_card)
        
        # 3. Cache Management Card
        cache_card = QFrame()
        cache_card.setProperty("class", "card")
        cache_layout = QVBoxLayout(cache_card)
        cache_layout.setContentsMargins(20, 20, 20, 20)
        cache_layout.setSpacing(12)
        
        cache_title = QLabel("Cache & Storage")
        cache_title.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-weight: bold; font-size: 15px;")
        cache_layout.addWidget(cache_title)
        
        self.lbl_cache_path = QLabel("Cache File: followed_artists_cache.json")
        self.lbl_cache_path.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 13px;")
        cache_layout.addWidget(self.lbl_cache_path)
        
        self.btn_clear_cache = QPushButton("Clear Followed Artists Cache")
        self.btn_clear_cache.setCursor(Qt.PointingHandCursor)
        self.btn_clear_cache.clicked.connect(self.clear_cache_requested.emit)
        cache_layout.addWidget(self.btn_clear_cache)
        
        layout.addWidget(cache_card)
        layout.addStretch()
        
        # Load settings initially
        self.load_settings()

    def load_settings(self):
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        
        workers = settings.value("default_workers", 5, type=int)
        playlist_name = settings.value("default_playlist_name", "New Releases", type=str)
        playlist_desc = settings.value("default_playlist_desc", "New tracks from followed artists", type=str)
        auto_export = settings.value("auto_export_json", True, type=bool)
        auto_create = settings.value("auto_create_playlist", True, type=bool)
        reduced_motion = settings.value("reduced_motion", False, type=bool)
        cutoff_idx = settings.value("default_cutoff_idx", 1, type=int) # default to index 1 (30 days)
        
        self.spin_workers.setValue(workers)
        self.txt_playlist_name.setText(playlist_name)
        self.txt_playlist_desc.setText(playlist_desc)
        self.chk_export.setChecked(auto_export)
        self.chk_create_pl.setChecked(auto_create)
        self.chk_reduced_motion.setChecked(reduced_motion)
        self.combo_cutoff.setCurrentIndex(cutoff_idx)

    def save_settings(self):
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        
        settings.setValue("default_workers", self.spin_workers.value())
        settings.setValue("default_playlist_name", self.txt_playlist_name.text())
        settings.setValue("default_playlist_desc", self.txt_playlist_desc.text())
        settings.setValue("auto_export_json", self.chk_export.isChecked())
        settings.setValue("auto_create_playlist", self.chk_create_pl.isChecked())
        settings.setValue("reduced_motion", self.chk_reduced_motion.isChecked())
        settings.setValue("default_cutoff_idx", self.combo_cutoff.currentIndex())
        
        # Map indices to days
        cutoff_days_map = {0: 7, 1: 30, 2: 90, 3: 180}
        days = cutoff_days_map.get(self.combo_cutoff.currentIndex(), 30)
        settings.setValue("default_cutoff_days", days)
        
        self.settings_changed.emit()

    def update_connection_status(self, user_name: str, redirect_uri: str):
        if user_name:
            self.lbl_status.setText(f"Connection status: Connected as {user_name}")
            self.btn_disconnect.setEnabled(True)
        else:
            self.lbl_status.setText("Connection status: Not Connected")
            self.btn_disconnect.setEnabled(False)
            
        self.lbl_redirect.setText(f"Redirect URI: {redirect_uri}")
