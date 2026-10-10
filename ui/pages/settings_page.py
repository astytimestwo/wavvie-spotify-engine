"""Settings: your account, how far the first check looks back, and advanced options."""
from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QSpinBox, QStyledItemDelegate, QVBoxLayout,
                               QWidget)

from ui.widgets.controls import button, label, rule, scroll_column

LOOK_BACK_DAYS = (7, 30, 90, 180)


@dataclass
class Preferences:
    look_back_days: int = 30
    artist_range: Optional[Tuple[int, int]] = None
    workers: int = 5
    export_json: bool = False
    reduced_motion: bool = False


def read_preferences():
    settings = QSettings("wavvie", "SpotifyPlaylistCreator")
    days = settings.value("default_cutoff_days", 30, type=int)
    first = max(1, settings.value("artist_range_start", 1, type=int))
    last = max(first, settings.value("artist_range_end", first, type=int))
    return Preferences(
        look_back_days=days if days in LOOK_BACK_DAYS else 30,
        artist_range=(first, last) if settings.value("artist_range_enabled", False, type=bool) else None,
        workers=min(20, max(1, settings.value("default_workers", 5, type=int))),
        export_json=settings.value("auto_export_json", False, type=bool),
        reduced_motion=settings.value("reduced_motion", False, type=bool),
    )


class SettingsPage(QWidget):
    done_requested = Signal()
    disconnect_requested = Signal()
    refresh_artists_requested = Signal()
    activity_log_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.artist_count = 0
        self.scroll, layout = scroll_column(self, top=20)
        top = QHBoxLayout()
        top.addWidget(label("Settings", "headline"), 1)
        self.btn_done = button("Done", "primary", "closeSettings")
        top.addWidget(self.btn_done, 0, Qt.AlignVCenter)
        layout.addLayout(top)

        layout.addWidget(label("Spotify account", "section"))
        account = QHBoxLayout()
        self.lbl_account = label("Not connected", "body")
        self.btn_disconnect = button("Disconnect", "danger", "disconnect")
        account.addWidget(self.lbl_account, 1)
        account.addWidget(self.btn_disconnect)
        layout.addLayout(account)
        layout.addWidget(rule())

        layout.addWidget(label("First check", "section"))
        look_back = QHBoxLayout()
        caption = label("When there are no earlier checks, look back")
        self.combo_look_back = QComboBox()
        self.combo_look_back.setObjectName("lookBack")
        self.combo_look_back.addItems([f"{days} days" for days in LOOK_BACK_DAYS])
        # The native list adds Windows' blue accent; a styled delegate draws it from the stylesheet.
        self.combo_look_back.setItemDelegate(QStyledItemDelegate(self.combo_look_back))
        caption.setBuddy(self.combo_look_back)
        look_back.addWidget(caption, 1)
        look_back.addWidget(self.combo_look_back)
        layout.addLayout(look_back)
        layout.addWidget(rule())

        self.btn_advanced = button("Show advanced settings", "quiet", "toggleAdvanced")
        layout.addWidget(self.btn_advanced, 0, Qt.AlignLeft)
        self.advanced = QWidget()
        advanced = QVBoxLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(10)
        self.chk_range = QCheckBox("Only check some artists")
        self.chk_range.setObjectName("artistRange")
        advanced.addWidget(self.chk_range)
        # The range's captions and hint dim along with its boxes while the checkbox is off.
        self.range_box = QWidget()
        range_layout = QVBoxLayout(self.range_box)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(10)
        range_row = QHBoxLayout()
        self.spin_from = QSpinBox()
        self.spin_to = QSpinBox()
        for spin, text, name in ((self.spin_from, "From", "First artist to check"),
                                 (self.spin_to, "to", "Last artist to check")):
            spin.setRange(1, 9999)
            spin.setAccessibleName(name)
            caption = label(text, wrap=False)
            caption.setBuddy(spin)
            range_row.addWidget(caption)
            range_row.addWidget(spin)
        range_row.addStretch()
        range_layout.addLayout(range_row)
        range_layout.addWidget(label("Artists are in alphabetical order. Both ends are included.", "secondary"))
        advanced.addWidget(self.range_box)
        workers = QHBoxLayout()
        caption = label("Parallel checks", wrap=False)
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 20)
        caption.setBuddy(self.spin_workers)
        workers.addWidget(caption)
        workers.addWidget(self.spin_workers)
        workers.addStretch()
        advanced.addLayout(workers)
        advanced.addWidget(label("Lower this if Spotify often asks wavvie to slow down.", "secondary"))
        self.chk_json = QCheckBox("Also save a JSON file of each check")
        self.chk_json.setObjectName("saveJson")
        self.chk_motion = QCheckBox("Reduce motion")
        self.chk_motion.setObjectName("reduceMotion")
        advanced.addWidget(self.chk_json)
        advanced.addWidget(self.chk_motion)
        tools = QHBoxLayout()
        tools.setSpacing(24)
        self.btn_refresh = button("Refresh artist list", "quiet", "refreshArtists")
        self.btn_log = button("View activity log", "quiet", "viewActivityLog")
        tools.addWidget(self.btn_refresh)
        tools.addWidget(self.btn_log)
        tools.addStretch()
        advanced.addLayout(tools)
        self.advanced.hide()
        layout.addWidget(self.advanced)
        self.lbl_saved = label("Changes are saved automatically.", "secondary")
        layout.addWidget(self.lbl_saved)
        layout.addStretch()

        self.btn_done.clicked.connect(self.done_requested.emit)
        self.btn_disconnect.clicked.connect(self.disconnect_requested.emit)
        self.btn_advanced.clicked.connect(self.toggle_advanced)
        self.btn_refresh.clicked.connect(self.refresh_artists_requested.emit)
        self.btn_log.clicked.connect(self.activity_log_requested.emit)
        self.combo_look_back.currentIndexChanged.connect(self.save_settings)
        for box in (self.chk_range, self.chk_json, self.chk_motion):
            box.toggled.connect(self.save_settings)
        for spin in (self.spin_from, self.spin_to, self.spin_workers):
            spin.valueChanged.connect(self.save_settings)
        self.load_settings()

    def controls(self):
        return (self.combo_look_back, self.chk_range, self.spin_from, self.spin_to, self.spin_workers,
                self.chk_json, self.chk_motion)

    def load_settings(self):
        # Loading one control must not save the others before they are set.
        blockers = [QSignalBlocker(control) for control in self.controls()]
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        preferences = read_preferences()
        self.combo_look_back.setCurrentIndex(LOOK_BACK_DAYS.index(preferences.look_back_days))
        self.chk_range.setChecked(preferences.artist_range is not None)
        self.spin_from.setValue(settings.value("artist_range_start", 1, type=int))
        self.spin_to.setValue(settings.value("artist_range_end", max(1, self.artist_count), type=int))
        self.spin_workers.setValue(preferences.workers)
        self.chk_json.setChecked(preferences.export_json)
        self.chk_motion.setChecked(preferences.reduced_motion)
        del blockers
        self.sync_range_controls()

    def save_settings(self):
        if self.spin_to.value() < self.spin_from.value():
            blocker = QSignalBlocker(self.spin_to)
            self.spin_to.setValue(self.spin_from.value())
            del blocker
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        settings.setValue("default_cutoff_days", LOOK_BACK_DAYS[self.combo_look_back.currentIndex()])
        settings.setValue("artist_range_enabled", self.chk_range.isChecked())
        settings.setValue("artist_range_start", self.spin_from.value())
        settings.setValue("artist_range_end", self.spin_to.value())
        settings.setValue("default_workers", self.spin_workers.value())
        settings.setValue("auto_export_json", self.chk_json.isChecked())
        settings.setValue("reduced_motion", self.chk_motion.isChecked())
        settings.sync()
        self.lbl_saved.setText("Changes are saved automatically." if settings.status() == QSettings.NoError
                               else "Your changes couldn't be saved. Check that wavvie can write its settings.")
        self.sync_range_controls()
        self.settings_changed.emit()

    def sync_range_controls(self):
        self.range_box.setEnabled(self.chk_range.isChecked())

    def toggle_advanced(self):
        show = self.advanced.isHidden()
        self.advanced.setVisible(show)
        self.btn_advanced.setText("Hide advanced settings" if show else "Show advanced settings")

    def set_account(self, name):
        self.lbl_account.setText(f"Connected as {name}" if name else "Not connected")
        self.btn_disconnect.setVisible(bool(name))

    def set_artist_count(self, count):
        self.artist_count = count
        for spin in (self.spin_from, self.spin_to):
            blocker = QSignalBlocker(spin)
            spin.setMaximum(max(1, count))
            del blocker
        if not QSettings("wavvie", "SpotifyPlaylistCreator").contains("artist_range_end"):
            # Until a range is saved it covers every artist, so ticking the box narrows from all of them.
            blocker = QSignalBlocker(self.spin_to)
            self.spin_to.setValue(max(1, count))
            del blocker

    def set_busy(self, busy):
        self.btn_disconnect.setEnabled(not busy)
        self.btn_refresh.setEnabled(not busy)
