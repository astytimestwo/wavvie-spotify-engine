from typing import Optional
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame, QProgressBar, QListWidget)
from PySide6.QtGui import QFont, QColor, QImage
from ui.theme import Theme
from ui.widgets.circular_visualizer import CircularVisualizer
from core.models import ScanConfiguration, ScanProgress, ScanResult

class DashboardPage(QWidget):
    quick_start_requested = Signal()
    cancel_scan_requested = Signal()
    view_results_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_state = "ready"
        
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
        self.btn_quick = QPushButton("Quick Scan")
        self.btn_quick.setProperty("class", "primary")
        self.btn_quick.setCursor(Qt.PointingHandCursor)
        self.btn_quick.clicked.connect(self.quick_start_requested.emit)
        header_layout.addWidget(self.btn_quick)

        self.btn_view_results = QPushButton("View Results")
        self.btn_view_results.setProperty("class", "accent")
        self.btn_view_results.setCursor(Qt.PointingHandCursor)
        self.btn_view_results.clicked.connect(self.view_results_requested.emit)
        self.btn_view_results.hide()
        header_layout.addWidget(self.btn_view_results)
        
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

        self.btn_cancel_scan = QPushButton("Cancel Scan")
        self.btn_cancel_scan.setProperty("class", "danger")
        self.btn_cancel_scan.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_scan.clicked.connect(self.cancel_scan_requested.emit)
        self.btn_cancel_scan.hide()
        pulse_title_layout.addWidget(self.btn_cancel_scan)
        
        self.pulse_subtitle = QLabel("Ready")
        self.pulse_subtitle.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 11px;")
        pulse_title_layout.addWidget(self.pulse_subtitle)
        pulse_layout.addLayout(pulse_title_layout)
        
        # Put circular visualizer in center
        self.visualizer = CircularVisualizer()
        self.visualizer.set_state("idle")
        pulse_layout.addWidget(self.visualizer, 1, Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                text-align: center;
                color: {Theme.STRONG_TEXT};
                height: 16px;
            }}
            QProgressBar::chunk {{
                background-color: {Theme.SPOTIFY_GREEN};
                border-radius: 6px;
            }}
        """)
        pulse_layout.addWidget(self.progress_bar)

        scan_meta_layout = QHBoxLayout()
        scan_meta_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_scan_metrics = QLabel("Tracks: 0  |  Collabs: 0  |  Artists: 0/0  |  Time: 0s")
        self.lbl_scan_metrics.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-family: {Theme.FONT_MONO}; font-size: 12px;")
        scan_meta_layout.addWidget(self.lbl_scan_metrics)
        scan_meta_layout.addStretch()
        self.lbl_scan_artist = QLabel("")
        self.lbl_scan_artist.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px;")
        scan_meta_layout.addWidget(self.lbl_scan_artist)
        pulse_layout.addLayout(scan_meta_layout)

        self.log_list = QListWidget()
        self.log_list.setSelectionMode(QListWidget.NoSelection)
        self.log_list.setMaximumHeight(260)
        self.log_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 16px;
                padding: 12px;
                color: {Theme.STRONG_TEXT};
                font-family: {Theme.FONT_MONO};
                font-size: 12px;
            }}
        """)
        pulse_layout.addWidget(self.log_list)
        
        layout.addWidget(self.pulse_card, 1)
        
        # Load local settings for last scan summary
        self.load_dashboard_settings()
        self.show_scan_ready()

    def load_dashboard_settings(self):
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        
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
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        settings.setValue("total_followed_artists", count)

    def show_scan_ready(self):
        self.scan_state = "ready"
        self.btn_quick.setText("Quick Scan")
        self.btn_quick.setEnabled(True)
        self.btn_view_results.hide()
        self.btn_cancel_scan.hide()
        self.pulse_subtitle.setText("Ready")
        self.visualizer.set_state("idle")
        self.visualizer.set_progress(0.0)
        self.visualizer.set_artist_image(None)
        self.progress_bar.setValue(0)
        self.lbl_scan_artist.setText("")
        self.lbl_scan_metrics.setText("Tracks: 0  |  Collabs: 0  |  Artists: 0/0  |  Time: 0s")

    def show_scan_running(self, config: ScanConfiguration):
        self.scan_state = "running"
        self.btn_quick.setText("Running")
        self.btn_quick.setEnabled(False)
        self.btn_view_results.hide()
        self.btn_cancel_scan.show()
        self.pulse_subtitle.setText("Running")
        self.visualizer.set_state("scanning")
        self.visualizer.set_progress(0.0)
        self.visualizer.set_artist_image(None)
        self.progress_bar.setValue(0)
        self.lbl_scan_artist.setText("")
        self.lbl_scan_metrics.setText("Tracks: 0  |  Collabs: 0  |  Artists: 0/0  |  Time: 0s")
        self.log_list.clear()

    def show_scan_complete(self, result: ScanResult):
        self.scan_state = "complete"
        self.btn_quick.setText("Quick Scan")
        self.btn_quick.setEnabled(True)
        self.btn_view_results.show()
        self.btn_cancel_scan.hide()
        self.pulse_subtitle.setText("Complete")
        self.visualizer.set_state("complete")
        self.visualizer.set_progress(100.0)
        self.progress_bar.setValue(100)
        self.lbl_scan_artist.setText("")
        self.lbl_scan_metrics.setText(
            f"Tracks: {len(result.tracks)}  |  "
            f"Collabs: {sum(1 for track in result.tracks if track.is_collaboration)}  |  "
            f"Artists: {result.total_artists}/{result.total_artists}  |  Complete"
        )

    def show_scan_failed(self, message: str):
        self.scan_state = "failed"
        self.btn_quick.setText("Quick Scan")
        self.btn_quick.setEnabled(True)
        self.btn_view_results.hide()
        self.btn_cancel_scan.hide()
        self.pulse_subtitle.setText("Failed")
        self.visualizer.set_state("error")
        self.lbl_scan_artist.setText("")
        if message:
            self.add_scan_log_line(f"Scan failed: {message}", Theme.ERROR)

    def show_scan_cancelled(self):
        self.scan_state = "cancelled"
        self.btn_quick.setText("Quick Scan")
        self.btn_quick.setEnabled(True)
        self.btn_view_results.hide()
        self.btn_cancel_scan.hide()
        self.pulse_subtitle.setText("Cancelled")
        self.visualizer.set_state("error")
        self.lbl_scan_artist.setText("")
        self.add_scan_log_line("Scan cancelled.", Theme.ERROR)

    def update_scan_progress(self, progress: ScanProgress):
        total = progress.total_artists
        processed = progress.processed_artists
        percentage = int((processed / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.visualizer.set_progress(percentage)
        self.pulse_subtitle.setText("Running")
        self.lbl_scan_metrics.setText(
            f"Tracks: {progress.tracks_found}  |  "
            f"Collabs: {progress.collaborations_found}  |  "
            f"Artists: {processed}/{total}  |  "
            f"Time: {int(progress.elapsed_time)}s"
        )

    def set_scan_artist(self, name: str, image: Optional[QImage] = None):
        self.lbl_scan_artist.setText(f"Scanning: {name}" if name else "")
        self.visualizer.set_artist_image(image)

    def trigger_track_discovery(self, is_collab: bool):
        self.visualizer.trigger_track_discovery(is_collab)

    def add_scan_log_line(self, message: str, color_hex: str = None):
        self.log_list.addItem(message)
        if color_hex:
            self.log_list.item(self.log_list.count() - 1).setForeground(QColor(color_hex))
        while self.log_list.count() > 80:
            self.log_list.takeItem(0)
        self.log_list.scrollToBottom()


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtext: str, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumHeight(90)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        
        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-family: {Theme.FONT_BODY}; font-size: 10px; font-weight: bold; letter-spacing: 0px;")
        layout.addWidget(self.title_lbl)
        
        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-family: Agrandir; font-size: 36px; font-weight: bold;")
        layout.addWidget(self.val_lbl)
        
        self.sub_lbl = QLabel(subtext)
        self.sub_lbl.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-family: {Theme.FONT_BODY}; font-size: 11px;")
        layout.addWidget(self.sub_lbl)

    def set_value(self, value: str):
        self.val_lbl.setText(value)
