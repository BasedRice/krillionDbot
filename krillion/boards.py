"""Leaderboards, stats and announcements: everything the bot says in chat."""
import datetime as dt
from collections import Counter
from collections.abc import Sequence
from typing import Any

import discord
from discord.utils import escape_markdown

COLOR = 0x1E90FF
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
BOARD_LIMIT = 25

Row = Any  # a sqlite3.Row (or dict) from the scores table


def rank(scores: Sequence[int]) -> list[int]:
    """Ranks for scores sorted high to low; ties share a rank: 320, 225, 225, 180 -> 1, 2, 2, 4."""
    ranks: list[int] = []
    for i, score in enumerate(scores):
        ranks.append(ranks[-1] if i and score == scores[i - 1] else i + 1)
    return ranks


def place(r: int) -> str:
    return MEDALS.get(r, f"`{r}.`")


def join_names(names: Sequence[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def name(row: Row) -> str:
    return escape_markdown(row["user_name"])


def flag(row: Row) -> str:
    return " ⚠️" if row["check_status"] == "mismatch" else ""


def board_lines(rows: Sequence[Row], limit: int = BOARD_LIMIT) -> list[str]:
    ranks = rank([row["score"] for row in rows])
    lines = []
    for r, row in zip(ranks, rows[:limit]):
        tiles = f"  {row['tiles']}" if row["tiles"] else ""
        lines.append(f"{place(r)} **{name(row)}** — {row['score']}{flag(row)}{tiles}")
    if len(rows) > limit:
        lines.append(f"…and {len(rows) - limit} more")
    return lines


def leaderboard_embed(puzzle: int, rows: Sequence[Row], record: Row | None, *,
                      final: bool = False) -> discord.Embed:
    lines = board_lines(rows)
    if final:
        winners = [name(row) for row in rows if row["score"] == rows[0]["score"]]
        verb = "wins" if len(winners) == 1 else "tie for the win"
        lines.insert(0, f"👑 **{join_names(winners)}** {verb} with **{rows[0]['score']}**!\n")
    title = f"🦐 Krillion #{puzzle} — {'Final Results' if final else 'Leaderboard'}"
    embed = discord.Embed(title=title, description="\n".join(lines), color=COLOR)
    average = round(sum(row["score"] for row in rows) / len(rows))
    footer = f"{len(rows)} player{'' if len(rows) == 1 else 's'} · avg {average}"
    if record is not None:
        footer += f" · all-time record {record['score']} ({record['user_name']}, #{record['puzzle']})"
    embed.set_footer(text=footer)
    return embed


def alltime_embed(top: Sequence[Row]) -> discord.Embed:
    best = top[0]
    header = f"Record: **{best['score']}** by **{name(best)}** on #{best['puzzle']}"
    matched = [name(row) for row in top[1:] if row["score"] == best["score"]]
    if matched:
        header += f" (matched by {join_names(matched)})"
    ranks = rank([row["score"] for row in top])
    lines = [f"{place(r)} **{name(row)}** — {row['score']}{flag(row)} · #{row['puzzle']}"
             for r, row in zip(ranks, top)]
    return discord.Embed(title="🏆 Krillion All-Time Top 10",
                         description=header + "\n\n" + "\n".join(lines), color=COLOR)


def streaks(puzzles: Sequence[int], latest: int) -> tuple[int, int]:
    """(current, longest) runs of back-to-back puzzles played. The current run
    is still alive if it reaches the latest puzzle or the one before it."""
    run = longest = 0
    prev = None
    for p in sorted(set(puzzles)):
        run = run + 1 if prev is not None and p == prev + 1 else 1
        longest = max(longest, run)
        prev = p
    current = run if prev is not None and prev >= latest - 1 else 0
    return current, longest


def stats_embed(display_name: str, rows: Sequence[Row], wins: int, latest: int) -> discord.Embed:
    best = max(rows, key=lambda row: row["score"])
    average = sum(row["score"] for row in rows) / len(rows)
    current, longest = streaks([row["puzzle"] for row in rows], latest)
    embed = discord.Embed(title=f"🦐 Krillion stats: {display_name}", color=COLOR)
    embed.add_field(name="Games", value=str(len(rows)))
    embed.add_field(name="Average", value=f"{average:.0f}")
    embed.add_field(name="Best", value=f"{best['score']} (#{best['puzzle']})")
    embed.add_field(name="Daily wins", value=str(wins))
    embed.add_field(name="Streak", value=f"{current} day{'' if current == 1 else 's'}")
    embed.add_field(name="Longest streak", value=f"{longest} day{'' if longest == 1 else 's'}")
    return embed


def announcement(*, user_id: int, display_name: str, puzzle: int, score: int,
                 record: Row | None, day_best: Row | None, latest: int | None) -> str | None:
    """What to say about a new score, given the record, the puzzle's best and
    the newest puzzle as they were before it. None for an ordinary score."""
    who = escape_markdown(display_name)
    if record is not None:
        if score > record["score"]:
            beaten = "their own" if record["user_id"] == user_id else f"{name(record)}'s"
            return (f"🚨 **NEW ALL-TIME RECORD!** {who} scored **{score}** on Krillion #{puzzle}, "
                    f"beating {beaten} {record['score']} (#{record['puzzle']})")
        if score == record["score"]:
            return f"🦐 {who} matched the all-time record of **{score}**!"
    if day_best is not None and score > day_best["score"] and latest is not None and puzzle >= latest:
        return f"👑 {who} takes the lead on Krillion #{puzzle} with **{score}**!"
    return None


def puzzle_for_day(rows: Sequence[Row], day: dt.date, tz: dt.tzinfo) -> int | None:
    """The puzzle most people played on a local calendar day: the one whose
    final results go out for that day. Rows need puzzle and posted_at."""
    counts = Counter(row["puzzle"] for row in rows
                     if dt.datetime.fromisoformat(row["posted_at"]).astimezone(tz).date() == day)
    if not counts:
        return None
    return max(counts, key=lambda p: (counts[p], p))
