"""Remembers which dates wavvie has checked and which songs each check saved."""
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from typing import Iterable, List, Optional, Set

MAX_RECORDS = 20
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


@dataclass
class CheckRecord:
    start: str                      # first day checked, ISO date
    end: str                        # day the check ran, ISO date
    ran_at: str
    songs: int = 0
    playlist_name: Optional[str] = None
    playlist_url: Optional[str] = None
    complete: bool = True
    artist_range: Optional[str] = None
    track_ids: List[str] = field(default_factory=list)

    @property
    def start_date(self) -> date:
        return date.fromisoformat(self.start)

    @property
    def end_date(self) -> date:
        return date.fromisoformat(self.end)


@dataclass(frozen=True)
class NextWindow:
    start: date
    kind: str  # 'first', 'ready', 'up_to_date' or 'finish'


class CheckHistory:
    def __init__(self, records: Iterable[CheckRecord] = ()):
        self.records: List[CheckRecord] = list(records)  # newest first

    @classmethod
    def from_json(cls, text: Optional[str]) -> 'CheckHistory':
        try:
            items = json.loads(text) if text else []
        except ValueError:
            return cls()
        known = {item.name for item in fields(CheckRecord)}
        records = []
        for item in items if isinstance(items, list) else []:
            try:
                record = CheckRecord(**{key: value for key, value in item.items() if key in known})
                date.fromisoformat(record.start)
                date.fromisoformat(record.end)
            except (AttributeError, TypeError, ValueError):
                continue
            records.append(record)
        return cls(records)

    def to_json(self) -> str:
        return json.dumps([asdict(record) for record in self.records])

    def next_window(self, today: date, look_back_days: int) -> NextWindow:
        if not self.records:
            return NextWindow(today - timedelta(days=look_back_days), 'first')
        unfinished = []
        for record in self.records:
            if record.complete:
                break
            unfinished.append(record)
        if unfinished:
            return NextWindow(min(min(record.start_date for record in unfinished), today), 'finish')
        start = min(self.records[0].end_date, today)
        return NextWindow(start, 'up_to_date' if start == today else 'ready')

    def saved_ids_since(self, start: date) -> Set[str]:
        return {track_id for record in self.records if record.end_date >= start
                for track_id in record.track_ids}

    def add(self, record: CheckRecord, today: date, look_back_days: int) -> None:
        self.records.insert(0, record)
        del self.records[MAX_RECORDS:]
        # Saved song IDs only matter where the next check can overlap them.
        keep_from = self.next_window(today, look_back_days).start
        for older in self.records:
            if older.end_date < keep_from:
                older.track_ids = []


def short_date(day: date, with_year: bool = False) -> str:
    text = f"{day.day} {MONTHS[day.month - 1]}"
    return f"{text} {day.year}" if with_year else text


def window_label(start: date, end: date) -> str:
    if start == end:
        return short_date(start)
    with_year = start.year != end.year
    return f"{short_date(start, with_year)} – {short_date(end, with_year)}"


def playlist_name(start: date, end: date) -> str:
    return f"wavvie · New releases {window_label(start, end)}"


def playlist_description(start: date, end: date) -> str:
    year = "" if start.year != end.year else f" {end.year}"
    return f"New releases from artists you follow, {window_label(start, end)}{year}. Made with wavvie."


def release_label(release_date: str) -> str:
    parts = (release_date or '').split('-')
    try:
        if len(parts) == 3:
            return f"{int(parts[2])} {MONTHS[int(parts[1]) - 1]}"
        if len(parts) == 2:
            return f"{MONTHS[int(parts[1]) - 1]} {parts[0]}"
    except (ValueError, IndexError):
        return release_date
    return release_date or ''
