import datetime as dt
import itertools
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

import bot
from krillion.storage import Store

GUILD = 1
CHANNEL = 10
NOON_UTC = dt.datetime(2026, 10, 13, 16, 0, tzinfo=dt.timezone.utc)
_ids = itertools.count(1000)


def message(content, user_id, name, *, when=NOON_UTC, is_bot=False):
    return SimpleNamespace(
        id=next(_ids), content=content, created_at=when, jump_url="https://discord.com/channels/x",
        author=SimpleNamespace(id=user_id, display_name=name, bot=is_bot),
        guild=SimpleNamespace(id=GUILD), channel=SimpleNamespace(id=CHANNEL),
        add_reaction=AsyncMock(), reply=AsyncMock(),
    )


def share(puzzle, score, tiles):
    return f"Krillion #{puzzle} 🦐\n{score}\n\n{tiles}"


def reactions(msg):
    return [c.args[0] for c in msg.add_reaction.await_args_list]


def reply_text(msg):
    return msg.reply.await_args.args[0] if msg.reply.await_args else None


def fake_channel(messages=()):
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = CHANNEL
    channel.guild = SimpleNamespace(id=GUILD)
    channel.send = AsyncMock()

    async def history(**kwargs):
        for m in messages:
            yield m

    channel.history = history
    return channel


class CommandTreeTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_are_registered(self):
        client = bot.KrillionBot(Store(":memory:"))
        commands = {c.name: c for c in client.tree.get_commands()}
        self.assertEqual(set(commands), {"leaderboard", "alltime", "stats", "krillion"})
        self.assertEqual({c.name for c in commands["krillion"].commands}, {"setchannel", "remove", "rescan"})
        self.assertTrue(commands["krillion"].default_permissions.manage_guild)


class TakeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = bot.KrillionBot(Store(":memory:"))
        await self.client.take(message(share(89, 320, "🐟🏮🐟🏮⬛🦑🐟"), 4, "AshCat"), live=False, react=False)

    async def take(self, msg):
        return await self.client.take(msg, live=True, react=True)

    async def test_live_day(self):
        first = message(share(90, 225, "🏮🫧🫧⬛🐟🐟🦑"), 1, "Fire Alarm")
        self.assertEqual(await self.take(first), ("new", "ok"))
        self.assertEqual(reactions(first), ["✅"])
        self.assertIsNone(reply_text(first))  # first score of the day: nothing to announce

        lower = message(share(90, 180, "🦑🐟🫧🫧🐟🐟🫧"), 2, "Duck Daddy")
        await self.take(lower)
        self.assertIsNone(reply_text(lower))

        lead = message(share(90, 300, "🏮🏮🦑🦑🫧⬛⬛"), 3, "Ultrawide Villain")
        await self.take(lead)
        self.assertIn("takes the lead on Krillion #90 with **300**", reply_text(lead))

        record = message(share(90, 355, "🏮🏮🏮🦑🐟🫧⬛"), 5, "Newbie")
        await self.take(record)
        self.assertIn("NEW ALL-TIME RECORD", reply_text(record))
        self.assertIn("beating AshCat's 320 (#89)", reply_text(record))

        again = message(share(90, 500, "🏮🏮🏮🦑🐟🫧⬛"), 1, "Fire Alarm")
        self.assertEqual(await self.take(again), ("duplicate", "mismatch"))
        self.assertEqual(reactions(again), ["🔁"])
        self.assertEqual(self.client.store.puzzle_best(GUILD, 90)["score"], 355)

    async def test_fake_score_is_flagged_and_not_announced(self):
        fake = message(share(90, 595, "🏮🫧🫧⬛🐟🐟🦑"), 6, "Troll")
        self.assertEqual(await self.take(fake), ("new", "mismatch"))
        self.assertEqual(reactions(fake), ["✅", "⚠️"])
        self.assertIsNone(reply_text(fake))

    async def test_ignores_bots_chatter_and_removed_scores(self):
        self.assertIsNone(await self.take(message(share(90, 225, ""), 7, "Some Bot", is_bot=True)))
        self.assertIsNone(await self.take(message("Krillion #90 was hard", 1, "Fire Alarm")))
        posted = message(share(90, 225, ""), 8, "Fire Alarm")
        await self.take(posted)
        self.client.store.remove_score(GUILD, 90, 8)
        self.assertIsNone(await self.take(posted))

    async def test_history_import_counts_and_stays_quiet(self):
        history = [
            message(share(90, 225, "🏮🫧🫧⬛🐟🐟🦑"), 1, "Fire Alarm"),
            message("nice", 2, "Duck Daddy"),
            message(share(90, 999, "🦑🐟🫧🫧🐟🐟🫧"), 2, "Duck Daddy"),
            message(share(90, 100, ""), 1, "Fire Alarm"),
        ]
        self.client.store.set_channel(GUILD, CHANNEL)
        counts = await self.client.import_history(fake_channel(history), after=None, react=False)
        self.assertEqual((counts["new"], counts["duplicate"], counts["mismatch"]), (2, 1, 1))
        self.assertEqual(bot.import_summary(counts),
                         "Found **2** scores in its history (1 flagged ⚠️ because the emoji row didn't add up"
                         " to the score).")
        self.assertTrue(all(not m.add_reaction.await_count and not m.reply.await_count for m in history))
        self.assertEqual(self.client.store.watches()[0]["last_message_id"], history[-1].id)


class ResultsTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_each_puzzle_once(self):
        client = bot.KrillionBot(Store(":memory:"))
        evening = dt.datetime(2026, 10, 12, 23, 0, tzinfo=dt.timezone.utc)  # 7 PM ET on the 12th
        for user, score in [(1, 225), (2, 180), (3, 320)]:
            await client.take(message(share(90, score, ""), user, f"p{user}", when=evening), live=False, react=False)
        channel = fake_channel()
        client.get_channel = lambda _id: channel

        self.assertEqual(await client.post_results(GUILD, CHANNEL, dt.date(2026, 10, 12)), 90)
        embed = channel.send.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "🦐 Krillion #90 — Final Results")
        self.assertIn("**p3** wins with **320**", embed.description)
        self.assertIsNone(await client.post_results(GUILD, CHANNEL, dt.date(2026, 10, 12)))
        self.assertEqual(channel.send.await_count, 1)


if __name__ == "__main__":
    unittest.main()
