"""
LRC (Lyrics) file parser.
Supports:
  [mm:ss.xx] line  — standard synced lyrics
  [ar:Artist]      — ID3-like LRC metadata tags
Returns (metadata_dict, list_of_(ms_int, text))
"""
import re
from typing import Optional

_RE_TIME  = re.compile(r"\[(\d{1,2}):(\d{2})\.(\d{2,3})\]")
_RE_META  = re.compile(r"\[(\w+):(.+)\]")


def parse_lrc(content: str) -> tuple[dict, list[tuple[int, str]]]:
    metadata: dict[str, str] = {}
    lines: list[tuple[int, str]] = []

    for raw in content.splitlines():
        raw = raw.strip()
        if not raw:
            continue

        # Try time-tag first
        m = _RE_TIME.match(raw)
        if m:
            minutes = int(m.group(1))
            seconds = int(m.group(2))
            millis  = int(m.group(3).ljust(3, "0"))
            ms      = (minutes * 60 + seconds) * 1000 + millis
            text    = raw[m.end():].strip()
            lines.append((ms, text))
            continue

        # Try metadata tag
        m = _RE_META.match(raw)
        if m:
            metadata[m.group(1).lower()] = m.group(2).strip()

    lines.sort(key=lambda x: x[0])
    return metadata, lines


def lrc_to_plain(lines: list[tuple[int, str]]) -> str:
    return "\n".join(t for _, t in lines if t)
