import sys
from pathlib import Path


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[1]


def resource_path(name: str) -> Path:
    return resource_root() / "resources" / name
