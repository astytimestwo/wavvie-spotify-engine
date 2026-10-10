"""Qt adapters. One terminal signal per job, after callbacks are detached."""
from contextlib import contextmanager
import urllib.request
from PySide6.QtCore import QObject, Signal, QRunnable, Qt
from PySide6.QtGui import QImage

class WorkerSignals(QObject):
    started = Signal()
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(object)
    warning = Signal(str)
    rate_limit = Signal(int)
    batch_completed = Signal(int, int)
    artist_started = Signal(int, str, str)
    artist_scanned = Signal(int, str, int)
    track_discovered = Signal(object)
    duplicate_prevented = Signal(str, str)

@contextmanager
def callbacks(service, bindings):
    previous = {key: service.callbacks.get(key) for key in bindings}
    for key, callback in bindings.items():
        service.register_callback(key, callback)
    try:
        yield
    finally:
        for key, callback in bindings.items():
            if service.callbacks.get(key) is callback:
                if previous[key] is None:
                    service.callbacks.pop(key, None)
                else:
                    service.callbacks[key] = previous[key]

class AuthWorker(QRunnable):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.signals = WorkerSignals()

    def run(self):
        errors = []
        self.signals.started.emit()
        try:
            with callbacks(self.service, {"auth_failed": errors.append}):
                success = self.service.authenticate()
            if success:
                self.signals.finished.emit(self.service.user_data)
            else:
                self.signals.error.emit(errors[-1] if errors else "Spotify authentication failed.")
        except Exception as error:
            self.signals.error.emit(str(error))

class LoadArtistsWorker(QRunnable):
    def __init__(self, service, refresh=False):
        super().__init__()
        self.service = service
        self.refresh = refresh
        self.signals = WorkerSignals()

    def run(self):
        self.signals.started.emit()
        try:
            with callbacks(self.service, {"warning": self.signals.warning.emit}):
                artists = self.service.get_and_cache_followed_artists(refresh=self.refresh)
            self.signals.finished.emit(artists)
        except Exception as error:
            self.signals.error.emit(str(error))

class ScanWorker(QRunnable):
    def __init__(self, service, config):
        super().__init__()
        self.service = service
        self.config = config
        self.signals = WorkerSignals()

    def run(self):
        errors = []
        bindings = {
            "artist_scanning_started": lambda idx, name, img: self.signals.artist_started.emit(idx, name, img or ""),
            "artist_scanning_completed": self.signals.artist_scanned.emit,
            "track_discovered": self.signals.track_discovered.emit,
            "duplicate_prevented": self.signals.duplicate_prevented.emit,
            "rate_limit_encountered": self.signals.rate_limit.emit,
            "warning": self.signals.warning.emit,
            "progress_changed": lambda progress: self.signals.progress.emit(("progress", progress)),
            "fatal_error": errors.append,
        }
        self.signals.started.emit()
        try:
            with callbacks(self.service, bindings):
                result = self.service.scan_releases(self.config)
            if result is not None:
                self.signals.finished.emit(result)
            else:
                message = "Scan cancelled by user." if self.service.cancelled else (errors[-1] if errors else "Scan failed.")
                self.signals.error.emit(message)
        except Exception as error:
            self.signals.error.emit(str(error))

class PlaylistWorker(QRunnable):
    def __init__(self, service, tracks, config, start_idx, end_idx, followed_artists=0):
        super().__init__()
        self.service = service
        self.tracks = tracks
        self.config = config
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.followed_artists = followed_artists
        self.signals = WorkerSignals()

    def run(self):
        errors = []
        self.signals.started.emit()
        try:
            with callbacks(self.service, {"playlist_batch_completed": self.signals.batch_completed.emit, "warning": errors.append}):
                result = self.service.create_playlist(self.tracks, self.config, self.start_idx, self.end_idx,
                                                      self.followed_artists)
            if result is not None:
                self.signals.finished.emit(result)
            else:
                self.signals.error.emit(errors[-1] if errors else "Playlist creation failed.")
        except Exception as error:
            self.signals.error.emit(str(error))

class ImageLoadWorker(QRunnable):
    def __init__(self, url, target_size=200):
        super().__init__()
        self.url = url
        self.target_size = target_size
        self.signals = WorkerSignals()

    def run(self):
        try:
            request = urllib.request.Request(self.url, headers={"User-Agent": "wavvie"})
            with urllib.request.urlopen(request, timeout=10) as response:
                data = response.read(10 * 1024 * 1024)
            image = QImage()
            if not image.loadFromData(data):
                raise ValueError("Artwork could not be decoded.")
            self.signals.finished.emit(image.scaled(self.target_size, self.target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as error:
            self.signals.error.emit(str(error))
