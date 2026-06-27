from PySide6.QtCore import QObject, Signal, QRunnable
from core.models import ScanConfiguration

class WorkerSignals(QObject):
    started = Signal()
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(object)  # Tuples like (type, data)
    warning = Signal(str)
    rate_limit = Signal(int)
    batch_completed = Signal(int, int)
    artist_started = Signal(int, str, str)  # index, name, image_url
    artist_scanned = Signal(int, str, int)  # index, name, tracks_found
    track_discovered = Signal(object)      # Track dataclass
    duplicate_prevented = Signal(str, str) # track_name, original_artist

class AuthWorker(QRunnable):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.signals = WorkerSignals()
        
    def run(self):
        self.service.register_callback("auth_started", lambda: self.signals.started.emit())
        self.service.register_callback("auth_success", lambda user: self.signals.finished.emit(user))
        self.service.register_callback("auth_failed", lambda err: self.signals.error.emit(err))
        
        try:
            success = self.service.authenticate()
            if not success:
                # If authenticate() returns False without trigger_callback, we emit error
                if not self.service.sp:
                    self.signals.error.emit("Spotify authentication failed.")
        except Exception as e:
            self.signals.error.emit(str(e))

class LoadArtistsWorker(QRunnable):
    def __init__(self, service, refresh=False):
        super().__init__()
        self.service = service
        self.refresh = refresh
        self.signals = WorkerSignals()
        
    def run(self):
        self.signals.started.emit()
        self.service.register_callback("artists_loaded", lambda artists: self.signals.finished.emit(artists))
        self.service.register_callback("warning", lambda msg: self.signals.warning.emit(msg))
        
        try:
            self.service.get_and_cache_followed_artists(refresh=self.refresh)
        except Exception as e:
            self.signals.error.emit(str(e))

class ScanWorker(QRunnable):
    def __init__(self, service, config):
        super().__init__()
        self.service = service
        self.config = config
        self.signals = WorkerSignals()
        
    def run(self):
        self.service.register_callback("scan_started", lambda: self.signals.started.emit())
        self.service.register_callback("artist_scanning_started", lambda idx, name, img: self.signals.artist_started.emit(idx, name, img or ""))
        self.service.register_callback("artist_scanning_completed", lambda idx, name, count: self.signals.artist_scanned.emit(idx, name, count))
        self.service.register_callback("track_discovered", lambda track: self.signals.track_discovered.emit(track))
        self.service.register_callback("duplicate_prevented", lambda name, orig: self.signals.duplicate_prevented.emit(name, orig))
        self.service.register_callback("rate_limit_encountered", lambda sec: self.signals.rate_limit.emit(sec))
        self.service.register_callback("warning", lambda msg: self.signals.warning.emit(msg))
        self.service.register_callback("progress_changed", lambda prog: self.signals.progress.emit(("progress", prog)))
        self.service.register_callback("fatal_error", lambda err: self.signals.error.emit(err))
        
        try:
            result = self.service.scan_releases(self.config)
            if result:
                self.signals.finished.emit(result)
            else:
                if self.service.cancelled:
                    self.signals.error.emit("Scan cancelled by user.")
                else:
                    self.signals.error.emit("Scan failed.")
        except Exception as e:
            self.signals.error.emit(str(e))

class PlaylistWorker(QRunnable):
    def __init__(self, service, tracks, config, start_idx, end_idx):
        super().__init__()
        self.service = service
        self.tracks = tracks
        self.config = config
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.signals = WorkerSignals()
        
    def run(self):
        self.service.register_callback("playlist_started", lambda: self.signals.started.emit())
        self.service.register_callback("playlist_batch_completed", lambda completed, total: self.signals.batch_completed.emit(completed, total))
        self.service.register_callback("warning", lambda msg: self.signals.warning.emit(msg))
        
        try:
            result = self.service.create_playlist(self.tracks, self.config, self.start_idx, self.end_idx)
            if result:
                self.signals.finished.emit(result)
            else:
                self.signals.error.emit("Playlist creation failed.")
        except Exception as e:
            self.signals.error.emit(str(e))

import urllib.request
from PySide6.QtGui import QImage

class ImageLoadWorker(QRunnable):
    def __init__(self, url: str, target_size: int = 200):
        super().__init__()
        self.url = url
        self.target_size = target_size
        self.signals = WorkerSignals()
        
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                
            img = QImage()
            if img.loadFromData(data):
                # Crop/scale to limit dimensions
                img = img.scaled(self.target_size, self.target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.signals.finished.emit(img)
            else:
                self.signals.error.emit("Failed to parse image data.")
        except Exception as e:
            self.signals.error.emit(str(e))
