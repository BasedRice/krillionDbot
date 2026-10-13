"""krillionDbot: picks up Krillion scores in Discord and keeps the leaderboards.

Start it with run_bot.bat (or `python bot.py`). Setup steps are in README.md.
"""
import asyncio
import datetime as dt
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from krillion import boards
from krillion.parsing import check_score, parse_share, unknown_tiles
from krillion.storage import Store

load_dotenv(Path(__file__).with_name(".env"))

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
TOKEN_PLACEHOLDER = "paste-your-token-here"
TZ = ZoneInfo(os.getenv("TIMEZONE") or "America/New_York")
RESULTS_TIME = dt.time.fromisoformat(os.getenv("RESULTS_TIME") or "00:00").replace(tzinfo=TZ)
VERIFY_SCORES = (os.getenv("VERIFY_SCORES") or "true").strip().lower() not in {"0", "false", "no", "off"}
# Kept outside OneDrive by default: OneDrive syncing a half-written database can corrupt it.
DB_PATH = Path(os.getenv("DB_PATH") or Path(os.getenv("LOCALAPPDATA") or Path.home()) / "krillionDbot" / "krillion.db")

# What the bot needs in the watched channel, with the names Discord shows.
NEEDED_PERMISSIONS = {
    "view_channel": "View Channel",
    "read_message_history": "Read Message History",
    "send_messages": "Send Messages",
    "add_reactions": "Add Reactions",
    "embed_links": "Embed Links",
}

log = logging.getLogger("krillion")


class KrillionBot(discord.Client):
    def __init__(self, store: Store):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.store = store
        self.tree = app_commands.CommandTree(self)
        for command in (leaderboard, alltime, stats, Admin()):
            self.tree.add_command(command)
        self.tree.error(command_error)
        self.synced_guilds: set[int] = set()
        # Held while reading channel history, so live messages don't move the
        # catch-up checkpoint past messages that haven't been read yet.
        self.reading_history = asyncio.Lock()

    async def setup_hook(self) -> None:
        self.daily_results.start()

    async def on_ready(self) -> None:
        log.info("Logged in as %s, in %d server(s)", self.user, len(self.guilds))
        for guild in self.guilds:
            await self.sync_commands(guild)
        await self.catch_up()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.sync_commands(guild)

    async def sync_commands(self, guild: discord.Guild) -> None:
        # Per-server sync shows new commands right away (global sync can lag).
        if guild.id in self.synced_guilds:
            return
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.synced_guilds.add(guild.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.channel.id != self.store.watched_channel(message.guild.id):
            return
        await self.take(message, live=True, react=True)
        if not self.reading_history.locked():
            self.store.advance_checkpoint(message.guild.id, message.id)

    async def take(self, message: discord.Message, *, live: bool, react: bool) -> tuple[str, str] | None:
        """Save the Krillion score in a message, if there is one.
        Returns (outcome, check), see Store.save_score and check_score."""
        if message.author.bot or message.guild is None:
            return None
        share = parse_share(message.content)
        if share is None or self.store.is_removed(message.id):
            return None
        check = check_score(share) if VERIFY_SCORES else "unchecked"
        if VERIFY_SCORES and check == "unchecked" and share.tiles:
            log.info("Unknown tile(s) %s in %s's score, skipped the points check",
                     unknown_tiles(share), message.author)
        guild_id = message.guild.id
        before = None
        if live:
            before = dict(record=self.store.record(guild_id),
                          day_best=self.store.puzzle_best(guild_id, share.puzzle),
                          latest=self.store.latest_puzzle(guild_id))
        outcome = self.store.save_score(
            guild_id=guild_id, puzzle=share.puzzle, user_id=message.author.id,
            user_name=message.author.display_name, score=share.score, tiles=share.tiles,
            check_status=check, channel_id=message.channel.id, message_id=message.id,
            posted_at=message.created_at.isoformat(timespec="seconds"),
        )
        if react:
            await self.react(message, outcome, check)
        if before is not None and outcome == "new" and check != "mismatch":
            text = boards.announcement(user_id=message.author.id, display_name=message.author.display_name,
                                       puzzle=share.puzzle, score=share.score, **before)
            if text:
                await message.reply(text)
        return outcome, check

    async def react(self, message: discord.Message, outcome: str, check: str) -> None:
        emojis = ["🔁"] if outcome == "duplicate" else ["✅"] + (["⚠️"] if check == "mismatch" else [])
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException as e:
                log.warning("Couldn't react to %s: %s", message.jump_url, e)
                return

    async def import_history(self, channel: discord.TextChannel, *, after: int | None, react: bool) -> Counter:
        """Read a channel's messages oldest first (all of them, or those after a
        message id) and save every score. Counts outcomes plus 'mismatch'."""
        counts: Counter = Counter()
        start = discord.Object(id=after) if after else None
        async for message in channel.history(limit=None, after=start, oldest_first=True):
            result = await self.take(message, live=False, react=react)
            if result:
                outcome, check = result
                counts[outcome] += 1
                if check == "mismatch" and outcome != "duplicate":
                    counts["mismatch"] += 1
            self.store.advance_checkpoint(channel.guild.id, message.id)
        return counts

    async def catch_up(self) -> None:
        """Pick up scores posted in the watched channels while the bot was offline."""
        async with self.reading_history:
            for watch in self.store.watches():
                channel = self.get_channel(watch["channel_id"])
                if not isinstance(channel, discord.TextChannel):
                    log.warning("Can't see the watched channel %s any more", watch["channel_id"])
                    continue
                after = watch["last_message_id"]
                try:
                    # Only react when catching up; an interrupted first import stays quiet.
                    counts = await self.import_history(channel, after=after, react=after is not None)
                except discord.HTTPException:
                    log.exception("Couldn't catch up on #%s", channel)
                    continue
                if counts["new"]:
                    log.info("Caught up on #%s: %d new score(s)", channel, counts["new"])

    @tasks.loop(time=RESULTS_TIME)
    async def daily_results(self) -> None:
        # The day that just ended: a midnight or morning post covers yesterday.
        day = (dt.datetime.now(TZ) - dt.timedelta(hours=12)).date()
        for watch in self.store.watches():
            try:
                await self.post_results(watch["guild_id"], watch["channel_id"], day)
            except Exception:
                log.exception("Couldn't post daily results for server %s", watch["guild_id"])

    @daily_results.before_loop
    async def before_daily_results(self) -> None:
        await self.wait_until_ready()

    async def post_results(self, guild_id: int, channel_id: int, day: dt.date) -> int | None:
        """Post the final standings for the puzzle most people played on `day`."""
        since = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(), TZ)
        rows = self.store.scores_posted_after(
            guild_id, since.astimezone(dt.timezone.utc).isoformat(timespec="seconds"))
        puzzle = boards.puzzle_for_day(rows, day, TZ)
        if puzzle is None or self.store.results_posted(guild_id, puzzle):
            return None
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Can't see channel %s to post results for #%s", channel_id, puzzle)
            return None
        scores = self.store.puzzle_scores(guild_id, puzzle)
        await channel.send(embed=boards.leaderboard_embed(puzzle, scores, self.store.record(guild_id), final=True))
        self.store.mark_results_posted(guild_id, puzzle)
        log.info("Posted final results for Krillion #%s in #%s", puzzle, channel)
        return puzzle

    async def unreact(self, row) -> None:
        """Take the bot's ✅ off a removed score's message, if it's still there."""
        channel = self.get_channel(row["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(row["message_id"])
            await message.remove_reaction("✅", self.user)
        except discord.HTTPException:
            pass


def missing_permissions(channel: discord.TextChannel) -> list[str]:
    perms = channel.permissions_for(channel.guild.me)
    return [label for perm, label in NEEDED_PERMISSIONS.items() if not getattr(perms, perm)]


def import_summary(counts: Counter) -> str:
    found = counts["new"] + counts["replaced"] + counts["same"]
    text = f"Found **{found}** score{'' if found == 1 else 's'} in its history"
    if counts["mismatch"]:
        text += f" ({counts['mismatch']} flagged ⚠️ because the emoji row didn't add up to the score)"
    return text + "."


# --- slash commands ----------------------------------------------------------

@app_commands.command(description="Krillion leaderboard for the newest puzzle, or any puzzle number")
@app_commands.describe(puzzle="Puzzle number, e.g. 90 (leave empty for the newest)")
@app_commands.guild_only()
async def leaderboard(interaction: discord.Interaction, puzzle: Optional[app_commands.Range[int, 1]] = None) -> None:
    store = interaction.client.store
    puzzle = puzzle or store.latest_puzzle(interaction.guild_id)
    rows = store.puzzle_scores(interaction.guild_id, puzzle) if puzzle else []
    if not rows:
        text = f"Nobody has posted Krillion #{puzzle} yet." if puzzle else "No Krillion scores yet."
        await interaction.response.send_message(text, ephemeral=True)
        return
    embed = boards.leaderboard_embed(puzzle, rows, store.record(interaction.guild_id))
    await interaction.response.send_message(embed=embed)


@app_commands.command(description="All-time Krillion record and top 10 scores")
@app_commands.guild_only()
async def alltime(interaction: discord.Interaction) -> None:
    top = interaction.client.store.top_scores(interaction.guild_id, 10)
    if not top:
        await interaction.response.send_message("No Krillion scores yet.", ephemeral=True)
        return
    await interaction.response.send_message(embed=boards.alltime_embed(top))


@app_commands.command(description="A player's Krillion stats")
@app_commands.describe(user="Whose stats (leave empty for yours)")
@app_commands.guild_only()
async def stats(interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
    store = interaction.client.store
    user = user or interaction.user
    rows = store.player_scores(interaction.guild_id, user.id)
    if not rows:
        await interaction.response.send_message(f"{user.display_name} hasn't posted a Krillion score yet.",
                                                ephemeral=True)
        return
    embed = boards.stats_embed(user.display_name, rows, store.daily_wins(interaction.guild_id, user.id),
                               store.latest_puzzle(interaction.guild_id))
    await interaction.response.send_message(embed=embed)


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class Admin(app_commands.Group, name="krillion", description="krillionDbot settings (admins only)"):

    @app_commands.command(description="Watch a channel for Krillion scores and import its history")
    @app_commands.describe(channel="Channel to watch (leave empty for this one)")
    async def setchannel(self, interaction: discord.Interaction,
                         channel: Optional[discord.TextChannel] = None) -> None:
        bot: KrillionBot = interaction.client
        channel = channel or interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Pick a regular text channel.", ephemeral=True)
            return
        missing = missing_permissions(channel)
        if missing:
            await interaction.response.send_message(
                f"I can't work in {channel.mention} yet. I'm missing: {', '.join(missing)}.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        async with bot.reading_history:
            bot.store.set_channel(channel.guild.id, channel.id)
            counts = await bot.import_history(channel, after=None, react=False)
        await interaction.followup.send(f"🦐 Now watching {channel.mention}. {import_summary(counts)}")

    @app_commands.command(description="Delete a player's score for one puzzle")
    @app_commands.describe(user="Whose score", puzzle="Puzzle number, e.g. 90")
    async def remove(self, interaction: discord.Interaction, user: discord.User,
                     puzzle: app_commands.Range[int, 1]) -> None:
        bot: KrillionBot = interaction.client
        row = bot.store.remove_score(interaction.guild_id, puzzle, user.id)
        if row is None:
            await interaction.response.send_message(f"{user.display_name} has no score for Krillion #{puzzle}.",
                                                    ephemeral=True)
            return
        await bot.unreact(row)
        await interaction.response.send_message(
            f"Removed {row['user_name']}'s {row['score']} on Krillion #{puzzle}.", ephemeral=True)

    @app_commands.command(description="Re-read the watched channel's whole history for missed scores")
    async def rescan(self, interaction: discord.Interaction) -> None:
        bot: KrillionBot = interaction.client
        channel_id = bot.store.watched_channel(interaction.guild_id)
        channel = bot.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("No channel set yet. Use `/krillion setchannel` first.",
                                                    ephemeral=True)
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        async with bot.reading_history:
            counts = await bot.import_history(channel, after=None, react=False)
        added = counts["new"] + counts["replaced"]
        await interaction.followup.send(
            f"Rescanned {channel.mention}: {added} score{'' if added == 1 else 's'} added. {import_summary(counts)}")


async def command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    name = interaction.command.qualified_name if interaction.command else "?"
    log.error("/%s failed", name, exc_info=error)
    text = "Something went wrong with that command. The bot's window has the details."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        pass


def main() -> None:
    if not TOKEN or TOKEN == TOKEN_PLACEHOLDER:
        raise SystemExit("No bot token yet: open .env and paste it after DISCORD_TOKEN= (README.md, step 2).")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    discord.utils.setup_logging(root=True)
    log.info("Scores database: %s", DB_PATH)
    try:
        KrillionBot(Store(DB_PATH)).run(TOKEN, log_handler=None)
    except discord.LoginFailure:
        raise SystemExit("Discord rejected the token. Reset it on the Bot tab and paste the new one into .env.")
    except discord.PrivilegedIntentsRequired:
        raise SystemExit("Turn on Message Content Intent (Developer Portal > your app > Bot), then start again.")


if __name__ == "__main__":
    main()
