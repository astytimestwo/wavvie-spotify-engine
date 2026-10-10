"""Render the README's banner, GIFs and screenshots from the real app, with made-up demo data.

Runs offscreen in a throwaway folder with throwaway settings, so it never calls Spotify or touches
your caches and preferences. From the repository root:

    python docs/media/make_media.py
"""
import importlib
import math
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter, QPainterPath,  # noqa: E402
                           QPen, QRegion)
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication([])

from ui.font_loader import load_bundled_fonts  # noqa: E402

load_bundled_fonts()
# Offscreen Qt has no system fonts to fall back on, and Agrandir has no "●", so password fields
# would draw nothing. Borrow the glyph from Windows, as the native platform does.
for fallback in ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/seguisym.ttf'):
    if Path(fallback).exists():
        QFont.insertSubstitution('Agrandir', QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(fallback))[0])
        break

from core.history import CheckRecord, NextWindow, playlist_name  # noqa: E402
from core.models import Track  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.resources import resource_path  # noqa: E402
from ui.theme import Theme  # noqa: E402
from ui.widgets.tide import Tide  # noqa: E402

DEMO_NAME = 'Sam'
ARTISTS = 248
CHECK_START, TODAY = date(2026, 10, 3), date(2026, 10, 10)
HISTORY = [
    CheckRecord('2026-09-26', '2026-10-03', 'x', songs=12, playlist_name='wavvie', playlist_url='https://open.spotify.com'),
    CheckRecord('2026-09-12', '2026-09-26', 'x', songs=7, playlist_name='wavvie', playlist_url='https://open.spotify.com'),
    CheckRecord('2026-08-29', '2026-09-12', 'x', songs=0),
]
# title, artists (the followed one first when it's a guest), release type, release date, guest appearance
SONGS = [
    ('Glasshouse Summer', ['Nova Reyes'], 'single', '2026-10-09', False),
    ('Neon Weather', ['The Paper Boats'], 'album', '2026-10-09', False),
    ('Paper Moons (feat. Nova Reyes)', ['Kite Club', 'Nova Reyes'], 'single', '2026-10-08', True),
    ('Slow Bloom', ['Marlow Lane'], 'ep', '2026-10-07', False),
    ('Salt & Static', ['Juniper Vale'], 'single', '2026-10-06', False),
    ('Afterglow Avenue', ['Kite Club'], 'single', '2026-10-06', False),
    ('Satellite Hearts', ['Ivy Atlas'], 'album', '2026-10-05', False),
    ('Low Tide Lights (Night Mix)', ['Nova Reyes'], 'single', '2026-10-04', False),
    ('Somewhere South', ['The Paper Boats', 'Marlow Lane'], 'single', '2026-10-03', True),
]
ARTWORK = [('#F2994A', '#F2C94C'), ('#56CCF2', '#2F80ED'), ('#BB6BD9', '#F2994A'), ('#6FCF97', '#219653'),
           ('#EB5757', '#F2C94C'), ('#9B51E0', '#56CCF2'), ('#2D9CDB', '#6FCF97'), ('#F2C94C', '#EB5757'),
           ('#27AE60', '#56CCF2')]
TRACKS = [Track(f't{index}', title, title, f'a{index}', kind, released, artists[-1] if guest else artists[0],
                f'f{index}', guest, 'featured' if guest else 'main', artists, title.lower(), f'demo-art-{index}')
          for index, (title, artists, kind, released, guest) in enumerate(SONGS)]
CLIENT_ID = '4c8e2b1f9a7d4e6c8b3a5f1d2e9c7a60'   # made up
CLIENT_SECRET = 'd81f3a6c5e2b4970a1c8f6e3b2d5a7c9'  # made up; shown as dots anyway


def artwork(index, size):
    """Stand-in album art: a two-colour gradient with a soft sun."""
    first, second = ARTWORK[index % len(ARTWORK)]
    image = QImage(size, size, QImage.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor(first))
    gradient.setColorAt(1, QColor(second))
    painter.fillRect(image.rect(), gradient)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 70))
    painter.drawEllipse(QPointF(size * (0.3 + 0.08 * (index % 4)), size * 0.62), size * 0.24, size * 0.24)
    painter.end()
    return image


def settle(rounds=6):
    for _ in range(rounds):
        app.processEvents()
        QTest.qWait(10)


def to_pil(image):
    image = image.convertToFormat(QImage.Format_RGB888)
    data = bytes(image.constBits())
    return Image.frombuffer('RGB', (image.width(), image.height()), data, 'raw', 'RGB', image.bytesPerLine(), 1)


def frame(window):
    settle()
    return to_pil(window.grab().toImage())


def still(window, name, scale=2):
    """A sharp screenshot: the window drawn at twice its size, as a 200% display would show it."""
    settle()
    image = QImage(window.size() * scale, QImage.Format_RGB32)
    image.setDevicePixelRatio(scale)
    window.render(image)
    image.setDevicePixelRatio(1)
    image.save(str(OUT / name))
    print('saved', name)


def save_gif(name, frames):
    """frames: [(PIL image, milliseconds)]. One shared palette keeps colours from flickering between frames."""
    images = [image for image, _ in frames]
    samples = images[::max(1, len(images) // 6)] + [images[-1]]
    sheet = Image.new('RGB', (images[0].width, images[0].height * len(samples)))
    for row, sample in enumerate(samples):
        sheet.paste(sample, (0, images[0].height * row))
    palette = sheet.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    paletted = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    paletted[0].save(OUT / name, save_all=True, append_images=paletted[1:], loop=0,
                     duration=[milliseconds for _, milliseconds in frames], optimize=True)
    print('saved', name, f'{(OUT / name).stat().st_size // 1024} KB, {len(frames)} frames')


def pressed(button):
    """The primary button as the pointer presses it."""
    button.setStyleSheet(f'background: {Theme.SUN_HOVER};')
    return lambda: button.setStyleSheet('')


def banner(name, width=800, height=280, scale=2):
    image = QImage(width * scale, height * scale, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(scale, scale)
    card = QPainterPath()
    card.addRoundedRect(QRectF(0, 0, width, height), 22, 22)
    painter.setClipPath(card)
    painter.fillRect(QRectF(0, 0, width, height), QColor(Theme.DEEP))
    painter.save()  # the app's tide, a little flatter to suit the banner
    painter.translate(0, height)
    painter.scale(1, 0.72)
    painter.translate(0, -Tide.HEIGHT)
    tide = Tide()
    tide.resize(width, Tide.HEIGHT)
    tide.render(painter, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    painter.restore()
    logo = QSvgRenderer(str(resource_path('wavvie_wordmark.svg')))
    logo_height = 66
    logo.render(painter, QRectF(56, 46, logo_height * logo.defaultSize().width() / logo.defaultSize().height(), logo_height))
    font = QFont(Theme.FONT_BODY)
    font.setPixelSize(19)
    painter.setFont(font)
    painter.setPen(QColor(Theme.FOAM))
    painter.drawText(QPointF(58, 152), 'New music from the artists you follow,')
    painter.setPen(QColor(Theme.MIST))
    painter.drawText(QPointF(58, 180), 'saved to a private Spotify playlist.')
    wave = QPainterPath()  # the progress ripple from the checking screen
    left, right, middle = 470, 744, 98
    wave.moveTo(left, middle)
    x = left
    while x < right - 96:
        x += 2
        wave.lineTo(x, middle + 6 * math.sin((x - left) / 15))
    painter.setPen(QPen(QColor(Theme.SUN), 3))
    painter.drawPath(wave)
    painter.setPen(QPen(QColor(Theme.LINE), 2))
    painter.drawLine(QPointF(x, middle), QPointF(right, middle))
    painter.end()
    image.save(str(OUT / name))
    print('saved', name)


def main():
    workspace = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    os.chdir(workspace.name)
    try:
        render_all(workspace)
    finally:
        os.chdir(REPO)  # Windows can't remove a folder the process is standing in
        workspace.cleanup()


def render_all(workspace):
    ini = Path(workspace.name) / 'settings.ini'

    class DemoSettings(QSettings):
        def __init__(self, *args, **kwargs):
            super().__init__(str(ini), QSettings.IniFormat)

    for module in ('ui.main_window', 'ui.pages.settings_page'):
        patch.object(importlib.import_module(module), 'QSettings', DemoSettings).start()
    patch('ui.main_window.load_environment').start()
    patch.dict(os.environ, {'SPOTIPY_CLIENT_ID': 'demo', 'SPOTIPY_CLIENT_SECRET': 'demo'}).start()
    patch.object(MainWindow, 'load_artwork', lambda self, url: None).start()  # demo art is set by hand
    with patch.object(MainWindow, 'recheck_config'):
        window = MainWindow()
    window.resize(900, 680)
    window.show()
    window.activateWindow()
    QTest.qWaitForWindowActive(window, 2000)
    home, settings = window.home_page, window.settings_page
    window.service.user_data = {'id': 'demo', 'display_name': DEMO_NAME}
    window.avatar.set_user(DEMO_NAME)
    settings.set_account(DEMO_NAME)
    settings.set_artist_count(ARTISTS)
    window.followed_count = ARTISTS
    home.set_reduced_motion(True)  # the ripple is stepped by hand, one frame at a time

    banner('banner.png')

    # First run: connect a Spotify app, approve it in the browser, land on Home.
    setup = window.setup_page
    window.show_page(setup)
    frames = [(frame(window), 1200)]
    setup.txt_id.setFocus()
    for end in range(4, len(CLIENT_ID) + 1, 4):
        setup.txt_id.setText(CLIENT_ID[:end])
        frames.append((frame(window), 70))
    setup.txt_secret.setFocus()
    for end in range(4, len(CLIENT_SECRET) + 1, 4):
        setup.txt_secret.setText(CLIENT_SECRET[:end])
        frames.append((frame(window), 70))
    frames.append((frame(window), 600))
    release = pressed(setup.btn_save)
    frames.append((frame(window), 220))
    release()
    window.sign_in_page.show_waiting()
    window.show_page(window.sign_in_page)
    frames.append((frame(window), 1700))
    home.show_ready(NextWindow(date(2026, 9, 10), 'first'), ARTISTS, 30, [])
    window.show_page(home)
    frames.append((frame(window), 2800))
    save_gif('setup.gif', frames)

    # A check: one press, a ripple while every artist is checked, then the new playlist.
    home.show_ready(NextWindow(CHECK_START, 'ready'), ARTISTS, 30, HISTORY)
    frames = [(frame(window), 2000)]
    release = pressed(home.btn_primary)
    frames.append((frame(window), 220))
    release()
    home.show_checking(ARTISTS, CHECK_START)
    steps = 36
    for step in range(steps + 1):
        home.update_progress(round(ARTISTS * step / steps), ARTISTS, round(len(TRACKS) * step / steps))
        home.wave.advance()
        frames.append((frame(window), 70))
    home.show_saving(len(TRACKS))
    for _ in range(10):
        home.wave.advance()
        frames.append((frame(window), 70))
    home.show_done(playlist_name(CHECK_START, TODAY), 'https://open.spotify.com', TRACKS)
    for index, track in enumerate(TRACKS):
        home.set_artwork(track.album_artwork_url, artwork(index, 80))
    frames.append((frame(window), 4200))
    save_gif('check.gif', frames)
    still(window, 'done.png')

    window.show_page(settings)
    settings.toggle_advanced()
    still(window, 'settings.png')
    window.close()


if __name__ == '__main__':
    main()
