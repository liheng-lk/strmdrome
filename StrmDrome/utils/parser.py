"""
Smart Filename & Path Parser for StrmDrome v2.

Handles any of the following .strm file naming conventions and produces
a normalized ParsedTrack object:

  Artist/Album/01 - Title.strm            (standard Navidrome layout)
  Artist - Album - 01 - Title.strm        (flat with artist-album prefix)
  01. Title.strm  (in Artist/Album/ dir)  (numbered only, directory inferred)
  Title [2020].strm                       (year tag in brackets)
  Title (feat. Somebody).strm             (featuring tag)
  Artist - Title.strm                     (2-part hyphen)
  Title.strm                              (bare title, rely on directory only)
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedTrack:
    title:      str
    artist:     Optional[str] = None
    album:      Optional[str] = None
    track_num:  int = 0
    disc_num:   int = 1
    year:       int = 0
    featuring:  Optional[str] = None    # extra artist from "(feat. X)"


# ── Compiled patterns ────────────────────────────────────────────────────────

# Leading track number: "01 - ", "01. ", "1 "
_RE_TRACK = re.compile(r"^(\d{1,3})[.\-\s]+(.+)$")

# Year in brackets or parens:  "[2020]" or "(2020)"
_RE_YEAR = re.compile(r"[\[\(]((?:19|20)\d{2})[\]\)]")

# Featuring: "(feat. X)" or "(ft. X)" or "(with X)"
_RE_FEAT = re.compile(r"\s*[\[\(](?:feat\.|ft\.|with)\s+([^\)\]]+)[\)\]]", re.IGNORECASE)

# Disc number embedded in album name: "Album (Disc 2)" or "Album CD1"
_RE_DISC = re.compile(r"(?:[\s\-]?(?:disc|cd|disk)\s*(\d+))", re.IGNORECASE)


def _strip_ext(name: str) -> str:
    """Remove .strm extension."""
    return os.path.splitext(name)[0]


def _extract_year(s: str) -> tuple[str, int]:
    """Remove first year tag from string, return (cleaned_str, year)."""
    m = _RE_YEAR.search(s)
    if m:
        return s[:m.start()].strip() + s[m.end():].strip(), int(m.group(1))
    return s, 0


def _extract_feat(s: str) -> tuple[str, Optional[str]]:
    """Remove featuring clause, return (cleaned_str, featuring_artist)."""
    m = _RE_FEAT.search(s)
    if m:
        return (s[:m.start()] + s[m.end():]).strip(), m.group(1).strip()
    return s, None


def _split_by_sep(name: str) -> list[str]:
    """Split on ' - ' (the universal separator), collapse spaces."""
    return [p.strip() for p in name.split(" - ") if p.strip()]


def parse_strm_path(strm_path: str, music_root: str = "") -> ParsedTrack:
    """
    Given an absolute path to a .strm file and the music root directory,
    extract artist/album/title via cascading heuristics.

    Priority:
      1  Directory depth inference (Artist/Album/Song)
      2  Filename part-splitting on ' - '
      3  Track-number prefix stripping
      4  Bracket/paren annotations ([year], feat., disc N)
    """
    rel  = os.path.relpath(strm_path, music_root) if music_root else strm_path
    parts = rel.replace("\\", "/").split("/")
    # parts[0..n-2] are directories, parts[-1] is filename
    raw_name = _strip_ext(parts[-1])
    dir_parts = parts[:-1]   # e.g. ["Taylor Swift", "1989"]

    title    = raw_name
    artist   = None
    album    = None
    track    = 0
    disc     = 1
    year     = 0
    feat     = None

    # ── Step 1: directory inference ──────────────────────────────────────────
    if len(dir_parts) >= 2:
        artist = dir_parts[-2]
        album  = dir_parts[-1]
        # Disc embedded in album dir name: "1989 (Disc 1)"
        dm = _RE_DISC.search(album)
        if dm:
            disc  = int(dm.group(1))
            album = album[:dm.start()].strip()
    elif len(dir_parts) == 1:
        artist = dir_parts[0]

    # ── Step 2: extract year / feat from raw title ───────────────────────────
    title, year      = _extract_year(raw_name)
    title, feat      = _extract_feat(title)

    # ── Step 3: track number prefix from title ───────────────────────────────
    m = _RE_TRACK.match(title)
    if m:
        track = int(m.group(1))
        title = m.group(2).strip()

    # ── Step 4: try splitting title on ' - ' to infer missing artist/album ───
    chunks = _split_by_sep(title)

    if len(chunks) >= 3 and not artist:
        # "Artist - Album - Title"  or  "Artist - 01 - Title"
        artist = chunks[0]
        # Check if second chunk is numeric (track num)
        if chunks[1].isdigit():
            track = int(chunks[1])
            title = " - ".join(chunks[2:])
        else:
            album = chunks[1]
            title = " - ".join(chunks[2:])

    elif len(chunks) == 2:
        if not artist:
            # "Artist - Title"  (no album from dir → album unknown)
            artist = chunks[0]
            title  = chunks[1]
        else:
            # "01 - Title" already handled by track regex; else just use as-is
            title = " - ".join(chunks)

    # ── Step 5: strip trailing feat from artist if still there ───────────────
    if artist:
        artist, f2 = _extract_feat(artist)
        feat = feat or f2
        artist, _  = _extract_year(artist)
        artist = artist.strip(" -.")

    # ── Step 6: clean up title ───────────────────────────────────────────────
    title = title.strip(" -.")

    return ParsedTrack(
        title      = title or raw_name,
        artist     = artist,
        album      = album,
        track_num  = track,
        disc_num   = disc,
        year       = year,
        featuring  = feat,
    )
