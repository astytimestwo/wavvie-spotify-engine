import zipfile

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QFontDatabase

from ui.resources import resource_path

FONT_ARCHIVES = (
    "loubag-regular-1782520865-0.zip",
    "loubag-ultralight-1782520861-0.zip",
    "Agrandir-Font-Family.zip",
)


def load_bundled_fonts() -> set[str]:
    loaded_families: set[str] = set()

    for archive_name in FONT_ARCHIVES:
        archive_path = resource_path(archive_name)
        if not archive_path.exists():
            continue

        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                normalized = member.replace("\\", "/")
                if normalized.startswith("__MACOSX/") or not normalized.lower().endswith((".otf", ".ttf")):
                    continue

                font_id = QFontDatabase.addApplicationFontFromData(QByteArray(archive.read(member)))
                if font_id < 0:
                    continue

                loaded_families.update(QFontDatabase.applicationFontFamilies(font_id))

    return loaded_families
