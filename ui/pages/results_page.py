from typing import List, Dict, Optional
import os
from PySide6.QtCore import Qt, Signal, QUrl, QRectF, QSignalBlocker, QSize, QTimer, QPoint
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QLineEdit, QListWidget, 
                               QListWidgetItem, QComboBox, QCheckBox, QSplitter,
                               QTextEdit, QSizePolicy, QDialog)
from PySide6.QtGui import QImage, QPixmap, QDesktopServices, QPainter, QColor, QBrush, QRadialGradient
from ui.theme import Theme
from ui.widgets.elided_label import ElidedLabel
from core.models import Track

def extract_dominant_color(qimage: QImage) -> QColor:
    if qimage.isNull():
        return QColor(Theme.VIOLET_ACCENT)
    scaled = qimage.scaled(10, 10, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    r_sum, g_sum, b_sum = 0, 0, 0
    count = 100
    for x in range(10):
        for y in range(10):
            pixel = scaled.pixelColor(x, y)
            r_sum += pixel.red()
            g_sum += pixel.green()
            b_sum += pixel.blue()
    return QColor(int(r_sum / count), int(g_sum / count), int(b_sum / count))

class TrackItemWidget(QWidget):
    checked_changed = Signal(bool)

    def __init__(self, track: Track, parent=None):
        super().__init__(parent)
        self.track = track
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # 1. Checkbox
        self.chk = QCheckBox()
        self.chk.setAccessibleName(f"Select {track.track_name} by {', '.join(track.all_artists)}")
        self.chk.setChecked(True)
        self.chk.stateChanged.connect(lambda state: self.checked_changed.emit(state == 2))
        layout.addWidget(self.chk)
        
        # 2. Artwork image (will be loaded by parent page controller)
        self.lbl_art = QLabel()
        self.lbl_art.setFixedSize(48, 48)
        self.lbl_art.setStyleSheet(f"background-color: {Theme.SECONDARY_SURFACE}; border-radius: 8px;")
        layout.addWidget(self.lbl_art)
        
        # 3. Track details
        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(2)
        
        self.lbl_title = ElidedLabel(track.track_name)
        self.lbl_title.setTextFormat(Qt.PlainText)
        self.lbl_title.setToolTip(track.track_name)
        self.lbl_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_title.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-weight: bold; font-size: 13px;")
        self.lbl_artist = ElidedLabel(", ".join(track.all_artists))
        self.lbl_artist.setTextFormat(Qt.PlainText)
        self.lbl_artist.setToolTip(", ".join(track.all_artists))
        self.lbl_artist.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_artist.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 11px;")
        
        details_layout.addWidget(self.lbl_title)
        details_layout.addWidget(self.lbl_artist)
        layout.addWidget(details, 1)
        
        # 4. Album name
        self.lbl_album = QLabel(track.album_name)
        self.lbl_album.setTextFormat(Qt.PlainText)
        self.lbl_album.setToolTip(track.album_name)
        self.lbl_album.hide()
        self.lbl_album.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 11px;")
        
        # 5. Badges
        # Album type
        self.lbl_type = QLabel(track.album_type.upper())
        self.lbl_type.setAlignment(Qt.AlignCenter)
        self.lbl_type.setFixedSize(65, 20)
        
        type_color = Theme.MUTED_TEXT
        if track.album_type == 'album':
            type_color = Theme.VIOLET_ACCENT
        elif track.album_type == 'single':
            type_color = Theme.CYAN_ACCENT
        elif track.album_type == 'ep':
            type_color = Theme.WARNING
        self.lbl_type.setStyleSheet(f"""
            border: 1px solid {type_color}; 
            color: {type_color}; 
            border-radius: 10px; 
            font-size: 9px; 
            font-weight: bold;
        """)
        layout.addWidget(self.lbl_type)
        
        # Role
        self.lbl_role = QLabel(track.performer_role.upper())
        self.lbl_role.setAlignment(Qt.AlignCenter)
        self.lbl_role.setFixedSize(75, 20)
        role_color = Theme.SPOTIFY_GREEN if track.performer_role == 'main' else Theme.ERROR
        self.lbl_role.setStyleSheet(f"""
            border: 1px solid {role_color}; 
            color: {role_color}; 
            border-radius: 10px; 
            font-size: 9px; 
            font-weight: bold;
        """)
        layout.addWidget(self.lbl_role)
        
        # Release date
        self.lbl_date = QLabel(track.release_date)
        self.lbl_date.setFixedWidth(80)
        self.lbl_date.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-family: {Theme.FONT_MONO}; font-size: 11px;")
        layout.addWidget(self.lbl_date)

    def set_artwork(self, image: QImage):
        if not image.isNull():
            pix = QPixmap.fromImage(image.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_art.setPixmap(pix)


class DetailPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self.setStyleSheet(f"""
            QFrame#DetailPanel {{
                background-color: {Theme.ELEVATED_SURFACE};
                border-left: 1px solid {Theme.BORDER};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(16)
        
        self.ambient_color = QColor(0, 0, 0, 0)
        
        # Large artwork
        self.lbl_large_art = QLabel()
        self.lbl_large_art.setFixedSize(200, 200)
        self.lbl_large_art.setAlignment(Qt.AlignCenter)
        self.lbl_large_art.setStyleSheet(f"background-color: {Theme.SECONDARY_SURFACE}; border-radius: 16px;")
        layout.addWidget(self.lbl_large_art, 0, Qt.AlignCenter)
        
        # Text details
        self.lbl_title = QLabel("Select a Track")
        self.lbl_title.setTextFormat(Qt.PlainText)
        self.lbl_title.setProperty("class", "heading")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("font-size: 18px;")
        layout.addWidget(self.lbl_title)
        
        self.lbl_artists = QLabel("")
        self.lbl_artists.setTextFormat(Qt.PlainText)
        self.lbl_artists.setWordWrap(True)
        self.lbl_artists.setAlignment(Qt.AlignCenter)
        self.lbl_artists.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px;")
        layout.addWidget(self.lbl_artists)
        
        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {Theme.BORDER}; max-height: 1px; border: none;")
        layout.addWidget(line)
        
        # Metadata fields
        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        self.meta_text.setFrameStyle(QFrame.NoFrame)
        self.meta_text.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px; font-family: {Theme.FONT_BODY}; background: transparent;")
        layout.addWidget(self.meta_text, 1)
        
        # Spotify link
        self.btn_spotify = QPushButton("Open in Spotify")
        self.btn_spotify.setProperty("class", "primary")
        self.btn_spotify.setCursor(Qt.PointingHandCursor)
        self.btn_spotify.setEnabled(False)
        self.btn_spotify.clicked.connect(self.open_spotify_link)
        layout.addWidget(self.btn_spotify)
        
        self.current_track: Optional[Track] = None

    def set_track(self, track: Track, artwork: Optional[QImage]):
        self.current_track = track
        
        self.lbl_title.setText(track.track_name)
        self.lbl_artists.setText(", ".join(track.all_artists))
        
        # Set large artwork
        if artwork and not artwork.isNull():
            pix = QPixmap.fromImage(artwork.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_large_art.setPixmap(pix)
            self.ambient_color = extract_dominant_color(artwork)
        else:
            self.lbl_large_art.clear()
            self.lbl_large_art.setText("No Art")
            self.ambient_color = QColor(0, 0, 0, 0)
            
        self.btn_spotify.setEnabled(True)
        
        self.meta_text.setPlainText(
            f"Album\n{track.album_name}\n\nReleased\n{track.release_date}\n\n"
            f"Release type\n{track.album_type.title()}\n\nRole\n{track.performer_role.title()}")
        self.update()  # Trigger paintEvent for glow repaint

    def clear(self):
        self.current_track = None
        self.lbl_title.setText("Select a track")
        self.lbl_artists.clear()
        self.lbl_large_art.clear()
        self.lbl_large_art.setText("Artwork")
        self.meta_text.setPlainText("Choose a release to see its details and open it in Spotify.")
        self.btn_spotify.setEnabled(False)
        self.ambient_color = QColor(0, 0, 0, 0)
        self.update()

    def open_spotify_link(self):
        if self.current_track and self.current_track.track_id:
            url = f"https://open.spotify.com/track/{self.current_track.track_id}"
            QDesktopServices.openUrl(QUrl(url))

    def paintEvent(self, event):
        # Draw background and then overlay ambient radial glow in the top half
        super().paintEvent(event)
        
        if self.ambient_color.alpha() == 0 or self.ambient_color == QColor(0,0,0,0):
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Gradient centered at the artwork label center
        center_x = self.width() / 2.0
        center_y = 120.0
        
        radial_grad = QRadialGradient(center_x, center_y, 160.0)
        # 15% opacity dominant color fading out
        glow_color = QColor(self.ambient_color.red(), self.ambient_color.green(), self.ambient_color.blue(), 30)
        radial_grad.setColorAt(0.0, glow_color)
        radial_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setBrush(QBrush(radial_grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())


class ResultsPage(QWidget):
    create_playlist_requested = Signal(list)  # list of tracks to add
    export_json_requested = Signal(list)
    artwork_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.busy = False
        self.has_scanned = False
        self.loading = False
        self.load_timer = QTimer(self)
        self.load_timer.setSingleShot(True)
        self.load_timer.timeout.connect(self.load_next_rows)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left Canvas
        canvas = QFrame()
        canvas.setProperty("class", "canvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(16, 16, 16, 16)
        canvas_layout.setSpacing(12)
        
        # Header Controls
        header = QHBoxLayout()
        title = QLabel("Scan Results")
        title.setProperty("class", "heading")
        title.setStyleSheet("font-size: 24px;")
        header.addWidget(title)
        
        header.addStretch()
        self.btn_details = QPushButton("Track details")
        self.btn_details.clicked.connect(self.show_details)
        header.addWidget(self.btn_details)
        
        self.btn_export = QPushButton("Export JSON")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.clicked.connect(self.on_export_clicked)
        header.addWidget(self.btn_export)
        
        self.btn_create_pl = QPushButton("Create Playlist")
        self.btn_create_pl.setProperty("class", "primary")
        self.btn_create_pl.setCursor(Qt.PointingHandCursor)
        self.btn_create_pl.clicked.connect(self.on_create_playlist_clicked)
        header.addWidget(self.btn_create_pl)
        
        canvas_layout.addLayout(header)
        
        # Filter / Search Row
        filter_layout = QHBoxLayout()
        
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search tracks or artists... (Ctrl+F)")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setAccessibleName("Search tracks, artists, or albums")
        self.txt_search.textChanged.connect(self.filter_tracks)
        filter_layout.addWidget(self.txt_search, 1)
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["All Album Types", "Albums", "Singles", "EPs", "Collaborations"])
        self.combo_type.currentIndexChanged.connect(self.filter_tracks)
        self.combo_type.setStyleSheet(f"""
            QComboBox {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                padding: 8px 12px;
                color: {Theme.STRONG_TEXT};
            }}
        """)
        filter_layout.addWidget(self.combo_type)
        
        self.combo_role = QComboBox()
        self.combo_role.addItems(["All Roles", "Main Artists", "Featured Artists"])
        self.combo_role.currentIndexChanged.connect(self.filter_tracks)
        self.combo_role.setStyleSheet(self.combo_type.styleSheet())
        filter_layout.addWidget(self.combo_role)
        
        canvas_layout.addLayout(filter_layout)
        
        # Selection tools
        select_row = QHBoxLayout()
        self.chk_select_all = QCheckBox("Select visible tracks")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.stateChanged.connect(self.toggle_all_selection)
        select_row.addWidget(self.chk_select_all)
        
        select_row.addStretch()
        
        self.lbl_selected_count = QLabel("Selected: 0 / 0 tracks")
        self.lbl_selected_count.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px;")
        select_row.addWidget(self.lbl_selected_count)
        
        canvas_layout.addLayout(select_row)

        self.empty_label = QLabel("Your releases will appear here. Start a scan from Home or New Release Scan.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setMinimumHeight(100)
        canvas_layout.addWidget(self.empty_label)
        self.btn_clear_filters = QPushButton("Clear filters")
        self.btn_clear_filters.clicked.connect(self.clear_filters)
        canvas_layout.addWidget(self.btn_clear_filters, 0, Qt.AlignLeft)

        self.output_label = QLabel("")
        self.output_label.setWordWrap(True)
        self.output_label.setTextFormat(Qt.PlainText)
        canvas_layout.addWidget(self.output_label)
        self.btn_open_output = QPushButton("Open output")
        self.btn_open_output.clicked.connect(self.open_output)
        self.btn_open_output.hide()
        canvas_layout.addWidget(self.btn_open_output, 0, Qt.AlignLeft)
        self.btn_export_folder = QPushButton("Open export folder")
        self.btn_export_folder.clicked.connect(lambda: QDesktopServices.openUrl(self.export_url))
        self.btn_export_folder.hide()
        canvas_layout.addWidget(self.btn_export_folder, 0, Qt.AlignLeft)
        self.outputs = {}
        
        # List Widget
        self.track_list = QListWidget()
        self.track_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.track_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Theme.MAIN_CANVAS};
                border: 1px solid {Theme.BORDER};
                border-radius: 18px;
                padding: 8px;
            }}
            QListWidget::item {{
                background-color: {Theme.SECONDARY_SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 12px;
                margin-bottom: 8px;
                padding: 4px;
            }}
            QListWidget::item:hover {{
                background-color: {Theme.HOVER_SURFACE};
            }}
            QListWidget::item:selected {{
                background-color: rgba(139, 115, 255, 0.1);
                border: 1px solid {Theme.VIOLET_ACCENT};
            }}
        """)
        self.track_list.currentItemChanged.connect(lambda item, previous: self.on_track_clicked(item))
        self.track_list.setAccessibleName("Discovered releases")
        self.track_list.verticalScrollBar().valueChanged.connect(self.request_visible_artwork)
        canvas_layout.addWidget(self.track_list, 1)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(canvas)
        main_layout.addWidget(self.splitter)
        
        # Right Detail Panel
        self.detail_panel = DetailPanel()
        self.splitter.addWidget(self.detail_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([800, 280])
        
        self.all_tracks: List[Track] = []
        self.item_widgets: Dict[str, TrackItemWidget] = {}
        self.artwork_cache: Dict[str, QImage] = {}
        self.detail_panel.clear()
        self.update_selection_metrics()

    def set_results(self, tracks: List[Track]):
        self.load_timer.stop()
        self.has_scanned = True
        self.all_tracks = list(tracks)
        self.detail_panel.clear()
        self.output_label.clear()
        self.outputs.clear()
        self.btn_open_output.hide()
        self.btn_export_folder.hide()
        self.track_list.clear()
        self.item_widgets.clear()
        self.load_index = 0
        self.loading = bool(tracks)
        self.load_next_rows()

    def load_next_rows(self):
        # Yield between small batches so navigation and cancellation stay responsive.
        end = min(self.load_index + 50, len(self.all_tracks))
        for track in self.all_tracks[self.load_index:end]:
            item = QListWidgetItem(self.track_list)
            item.setSizeHint(QSize(0, 80))
            
            widget = TrackItemWidget(track)
            widget.checked_changed.connect(self.update_selection_metrics)
            
            # Save widget mapping
            self.item_widgets[track.track_id] = widget
            
            self.track_list.setItemWidget(item, widget)
            if track.album_artwork_url in self.artwork_cache:
                widget.set_artwork(self.artwork_cache[track.album_artwork_url])
        self.load_index = end
        self.loading = end < len(self.all_tracks)
        self.filter_tracks()
        if self.loading:
            self.load_timer.start(1)
        self.request_visible_artwork()

    def update_selection_metrics(self):
        visible = list(self.visible_widgets())
        selected = sum(w.chk.isChecked() for w in visible)
        self.lbl_selected_count.setText(f"{len(visible)} of {len(self.all_tracks)} shown · {selected} selected")
        blocker = QSignalBlocker(self.chk_select_all)
        self.chk_select_all.setCheckState(Qt.Checked if visible and selected == len(visible)
                                         else Qt.PartiallyChecked if selected else Qt.Unchecked)
        available = not self.busy and not self.loading
        self.chk_select_all.setEnabled(bool(visible) and available)
        self.btn_export.setEnabled(bool(selected) and available)
        self.btn_create_pl.setEnabled(bool(selected) and available)
        self.btn_create_pl.setText(f"Create playlist ({selected})" if selected else "Create playlist")
        self.empty_label.setVisible(not visible)
        self.track_list.setVisible(bool(visible))
        filtered = bool(self.txt_search.text() or self.combo_type.currentIndex() or self.combo_role.currentIndex())
        self.btn_clear_filters.setVisible(filtered)
        if self.all_tracks:
            self.empty_label.setText("No releases match these filters. Try another search or clear the filters.")
        elif self.has_scanned:
            self.empty_label.setText("No releases found in this scan. Try an earlier date or a wider artist range.")
        else:
            self.empty_label.setText("Your releases will appear here. Start a scan from Home or New Release Scan.")
        if self.loading:
            self.empty_label.setText(f"Preparing results… {self.load_index} of {len(self.all_tracks)} tracks")
            self.empty_label.show()

    def visible_widgets(self):
        for index in range(self.track_list.count()):
            item = self.track_list.item(index)
            if not item.isHidden():
                widget = self.track_list.itemWidget(item)
                if widget:
                    yield widget

    def selected_tracks(self):
        return [w.track for w in self.visible_widgets() if w.chk.isChecked()]

    def set_busy(self, busy):
        self.busy = busy
        self.update_selection_metrics()

    def clear_filters(self):
        self.txt_search.clear()
        self.combo_type.setCurrentIndex(0)
        self.combo_role.setCurrentIndex(0)

    def show_output(self, message, url, button_text):
        self.output_url = url
        if url.isLocalFile():
            self.export_url = url
            self.outputs['export'] = message
            self.btn_export_folder.show()
        else:
            self.outputs['playlist'] = message
            self.btn_open_output.setText(button_text)
            self.btn_open_output.show()
            self.playlist_url = url
        self.output_label.setText("\n".join(self.outputs.values()))

    def open_output(self):
        QDesktopServices.openUrl(self.playlist_url)

    def toggle_all_selection(self, state):
        checked = state != Qt.Unchecked.value
        for widget in self.visible_widgets():
            blocker = QSignalBlocker(widget.chk)
            widget.chk.setChecked(checked)
        self.update_selection_metrics()

    def filter_tracks(self):
        query = self.txt_search.text().strip().lower()
        filter_type = self.combo_type.currentIndex()
        filter_role = self.combo_role.currentIndex()
        
        for i in range(self.track_list.count()):
            item = self.track_list.item(i)
            widget = self.track_list.itemWidget(item)
            if not widget:
                continue
                
            track = widget.track
            
            # 1. Search Query
            match_search = (query in track.track_name.lower() or 
                            any(query in a.lower() for a in track.all_artists) or 
                            query in track.album_name.lower())
            
            # 2. Type Filter
            # ["All Album Types", "Albums", "Singles", "EPs", "Collaborations"]
            match_type = True
            if filter_type == 1:
                match_type = (track.album_type == 'album')
            elif filter_type == 2:
                match_type = (track.album_type == 'single')
            elif filter_type == 3:
                match_type = (track.album_type == 'ep')
            elif filter_type == 4:
                match_type = track.is_collaboration
                
            # 3. Role Filter
            # ["All Roles", "Main Artists", "Featured Artists"]
            match_role = True
            if filter_role == 1:
                match_role = (track.performer_role == 'main')
            elif filter_role == 2:
                match_role = (track.performer_role == 'featured')
                
            visible = match_search and match_type and match_role
            item.setHidden(not visible)
            
        self.update_selection_metrics()

    def on_track_clicked(self, item):
        if item is None:
            return
        widget = self.track_list.itemWidget(item)
        if widget:
            track = widget.track
            art = self.artwork_cache.get(track.album_artwork_url, QImage())
            self.detail_panel.set_track(track, art)
            if track.album_artwork_url and art.isNull():
                self.artwork_requested.emit(track.album_artwork_url)

    def request_visible_artwork(self):
        if not self.isVisible() or not self.track_list.count():
            return
        first = max(0, self.track_list.indexAt(QPoint(8, 8)).row())
        # Include a small margin below the viewport for smooth scrolling.
        count = max(3, self.track_list.viewport().height() // 70 + 3)
        urls = set()
        shown = 0
        for row in range(first, self.track_list.count()):
            item = self.track_list.item(row)
            if item.isHidden():
                continue
            widget = self.track_list.itemWidget(item)
            url = widget.track.album_artwork_url if widget else None
            if url and url not in self.artwork_cache:
                urls.add(url)
            shown += 1
            if shown >= count:
                break
        for url in urls:
            self.artwork_requested.emit(url)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.request_visible_artwork)

    def set_track_artwork(self, artwork_url: str, image: QImage):
        # Cache image
        if len(self.artwork_cache) >= 256 and artwork_url not in self.artwork_cache:
            self.artwork_cache.pop(next(iter(self.artwork_cache)))
        self.artwork_cache[artwork_url] = image
        
        # Propagate to visible rows
        for widget in self.item_widgets.values():
            if widget.track.album_artwork_url == artwork_url:
                widget.set_artwork(image)
                
        # Propagate to details if currently active
        if (self.detail_panel.current_track and 
            self.detail_panel.current_track.album_artwork_url == artwork_url):
            self.detail_panel.set_track(self.detail_panel.current_track, image)

    def on_create_playlist_clicked(self):
        if not self.busy and not self.loading and self.selected_tracks():
            self.create_playlist_requested.emit(self.selected_tracks())

    def on_export_clicked(self):
        if not self.busy and not self.loading and self.selected_tracks():
            self.export_json_requested.emit(self.selected_tracks())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.detail_panel.setVisible(self.width() >= 1000)
        self.btn_details.setVisible(self.width() < 1000)

    def show_details(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Track details")
        layout = QVBoxLayout(dialog)
        panel = DetailPanel(dialog)
        panel.clear()
        if self.detail_panel.current_track:
            track = self.detail_panel.current_track
            panel.set_track(track, self.artwork_cache.get(track.album_artwork_url))
        layout.addWidget(panel)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.resize(360, 620)
        dialog.exec()

    def focus_search(self):
        self.txt_search.setFocus()
        self.txt_search.selectAll()
