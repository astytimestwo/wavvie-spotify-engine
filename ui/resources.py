import sys
from pathlib import Path

from PySide6.QtGui import QIcon

ICON_SIZES = (16, 32, 48, 64, 128, 256)


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[1]


def resource_path(name: str) -> Path:
    return resource_root() / "resources" / name


def app_icon() -> QIcon:
    """wavvie's "W" mark at every size the window decorations ask for, on Windows and Linux alike."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addFile(str(resource_path(f"wavvie_mark_{size}.png")))
    return icon
