"""SQLite storage: every score, the watched channel per server, and bookkeeping.

Records and leaderboards are always worked out from the scores table, so
removing a fake score automatically restores whatever it pushed down.
"""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    guild_id     INTEGER NOT NULL,
    puzzle       INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    user_name    TEXT    NOT NULL,
    score        INTEGER NOT NULL,
    tiles        TEXT    NOT NULL,
    check_status TEXT    NOT NULL,
    channel_id   INTEGER NOT NULL,
    message_id   INTEGER NOT NULL,
    posted_at    TEXT    NOT NULL,
    PRIMARY KEY (guild_id, puzzle, user_id)
);
CREATE INDEX IF NOT EXISTS scores_by_score ON scores (guild_id, score DESC, message_id);
CREATE INDEX IF NOT EXISTS scores_by_time ON scores (guild_id, posted_at);

CREATE TABLE IF NOT EXISTS watch (
    guild_id        INTEGER PRIMARY KEY,
    channel_id      INTEGER NOT NULL,
    last_message_id INTEGER
);

-- Scores an admin removed, so a rescan doesn't bring them back.
CREATE TABLE IF NOT EXISTS removed (
    message_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS results_posted (
    guild_id INTEGER NOT NULL,
    puzzle   INTEGER NOT NULL,
    PRIMARY KEY (guild_id, puzzle)
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # --- scores -----------------------------------------------------------

    def save_score(self, *, guild_id: int, puzzle: int, user_id: int, user_name: str,
                   score: int, tiles: str, check_status: str, channel_id: int,
                   message_id: int, posted_at: str) -> str:
        """Save a player's score for a puzzle. Their first post counts.

        Returns 'new', 'duplicate' (they already posted this puzzle earlier),
        'same' (this exact message was saved before, e.g. on a rescan) or
        'replaced' (this post is older than the one saved, which can happen
        while catching up on history).
        """
        row = self.db.execute(
            "SELECT message_id FROM scores WHERE guild_id = ? AND puzzle = ? AND user_id = ?",
            (guild_id, puzzle, user_id),
        ).fetchone()
        values = (user_name, score, tiles, check_status, channel_id, message_id, posted_at,
                  guild_id, puzzle, user_id)
        if row is None:
            self.db.execute(
                "INSERT INTO scores (user_name, score, tiles, check_status, channel_id, message_id,"
                " posted_at, guild_id, puzzle, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
            return "new"
        if message_id > row["message_id"]:
            return "duplicate"
        self.db.execute(
            "UPDATE scores SET user_name = ?, score = ?, tiles = ?, check_status = ?, channel_id = ?,"
            " message_id = ?, posted_at = ? WHERE guild_id = ? AND puzzle = ? AND user_id = ?",
            values,
        )
        return "same" if message_id == row["message_id"] else "replaced"

    def remove_score(self, guild_id: int, puzzle: int, user_id: int) -> sqlite3.Row | None:
        row = self.db.execute(
            "SELECT * FROM scores WHERE guild_id = ? AND puzzle = ? AND user_id = ?",
            (guild_id, puzzle, user_id),
        ).fetchone()
        if row is not None:
            self.db.execute("INSERT OR IGNORE INTO removed (message_id) VALUES (?)", (row["message_id"],))
            self.db.execute(
                "DELETE FROM scores WHERE guild_id = ? AND puzzle = ? AND user_id = ?",
                (guild_id, puzzle, user_id),
            )
        return row

    def is_removed(self, message_id: int) -> bool:
        return self.db.execute("SELECT 1 FROM removed WHERE message_id = ?", (message_id,)).fetchone() is not None

    def puzzle_scores(self, guild_id: int, puzzle: int) -> list[sqlite3.Row]:
        """A puzzle's scores, best first; ties go to whoever posted first."""
        return self.db.execute(
            "SELECT * FROM scores WHERE guild_id = ? AND puzzle = ? ORDER BY score DESC, message_id",
            (guild_id, puzzle),
        ).fetchall()

    def puzzle_best(self, guild_id: int, puzzle: int) -> sqlite3.Row | None:
        rows = self.puzzle_scores(guild_id, puzzle)
        return rows[0] if rows else None

    def top_scores(self, guild_id: int, limit: int = 10) -> list[sqlite3.Row]:
        """Best single scores ever; on a tie the earliest post ranks first."""
        return self.db.execute(
            "SELECT * FROM scores WHERE guild_id = ? ORDER BY score DESC, message_id LIMIT ?",
            (guild_id, limit),
        ).fetchall()

    def record(self, guild_id: int) -> sqlite3.Row | None:
        rows = self.top_scores(guild_id, 1)
        return rows[0] if rows else None

    def latest_puzzle(self, guild_id: int) -> int | None:
        return self.db.execute("SELECT MAX(puzzle) FROM scores WHERE guild_id = ?", (guild_id,)).fetchone()[0]

    def player_scores(self, guild_id: int, user_id: int) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM scores WHERE guild_id = ? AND user_id = ? ORDER BY puzzle",
            (guild_id, user_id),
        ).fetchall()

    def daily_wins(self, guild_id: int, user_id: int) -> int:
        """Finished puzzles where the player had the top score (ties all count).
        A puzzle is finished once a newer one exists or its results went out."""
        return self.db.execute(
            """
            SELECT COUNT(*) FROM scores s
            WHERE s.guild_id = ? AND s.user_id = ?
              AND s.score = (SELECT MAX(score) FROM scores
                             WHERE guild_id = s.guild_id AND puzzle = s.puzzle)
              AND (s.puzzle < (SELECT MAX(puzzle) FROM scores WHERE guild_id = s.guild_id)
                   OR s.puzzle IN (SELECT puzzle FROM results_posted WHERE guild_id = s.guild_id))
            """,
            (guild_id, user_id),
        ).fetchone()[0]

    def scores_posted_after(self, guild_id: int, posted_at: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT puzzle, posted_at FROM scores WHERE guild_id = ? AND posted_at >= ?",
            (guild_id, posted_at),
        ).fetchall()

    # --- watched channel --------------------------------------------------

    def set_channel(self, guild_id: int, channel_id: int) -> None:
        """Watch a channel, starting its history import from the beginning."""
        self.db.execute(
            "INSERT INTO watch (guild_id, channel_id, last_message_id) VALUES (?, ?, NULL)"
            " ON CONFLICT (guild_id) DO UPDATE SET channel_id = excluded.channel_id, last_message_id = NULL",
            (guild_id, channel_id),
        )

    def watched_channel(self, guild_id: int) -> int | None:
        row = self.db.execute("SELECT channel_id FROM watch WHERE guild_id = ?", (guild_id,)).fetchone()
        return row["channel_id"] if row else None

    def watches(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT guild_id, channel_id, last_message_id FROM watch").fetchall()

    def advance_checkpoint(self, guild_id: int, message_id: int) -> None:
        """Remember the newest message read, so a restart catches up from there."""
        self.db.execute(
            "UPDATE watch SET last_message_id = MAX(COALESCE(last_message_id, 0), ?) WHERE guild_id = ?",
            (message_id, guild_id),
        )

    # --- daily results ----------------------------------------------------

    def results_posted(self, guild_id: int, puzzle: int) -> bool:
        return self.db.execute(
            "SELECT 1 FROM results_posted WHERE guild_id = ? AND puzzle = ?", (guild_id, puzzle)
        ).fetchone() is not None

    def mark_results_posted(self, guild_id: int, puzzle: int) -> None:
        self.db.execute("INSERT OR IGNORE INTO results_posted (guild_id, puzzle) VALUES (?, ?)", (guild_id, puzzle))
