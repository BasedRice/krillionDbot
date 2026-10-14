import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from krillion import boards

ET = ZoneInfo("America/New_York")


def row(user_id, name, score, puzzle=90, tiles="", check="ok"):
    return {"user_id": user_id, "user_name": name, "score": score, "puzzle": puzzle,
            "tiles": tiles, "check_status": check}


SCREENSHOT = [row(4, "AshCat", 320), row(1, "Fire Alarm", 225), row(3, "Ultrawide Villain", 225),
              row(2, "Duck Daddy", 180)]


class RankTests(unittest.TestCase):
    def test_ties_share_a_rank(self):
        self.assertEqual(boards.rank([320, 225, 225, 180]), [1, 2, 2, 4])
        self.assertEqual(boards.rank([]), [])

    def test_board_lines(self):
        lines = boards.board_lines(SCREENSHOT)
        self.assertTrue(lines[0].startswith("🥇 **AshCat** — 320"))
        self.assertTrue(lines[1].startswith("🥈") and lines[2].startswith("🥈"))
        self.assertTrue(lines[3].startswith("`4.` **Duck Daddy**"))

    def test_board_flags_and_escapes(self):
        line = boards.board_lines([row(1, "x_cool_x", 595, check="mismatch")])[0]
        self.assertIn("x\\_cool\\_x", line)
        self.assertIn("⚠️", line)

    def test_board_is_capped(self):
        lines = boards.board_lines([row(i, f"p{i}", 100 - i) for i in range(30)], limit=25)
        self.assertEqual(len(lines), 26)
        self.assertEqual(lines[-1], "…and 5 more")

    def test_final_results_name_winner_or_tie(self):
        embed = boards.leaderboard_embed(90, SCREENSHOT, row(4, "AshCat", 320), final=True)
        self.assertIn("**AshCat** wins with **320**", embed.description)
        self.assertIn("4 players · avg 238", embed.footer.text)
        tied = [row(1, "A", 300), row(2, "B", 300)]
        self.assertIn("**A and B** tie for the win", boards.leaderboard_embed(90, tied, None, final=True).description)

    def test_alltime_mentions_matched_record(self):
        embed = boards.alltime_embed([row(4, "AshCat", 320), row(1, "Fire Alarm", 320, puzzle=91)])
        self.assertIn("Record: **320** by **AshCat** on #90 (matched by Fire Alarm)", embed.description)


class StatsTests(unittest.TestCase):
    def test_stats_fields(self):
        rows = [row(1, "AshCat", 300, puzzle=89), row(1, "AshCat", 320, puzzle=90)]
        fields = {f.name: f.value for f in boards.stats_embed("AshCat", rows, wins=1, latest=90).fields}
        self.assertEqual(fields["Runs"], "2")
        self.assertEqual(fields["Best"], "320 (#90)")
        self.assertEqual(fields["Streak"], "2 days")


class StreakTests(unittest.TestCase):
    def test_streaks(self):
        self.assertEqual(boards.streaks([85, 86, 87, 89, 90], latest=90), (2, 3))
        self.assertEqual(boards.streaks([88, 89], latest=90), (2, 2))  # today's not over yet
        self.assertEqual(boards.streaks([85, 86], latest=90), (0, 2))


class AnnouncementTests(unittest.TestCase):
    def say(self, score, *, user_id=9, puzzle=90, record=None, day_best=None, latest=90):
        return boards.announcement(user_id=user_id, display_name="Duck Daddy", puzzle=puzzle, score=score,
                                   record=record, day_best=day_best, latest=latest)

    def test_new_record(self):
        text = self.say(400, record=row(4, "AshCat", 320, puzzle=85))
        self.assertIn("NEW ALL-TIME RECORD", text)
        self.assertIn("beating AshCat's 320 (#85)", text)
        self.assertIn("beating their own 320", self.say(400, user_id=4, record=row(4, "AshCat", 320)))

    def test_matched_record(self):
        self.assertIn("matched the all-time record", self.say(320, record=row(4, "AshCat", 320)))

    def test_takes_the_lead(self):
        text = self.say(250, record=row(4, "AshCat", 320), day_best=row(1, "Fire Alarm", 225))
        self.assertIn("takes the lead on Krillion #90", text)

    def test_quiet_cases(self):
        record = row(4, "AshCat", 320)
        self.assertIsNone(self.say(200, record=record, day_best=row(1, "Fire Alarm", 225)))
        self.assertIsNone(self.say(250, record=record))  # first score of the day
        self.assertIsNone(self.say(250, puzzle=88, record=record, day_best=row(1, "x", 100)))  # old puzzle
        self.assertIsNone(self.say(250))  # very first score ever


class ResultsDayTests(unittest.TestCase):
    def test_picks_the_puzzle_most_played_that_day(self):
        rows = [
            {"puzzle": 90, "posted_at": "2026-10-12T15:00:00+00:00"},
            {"puzzle": 90, "posted_at": "2026-10-13T03:30:00+00:00"},  # 11:30 PM ET on the 12th
            {"puzzle": 91, "posted_at": "2026-10-13T03:45:00+00:00"},  # someone a timezone ahead
            {"puzzle": 91, "posted_at": "2026-10-13T05:00:00+00:00"},  # 1 AM ET on the 13th
        ]
        self.assertEqual(boards.puzzle_for_day(rows, dt.date(2026, 10, 12), ET), 90)
        self.assertEqual(boards.puzzle_for_day(rows, dt.date(2026, 10, 13), ET), 91)
        self.assertIsNone(boards.puzzle_for_day(rows, dt.date(2026, 10, 10), ET))


if __name__ == "__main__":
    unittest.main()
