"""Read a pasted Krillion result out of a Discord message.

A share looks like this (anything after the tile row is ignored):

    Krillion #90 🦐
    225

    🏮🫧🫧⬛🐟🐟🦑
"""
import re
from dataclasses import dataclass

# Points per answer tile, worked out from real posts: every share seen so far
# adds up exactly with these. A tile that isn't listed skips the check.
TILE_POINTS = {
    "\U0001FAE7": 10,  # 🫧 bubbles
    "\U0001F41F": 30,  # 🐟 fish
    "\U0001F991": 60,  # 🦑 squid
    "\U0001F3EE": 85,  # 🏮 lantern
    "⬛": 0,  # ⬛ no points
}

# The header must start the line, so a share quoted with "> " or a
# "Krillion #90" mentioned mid-sentence doesn't count.
_HEADER = re.compile(r"krillion\s*#\s*(\d{1,6})\W*", re.IGNORECASE)
_SCORE = re.compile(r"\d{1,6}")
_WORD = re.compile(r"\w")
_VARIATION_SELECTORS = {"︎", "️"}


@dataclass(frozen=True)
class Share:
    puzzle: int
    score: int
    tiles: str  # the emoji row as posted, "" if there wasn't one


def parse_share(text: str) -> Share | None:
    lines = [line.strip() for line in text.splitlines()]
    for i, line in enumerate(lines):
        header = _HEADER.fullmatch(line)
        if not header:
            continue
        rest = [line for line in lines[i + 1:] if line]
        if not rest or not _SCORE.fullmatch(rest[0]):
            continue
        tiles = rest[1] if len(rest) > 1 and not _WORD.search(rest[1]) else ""
        return Share(int(header.group(1)), int(rest[0]), tiles)
    return None


def split_tiles(row: str) -> list[str]:
    return [ch for ch in row if not ch.isspace() and ch not in _VARIATION_SELECTORS]


def unknown_tiles(share: Share) -> list[str]:
    return [t for t in split_tiles(share.tiles) if t not in TILE_POINTS]


def check_score(share: Share) -> str:
    """'ok' if the tiles add up to the posted score, 'mismatch' if they don't,
    'unchecked' when there's no tile row or it has a tile we don't know."""
    tiles = split_tiles(share.tiles)
    if not tiles or any(t not in TILE_POINTS for t in tiles):
        return "unchecked"
    return "ok" if sum(TILE_POINTS[t] for t in tiles) == share.score else "mismatch"
