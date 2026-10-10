"""The one screen wavvie needs: what to check next, the check itself, and what it saved."""
import os
from datetime import date
from typing import List, Optional

from PySide6.QtCore import QDate, QPoint, QRect, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDateEdit, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.history import CheckRecord, NextWindow, release_label, short_date, window_label
from core.models import Track
from ui.widgets.controls import button, clear_layout, label, rule, scroll_column
from ui.widgets.elided_label import ElidedLabel
from ui.widgets.wave_line import WaveLine


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def saved_phrase(record):
    return f"saved {plural(record.songs, 'song')}" if record.songs else "found nothing new"


class SongRow(QFrame):
    activated = Signal(str)

    def __init__(self, track: Track, parent=None):
        super().__init__(parent)
        self.track = track
        self.url = f"https://open.spotify.com/track/{track.track_id}"
        artists = ", ".join(track.all_artists)
        self.setObjectName("songRow")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(f"Open {track.track_name} by {artists} in Spotify")
        self.setToolTip(f"{track.track_name}\n{artists}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)
        self.art = QLabel()
        self.art.setObjectName("artwork")
        self.art.setFixedSize(40, 40)
        layout.addWidget(self.art)
        text = QVBoxLayout()
        text.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(ElidedLabel(track.track_name), 1)
        if track.performer_role == 'featured':
            title_row.addWidget(label("feature", "tag", wrap=False))
        text.addLayout(title_row)
        names = ElidedLabel(artists)
        names.setProperty("role", "secondary")
        text.addWidget(names)
        layout.addLayout(text, 1)
        layout.addWidget(label(release_label(track.release_date), "meta", wrap=False))

    def set_artwork(self, image):
        if not image.isNull():
            self.art.setPixmap(QPixmap.fromImage(image.scaled(40, 40, Qt.KeepAspectRatioByExpanding,
                                                              Qt.SmoothTransformation)))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.url)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activated.emit(self.url)
        else:
            super().keyPressEvent(event)


class HistoryRow(QWidget):
    open_requested = Signal(str)

    def __init__(self, record: CheckRecord, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addWidget(label(window_label(record.start_date, record.end_date), wrap=False), 1)
        layout.addWidget(label(plural(record.songs, 'song') if record.songs else "Nothing new", "secondary", wrap=False))
        if record.playlist_url:
            self.btn_open = button("Open in Spotify", "quiet", "openHistoryPlaylist")
            self.btn_open.clicked.connect(lambda: self.open_requested.emit(record.playlist_url))
            layout.addWidget(self.btn_open)


class HomePage(QWidget):
    check_requested = Signal(object)
    stop_requested = Signal()
    done_requested = Signal()
    retry_save_requested = Signal()
    refresh_artists_requested = Signal()
    open_url_requested = Signal(str)
    show_file_requested = Signal(str)
    artwork_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = 'empty'
        self.suggested: Optional[NextWindow] = None
        self.look_back_days = 30
        self.last_start: Optional[date] = None
        self.song_rows: List[SongRow] = []
        self.requested_artwork = set()
        self.actions = {}
        self.scroll, layout = scroll_column(self, top=20)

        self.headline = label("", "headline")
        self.body = label("", "body")
        self.note = label("", "note")
        self.wave = WaveLine()
        self.progress = label("", "secondary")
        for widget in (self.headline, self.body, self.note, self.wave, self.progress):
            layout.addWidget(widget)

        self.dates_row = QWidget()
        dates = QHBoxLayout(self.dates_row)
        dates.setContentsMargins(0, 0, 0, 0)
        dates.setSpacing(10)
        self.lbl_from = label("Check from", wrap=False)
        self.date_start = QDateEdit()
        self.date_start.setObjectName("checkFrom")
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("d MMM yyyy")
        self.date_start.setAccessibleName("First day to check")
        self.lbl_from.setBuddy(self.date_start)
        self.btn_reset_dates = button("Use suggested dates", "quiet", "useSuggestedDates")
        for widget in (self.lbl_from, self.date_start, label("to today", wrap=False), self.btn_reset_dates):
            dates.addWidget(widget)
        dates.addStretch()
        layout.addWidget(self.dates_row)

        actions = QHBoxLayout()
        actions.setSpacing(16)
        self.btn_primary = button("", "primary", "primaryAction")
        self.btn_quiet = button("", "quiet", "quietAction")
        self.btn_extra = button("", "quiet", "extraAction")
        for widget in (self.btn_primary, self.btn_quiet, self.btn_extra):
            actions.addWidget(widget)
            widget.clicked.connect(lambda checked=False, source=widget: self.run_action(source))
        actions.addStretch()
        layout.addSpacing(4)
        layout.addLayout(actions)

        self.songs_box = QWidget()
        self.songs_layout = QVBoxLayout(self.songs_box)
        self.songs_layout.setContentsMargins(0, 8, 0, 0)
        self.songs_layout.setSpacing(2)
        layout.addWidget(self.songs_box)
        self.history_box = QWidget()
        self.history_layout = QVBoxLayout(self.history_box)
        self.history_layout.setContentsMargins(0, 20, 0, 0)
        self.history_layout.setSpacing(4)
        layout.addWidget(self.history_box)
        layout.addStretch()

        self.date_start.dateChanged.connect(self.update_check_label)
        self.btn_reset_dates.clicked.connect(self.use_suggested_dates)
        self.scroll.verticalScrollBar().valueChanged.connect(self.request_visible_artwork)
        self.show_state('empty', "")

    def show_state(self, state, headline, body="", note="", primary=None, quiet=None, extra=None):
        self.state = state
        self.headline.setText(headline)
        for widget, text in ((self.body, body), (self.note, note)):
            widget.setText(text)
            widget.setVisible(bool(text))
        self.wave.set_active(False)
        self.wave.hide()
        self.progress.hide()
        self.dates_row.hide()
        for widget, spec in ((self.btn_primary, primary), (self.btn_quiet, quiet), (self.btn_extra, extra)):
            self.set_action(widget, spec)
        clear_layout(self.songs_layout)
        self.song_rows = []
        self.songs_box.hide()
        clear_layout(self.history_layout)
        self.history_box.hide()

    def set_action(self, widget, spec):
        if spec is None:
            self.actions.pop(widget, None)
            widget.hide()
            return
        text, callback = spec
        widget.setText(text)
        widget.setEnabled(True)
        self.actions[widget] = callback
        widget.show()

    def run_action(self, widget):
        callback = self.actions.get(widget)
        if callback is not None:
            callback()

    def show_loading_artists(self):
        self.show_state('loading', "Getting your artists…")

    def show_no_artists(self):
        self.show_state('no_artists', "You don't follow any artists yet",
                        "Follow artists in Spotify, then refresh your artist list.",
                        primary=("Refresh artist list", self.refresh_artists_requested.emit))

    def show_artists_failed(self, message):
        self.show_state('artists_failed', "Couldn't load your artists", message,
                        primary=("Try again", self.refresh_artists_requested.emit))

    def show_ready(self, window, artist_count, look_back_days, history):
        self.suggested = window
        self.look_back_days = look_back_days
        last = history[0] if history else None
        if window.kind == 'first' or last is None:
            headline = "Let's find your new music"
            body = (f"wavvie will check the {plural(artist_count, 'artist')} you follow and save anything "
                    f"released in the last {look_back_days} days to a private playlist.")
        elif window.kind == 'finish':
            headline = "Let's finish your last check"
            body = (f"Your last check didn't cover everything, so wavvie will look at "
                    f"{short_date(window.start)} – today again and skip songs it already saved.")
        elif window.kind == 'up_to_date':
            headline = "You're up to date"
            body = f"Your last check ran today and {saved_phrase(last)}."
        else:
            headline = f"New music since {short_date(window.start)}"
            body = f"Your last check covered {window_label(last.start_date, last.end_date)} and {saved_phrase(last)}."
        self.show_state('ready', headline, body, primary=("", self.request_check),
                        quiet=("Change dates", self.open_dates))
        today = date.today()
        self.date_start.setMaximumDate(QDate(today.year, today.month, today.day))
        self.set_start(window.start)
        self.update_check_label()
        self.show_history(history[:5])

    def set_start(self, day):
        blocker = QSignalBlocker(self.date_start)
        self.date_start.setDate(QDate(day.year, day.month, day.day))
        del blocker

    def chosen_start(self):
        return self.date_start.date().toPython()

    def check_label(self):
        start = self.chosen_start()
        if self.suggested and start == self.suggested.start:
            if self.suggested.kind == 'first':
                return f"Check the last {self.look_back_days} days"
            if self.suggested.kind == 'up_to_date':
                return "Check again"
        return f"Check {short_date(start)} – today"

    def update_check_label(self):
        if self.state == 'ready':
            self.btn_primary.setText(self.check_label())

    def request_check(self):
        self.check_requested.emit(self.chosen_start())

    def open_dates(self):
        self.dates_row.show()
        self.btn_quiet.hide()
        self.date_start.setFocus()

    def use_suggested_dates(self):
        if self.suggested:
            self.set_start(self.suggested.start)
        self.dates_row.hide()
        self.btn_quiet.show()
        self.update_check_label()

    def show_checking(self, artist_count, start):
        self.last_start = start
        self.show_state('checking', f"Checking your {plural(artist_count, 'artist')}…",
                        quiet=("Stop", self.stop_requested.emit))
        self.wave.set_progress(0.0)
        self.wave.show()
        self.wave.set_active(True)
        self.progress.setText(f"0 of {artist_count} artists")
        self.progress.show()

    def update_progress(self, done, total, songs):
        if self.state != 'checking':
            return
        self.wave.set_progress(done / total if total else 0.0)
        text = f"{done} of {total} artists"
        if songs:
            text += f" · {plural(songs, 'new song')} so far"
        self.progress.setText(text)
        self.note.hide()

    def show_rate_limited(self, seconds):
        if self.state == 'checking':
            self.note.setText(f"Spotify asked wavvie to slow down. Continuing in about {seconds} s.")
            self.note.show()

    def show_stopping(self):
        self.btn_quiet.setText("Stopping…")
        self.btn_quiet.setEnabled(False)

    def show_saving(self, count):
        self.show_state('saving', f"Saving {plural(count, 'song')} to Spotify…")
        self.wave.set_progress(1.0)
        self.wave.show()
        self.wave.set_active(True)

    def show_done(self, playlist_name, playlist_url, tracks, notes=(), json_file=None, added=None):
        if added is None:
            headline = f"{plural(len(tracks), 'new song')} saved"
        else:
            headline = f"{added} of {len(tracks)} songs saved"
        body = f"In your new playlist “{playlist_name}”."
        if json_file:
            body += f"\nA copy was saved to {os.path.basename(json_file)}."
        self.show_state('done', headline, body, "\n".join(notes),
                        primary=("Open in Spotify", lambda: self.open_url_requested.emit(playlist_url)),
                        quiet=("Done", self.done_requested.emit),
                        extra=("Show file", lambda: self.show_file_requested.emit(json_file)) if json_file else None)
        self.show_songs(tracks)

    def show_nothing_new(self, start, notes=()):
        self.show_state('nothing_new', f"Nothing new since {short_date(start)}",
                        "No playlist was made. Check again in a few days.", "\n".join(notes),
                        quiet=("Done", self.done_requested.emit))

    def show_not_saved(self, count, message):
        self.show_state('not_saved', "Your songs weren't saved",
                        f"wavvie found {plural(count, 'new song')}, but Spotify didn't create the playlist. {message}",
                        primary=("Try saving again", self.retry_save_requested.emit),
                        quiet=("Done", self.done_requested.emit))

    def show_stopped(self):
        self.show_state('stopped', "Check stopped", "Nothing was saved.", quiet=("Done", self.done_requested.emit))

    def show_failed(self, message):
        self.show_state('failed', "That check didn't finish", message,
                        primary=("Try again", lambda: self.check_requested.emit(self.last_start)),
                        quiet=("Done", self.done_requested.emit))

    def show_songs(self, tracks):
        for track in tracks:
            row = SongRow(track)
            row.activated.connect(self.open_url_requested.emit)
            self.songs_layout.addWidget(row)
            self.song_rows.append(row)
        self.songs_box.setVisible(bool(tracks))
        self.requested_artwork = set()
        QTimer.singleShot(0, self, self.request_visible_artwork)

    def show_history(self, records):
        if not records:
            return
        self.history_layout.addWidget(rule())
        self.history_layout.addWidget(label("Earlier checks", "section"))
        for record in records:
            row = HistoryRow(record)
            row.open_requested.connect(self.open_url_requested.emit)
            self.history_layout.addWidget(row)
        self.history_box.show()

    def request_visible_artwork(self):
        viewport = self.scroll.viewport()
        nearby = QRect(0, -200, viewport.width(), viewport.height() + 400)
        for row in self.song_rows:
            url = row.track.album_artwork_url
            if not url or url in self.requested_artwork or not row.isVisible():
                continue
            if nearby.intersects(QRect(row.mapTo(viewport, QPoint(0, 0)), row.size())):
                self.requested_artwork.add(url)
                self.artwork_requested.emit(url)

    def set_artwork(self, url, image):
        for row in self.song_rows:
            if row.track.album_artwork_url == url:
                row.set_artwork(image)

    def set_reduced_motion(self, enabled):
        self.wave.set_reduced_motion(enabled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.request_visible_artwork()
