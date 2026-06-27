from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout
from PySide6.QtGui import QFont
from ui.theme import Theme
from ui.widgets.circular_visualizer import CircularVisualizer

class DashboardPage(QWidget):
    quick_start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 1. User Header & Welcome
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.welcome_label = QLabel("Welcome back!")
        self.welcome_label.setProperty("class", "heading")
        self.welcome_label.setStyleSheet("font-size: 32px; font-family: Loubag;")
        header_layout.addWidget(self.welcome_label)
        
        header_layout.addStretch()
        
        # Quick Scan button at top-right
        self.btn_quick = QPushButton("Quick Scan →")
        self.btn_quick.setProperty("class", "primary")
        self.btn_quick.setCursor(Qt.PointingHandCursor)
        self.btn_quick.clicked.connect(self.quick_start_requested.emit)
        header_layout.addWidget(self.btn_quick)
        
        layout.addWidget(header_widget)
        
        # 2. Stats Grid
        self.stats_frame = QWidget()
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        
        self.card_artists = StatCard("Followed Artists", "0", "Artists loaded")
        self.card_prev_tracks = StatCard("Previous Discovered", "0", "Tracks found")
        self.card_last_scan = StatCard("Last Scan", "Never", "Scan date")
        
        stats_layout.addWidget(self.card_artists)
        stats_layout.addWidget(self.card_prev_tracks)
        stats_layout.addWidget(self.card_last_scan)
        
        layout.addWidget(self.stats_frame)
        
        # 3. Release Pulse Visual Module
        self.pulse_card = QFrame()
        self.pulse_card.setProperty("class", "card")
        pulse_layout = QVBoxLayout(self.pulse_card)
        pulse_layout.setContentsMargins(16, 16, 16, 16)
        pulse_layout.setSpacing(8)
        
        pulse_title_layout = QHBoxLayout()
        pulse_title = QLabel("Release Pulse")
        pulse_title.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-family: {Theme.FONT_HEADINGS}; font-size: 14px; font-weight: bold;")
        pulse_title_layout.addWidget(pulse_title)
        pulse_title_layout.addStretch()
        
        pulse_subtitle = QLabel("Idle Waveform")
        pulse_subtitle.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 11px;")
        pulse_title_layout.addWidget(pulse_subtitle)
        pulse_layout.addLayout(pulse_title_layout)
        
        # Put circular visualizer in center
        self.visualizer = CircularVisualizer()
        self.visualizer.set_state("idle")
        pulse_layout.addWidget(self.visualizer, 1, Qt.AlignCenter)
        
        layout.addWidget(self.pulse_card, 1)
        
        # Load local settings for last scan summary
        self.load_dashboard_settings()

    def load_dashboard_settings(self):
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        
        last_scan = settings.value("last_scan_date", "Never")
        prev_tracks = settings.value("last_scan_tracks", "0")
        total_artists = settings.value("total_followed_artists", "0")
        
        self.card_last_scan.set_value(str(last_scan))
        self.card_prev_tracks.set_value(str(prev_tracks))
        self.card_artists.set_value(str(total_artists))

    def update_user_info(self, display_name: str):
        if display_name:
            self.welcome_label.setText(f"Good morning, {display_name}")
        else:
            self.welcome_label.setText("Good morning")

    def update_followed_artists_count(self, count: int):
        self.card_artists.set_value(str(count))
        # Persist count
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        settings.setValue("total_followed_artists", count)


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtext: str, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumHeight(90)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-family: {Theme.FONT_BODY}; font-size: 10px; font-weight: bold; letter-spacing: -3px;")
        layout.addWidget(self.title_lbl)
        
        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-family: Agrandir; font-size: 36px; font-weight: bold;")
        layout.addWidget(self.val_lbl)
        
        self.sub_lbl = QLabel(subtext)
        self.sub_lbl.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-family: {Theme.FONT_BODY}; font-size: 11px;")
        layout.addWidget(self.sub_lbl)

    def set_value(self, value: str):
        self.val_lbl.setText(value)
