from datetime import datetime, timedelta
from typing import Optional
from PySide6.QtCore import Qt, Signal, QDate, QTime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QGridLayout, QDateEdit, 
                               QSpinBox, QCheckBox, QLineEdit, QStackedWidget,
                               QListWidget, QProgressBar)
from PySide6.QtGui import QColor, QImage
from ui.theme import Theme
from ui.widgets.circular_visualizer import CircularVisualizer
from core.models import ScanConfiguration, ScanProgress, ScanResult

class ScanPage(QWidget):
    start_scan_requested = Signal(object)  # ScanConfiguration
    cancel_scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.stacked_widget = QStackedWidget(self)
        
        # Build views
        self.init_config_view()
        self.init_active_view()
        
        self.stacked_widget.addWidget(self.config_widget)
        self.stacked_widget.addWidget(self.active_widget)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.stacked_widget)
        
        self.total_artists_available = 0

    def set_total_artists(self, count: int):
        self.total_artists_available = count
        self.lbl_artists_count.setText(f"Followed artists found: {count}")
        self.spin_end.setMaximum(max(1, count))
        self.spin_end.setValue(count)

    def init_config_view(self):
        self.config_widget = QWidget()
        layout = QVBoxLayout(self.config_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("New Release Scan")
        title.setProperty("class", "heading")
        title.setStyleSheet("font-size: 24px;")
        layout.addWidget(title)
        
        self.lbl_artists_count = QLabel("Followed artists found: Loading...")
        self.lbl_artists_count.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_artists_count)
        
        # Configuration Card
        config_card = QFrame()
        config_card.setProperty("class", "card")
        grid = QGridLayout(config_card)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(10)
        
        # Row 0: Cutoff Date
        grid.addWidget(QLabel("Cutoff Date:"), 0, 0)
        self.date_cutoff = QDateEdit()
        self.date_cutoff.setCalendarPopup(True)
        # Default to 30 days ago
        default_date = QDate.currentDate().addDays(-30)
        self.date_cutoff.setDate(default_date)
        grid.addWidget(self.date_cutoff, 0, 1)
        
        # Row 1: Start Index
        grid.addWidget(QLabel("Start Artist Index:"), 1, 0)
        self.spin_start = QSpinBox()
        self.spin_start.setMinimum(1)
        self.spin_start.setMaximum(9999)
        self.spin_start.setValue(1)
        grid.addWidget(self.spin_start, 1, 1)
        
        # Row 2: End Index
        grid.addWidget(QLabel("End Artist Index:"), 2, 0)
        self.spin_end = QSpinBox()
        self.spin_end.setMinimum(1)
        self.spin_end.setMaximum(9999)
        self.spin_end.setValue(100)
        grid.addWidget(self.spin_end, 2, 1)
        
        # Row 3: Concurrency
        grid.addWidget(QLabel("Concurrency Workers:"), 3, 0)
        self.spin_workers = QSpinBox()
        self.spin_workers.setMinimum(1)
        self.spin_workers.setMaximum(20)
        self.spin_workers.setValue(5)
        grid.addWidget(self.spin_workers, 3, 1)
        
        # Row 4: Playlist Name
        grid.addWidget(QLabel("Playlist Name:"), 4, 0)
        self.txt_playlist_name = QLineEdit()
        self.txt_playlist_name.setText("New Releases")
        grid.addWidget(self.txt_playlist_name, 4, 1)
        
        # Row 5: Playlist Description
        grid.addWidget(QLabel("Playlist Description:"), 5, 0)
        self.txt_playlist_desc = QLineEdit()
        self.txt_playlist_desc.setText("New tracks from followed artists")
        grid.addWidget(self.txt_playlist_desc, 5, 1)
        
        # Row 6: Toggles
        toggles_layout = QHBoxLayout()
        self.chk_refresh = QCheckBox("Refresh Artist Cache")
        self.chk_export = QCheckBox("Export JSON After Scan")
        self.chk_export.setChecked(True)
        self.chk_create_playlist = QCheckBox("Create Spotify Playlist After Scan")
        self.chk_create_playlist.setChecked(True)
        
        toggles_layout.addWidget(self.chk_refresh)
        toggles_layout.addWidget(self.chk_export)
        toggles_layout.addWidget(self.chk_create_playlist)
        grid.addLayout(toggles_layout, 6, 0, 1, 2)
        
        layout.addWidget(config_card)
        
        # Start button
        self.btn_start = QPushButton("Start Release Scan")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.on_start_clicked)
        layout.addWidget(self.btn_start)
        layout.addStretch()

    def init_active_view(self):
        self.active_widget = QWidget()
        layout = QVBoxLayout(self.active_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header Status
        status_header = QWidget()
        sh_layout = QHBoxLayout(status_header)
        sh_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_status = QLabel("Scanning followed artists...")
        self.lbl_status.setProperty("class", "heading")
        self.lbl_status.setStyleSheet("font-size: 20px;")
        sh_layout.addWidget(self.lbl_status)
        sh_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel Scan")
        self.btn_cancel.setProperty("class", "danger")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.cancel_scan_requested.emit)
        sh_layout.addWidget(self.btn_cancel)
        layout.addWidget(status_header)
        
        # Circular visualizer
        self.visualizer = CircularVisualizer()
        layout.addWidget(self.visualizer, 0, Qt.AlignCenter)
        
        # Progress Bar & Numbers
        progress_card = QFrame()
        progress_card.setProperty("class", "card")
        pc_layout = QVBoxLayout(progress_card)
        pc_layout.setContentsMargins(18, 14, 18, 14)
        pc_layout.setSpacing(8)
        
        self.progress_bar = QProgressBar()
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
        pc_layout.addWidget(self.progress_bar)
        
        # Summary row
        metrics_layout = QHBoxLayout()
        self.lbl_metrics = QLabel("Tracks: 0  |  Collabs: 0  |  Artists: 0/0  |  Time: 0s")
        self.lbl_metrics.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-family: {Theme.FONT_MONO}; font-size: 12px;")
        metrics_layout.addWidget(self.lbl_metrics)
        metrics_layout.addStretch()
        
        self.lbl_current_artist = QLabel("")
        self.lbl_current_artist.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px;")
        metrics_layout.addWidget(self.lbl_current_artist)
        
        pc_layout.addLayout(metrics_layout)
        layout.addWidget(progress_card)
        
        # Live activity stream Console log
        console_title = QLabel("LIVE LOG CONSOLE")
        console_title.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 10px; font-weight: bold; letter-spacing: 0px;")
        layout.addWidget(console_title)
        
        self.log_list = QListWidget()
        self.log_list.setSelectionMode(QListWidget.NoSelection)
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
        layout.addWidget(self.log_list, 1)

    def on_start_clicked(self):
        # Gather inputs
        config = ScanConfiguration(
            start_index=self.spin_start.value(),
            end_index=self.spin_end.value(),
            cutoff_date_str=self.date_cutoff.date().toString("yyyy-MM-dd"),
            playlist_name=self.txt_playlist_name.text(),
            playlist_description=self.txt_playlist_desc.text(),
            worker_count=self.spin_workers.value(),
            export_json=self.chk_export.isChecked(),
            create_playlist_auto=self.chk_create_playlist.isChecked(),
            refresh_cache=self.chk_refresh.isChecked()
        )
        
        # Check validation
        if not config.playlist_name and config.create_playlist_auto:
            # Simple fallback validation
            return
            
        self.start_scan_requested.emit(config)

    def show_config(self):
        self.stacked_widget.setCurrentIndex(0)
        self.visualizer.set_state("idle")

    def show_active(self):
        self.stacked_widget.setCurrentIndex(1)
        self.log_list.clear()
        self.progress_bar.setValue(0)
        self.lbl_metrics.setText("Tracks: 0  |  Collabs: 0  |  Artists: 0/0  |  Time: 0s")
        self.lbl_current_artist.setText("")
        self.visualizer.set_state("scanning")
        self.visualizer.set_progress(0.0)

    def add_log_line(self, message: str, color_hex: str = None):
        item = message
        self.log_list.addItem(item)
        if color_hex:
            self.log_list.item(self.log_list.count() - 1).setForeground(QColor(color_hex))
        self.log_list.scrollToBottom()

    def update_scan_progress(self, progress: ScanProgress):
        # Update metrics
        total = progress.total_artists
        processed = progress.processed_artists
        
        self.lbl_metrics.setText(
            f"Tracks: {progress.tracks_found}  |  "
            f"Collabs: {progress.collaborations_found}  |  "
            f"Artists: {processed}/{total}  |  "
            f"Time: {int(progress.elapsed_time)}s"
        )
        
        if total > 0:
            percentage = (processed / total) * 100
            self.progress_bar.setValue(int(percentage))
            self.visualizer.set_progress(percentage)

    def set_current_artist(self, name: str, image: Optional[QImage] = None):
        self.lbl_current_artist.setText(f"Scanning: {name}" if name else "")
        self.visualizer.set_artist_image(image)

    def trigger_track_discovery(self, is_collab: bool):
        self.visualizer.trigger_track_discovery(is_collab)
