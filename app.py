import os
import sys


def use_app_folder():
    """A packaged wavvie keeps its .env and caches beside the executable, wherever it was started from."""
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))


# Before main's import-time .env loading, so a packaged app reads and writes its own folder.
use_app_folder()

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from main import load_environment  # noqa: E402
from ui.font_loader import load_bundled_fonts  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.resources import app_icon  # noqa: E402


def main():
    # Load env variables before starting
    load_environment()

    app = QApplication(sys.argv)
    app.setApplicationName("wavvie")
    app.setApplicationVersion("1.0.0")
    app.setDesktopFileName("wavvie")
    app.setWindowIcon(app_icon())
    load_bundled_fonts()

    window = MainWindow()
    window.show()
    if os.environ.get("WAVVIE_SMOKE_TEST"):
        # CI launches each release build once; quitting on its own proves the build starts.
        QTimer.singleShot(1500, app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
