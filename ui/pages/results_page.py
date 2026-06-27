from typing import List, Dict, Optional
import os
from PySide6.QtCore import Qt, Signal, QUrl, QRectF
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QLineEdit, QListWidget, 
                               QListWidgetItem, QComboBox, QCheckBox, QSplitter,
                               QTextEdit)
from PySide6.QtGui import QImage, QPixmap, QDesktopServices, QPainter, QColor, QBrush, QRadialGradient
from ui.theme import Theme
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
        
        self.lbl_title = QLabel(track.track_name)
        self.lbl_title.setStyleSheet(f"color: {Theme.STRONG_TEXT}; font-weight: bold; font-size: 13px;")
        self.lbl_artist = QLabel(", ".join(track.all_artists))
        self.lbl_artist.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 11px;")
        
        details_layout.addWidget(self.lbl_title)
        details_layout.addWidget(self.lbl_artist)
        layout.addWidget(details, 1)
        
        # 4. Album name
        self.lbl_album = QLabel(track.album_name)
        self.lbl_album.setFixedWidth(140)
        self.lbl_album.setStyleSheet(f"color: {Theme.MUTED_TEXT}; font-size: 11px;")
        layout.addWidget(self.lbl_album)
        
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
        self.setFixedWidth(320)
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
        self.lbl_title.setProperty("class", "heading")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setStyleSheet("font-size: 18px;")
        layout.addWidget(self.lbl_title)
        
        self.lbl_artists = QLabel("")
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
        
        # Format metadata
        meta_html = f"""
            <p><b>Album:</b> {track.album_name}</p>
            <p><b>Release Date:</b> {track.release_date}</p>
            <p><b>Type:</b> {track.album_type.upper()}</p>
            <p><b>Role:</b> {track.performer_role.upper()}</p>
            <p><b>Collaboration:</b> {"Yes" if track.is_collaboration else "No"}</p>
            <p><b>Signature:</b> <code style="font-family: {Theme.FONT_MONO}; font-size: 11px;">{track.track_signature}</code></p>
        """
        self.meta_text.setHtml(meta_html)
        self.update()  # Trigger paintEvent for glow repaint

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

    def __init__(self, parent=None):
        super().__init__(parent)
        
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
        self.chk_select_all = QCheckBox("Select All / Deselect All")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.stateChanged.connect(self.toggle_all_selection)
        select_row.addWidget(self.chk_select_all)
        
        select_row.addStretch()
        
        self.lbl_selected_count = QLabel("Selected: 0 / 0 tracks")
        self.lbl_selected_count.setStyleSheet(f"color: {Theme.SECONDARY_TEXT}; font-size: 12px;")
        select_row.addWidget(self.lbl_selected_count)
        
        canvas_layout.addLayout(select_row)
        
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
        self.track_list.itemClicked.connect(self.on_track_clicked)
        canvas_layout.addWidget(self.track_list, 1)
        
        main_layout.addWidget(canvas, 1)
        
        # Right Detail Panel
        self.detail_panel = DetailPanel()
        main_layout.addWidget(self.detail_panel)
        
        self.all_tracks: List[Track] = []
        self.item_widgets: Dict[str, TrackItemWidget] = {}
        self.artwork_cache: Dict[str, QImage] = {}

    def set_results(self, tracks: List[Track]):
        self.all_tracks = tracks
        self.track_list.clear()
        self.item_widgets.clear()
        
        for track in tracks:
            item = QListWidgetItem(self.track_list)
            # Size hint
            item.setSizeHint(item.sizeHint())
            
            widget = TrackItemWidget(track)
            widget.checked_changed.connect(self.update_selection_metrics)
            
            # Save widget mapping
            self.item_widgets[track.track_id] = widget
            
            self.track_list.setItemWidget(item, widget)
            
        self.filter_tracks()
        self.update_selection_metrics()

    def update_selection_metrics(self):
        total = len(self.item_widgets)
        selected = sum([1 for w in self.item_widgets.values() if w.chk.isChecked()])
        self.lbl_selected_count.setText(f"Selected: {selected} / {total} tracks")

    def toggle_all_selection(self, state):
        checked = (state == 2)
        for widget in self.item_widgets.values():
            # If the item is currently visible, toggle it
            if not widget.parentWidget().isHidden():
                widget.chk.setChecked(checked)
        self.update_selection_metrics()

    def filter_tracks(self):
        query = self.txt_search.text().lower()
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
        widget = self.track_list.itemWidget(item)
        if widget:
            track = widget.track
            art = self.artwork_cache.get(track.album_artwork_url, QImage())
            self.detail_panel.set_track(track, art)

    def set_track_artwork(self, artwork_url: str, image: QImage):
        # Cache image
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
        selected_tracks = []
        for widget in self.item_widgets.values():
            if widget.chk.isChecked() and not widget.parentWidget().isHidden():
                selected_tracks.append(widget.track)
        self.create_playlist_requested.emit(selected_tracks)

    def on_export_clicked(self):
        selected_tracks = []
        for widget in self.item_widgets.values():
            if widget.chk.isChecked() and not widget.parentWidget().isHidden():
                selected_tracks.append(widget.track)
        self.export_json_requested.emit(selected_tracks)

    def focus_search(self):
        self.txt_search.setFocus()
        self.txt_search.selectAll()
