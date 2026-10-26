"""Entries are write-once JSON files in website/data/, committed to the repo by the daily Action."""

import json
import os
import re
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "website" / "data"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _path(date: str) -> Path:
    # the date becomes a filename, so this is where path traversal is stopped
    if not DATE.match(date):
        raise ValueError(f"bad date: {date!r}")
    return DATA_DIR / f"{date}.json"


def _atomic_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp, 0o644)  # mkstemp creates 0600; the site may read as another user
        os.replace(tmp, path)  # a crash mid-write can't leave a half-written entry behind
    except BaseException:
        os.unlink(tmp)
        raise


def write(entry: dict, *, force: bool = False) -> None:
    path = _path(entry["metadata"]["date"])
    if path.exists() and not force:
        raise FileExistsError(f"{path.name} exists; pass force=True to regenerate it")
    _atomic_write(path, entry)


def read(date: str) -> dict | None:
    path = _path(date)
    return json.loads(path.read_text()) if path.exists() else None


def list_dates() -> list[str]:
    return sorted(p.stem for p in DATA_DIR.glob("????-??-??.json"))
