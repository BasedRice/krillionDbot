import unittest

from krillion.storage import Store

GUILD = 1


def save(store, *, puzzle, user, score, message_id, name=None, posted_at="2026-10-13T15:00:00+00:00"):
    return store.save_score(
        guild_id=GUILD, puzzle=puzzle, user_id=user, user_name=name or f"user{user}", score=score,
        tiles="", check_status="unchecked", channel_id=10, message_id=message_id, posted_at=posted_at,
    )


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def test_first_post_counts(self):
        self.assertEqual(save(self.store, puzzle=90, user=1, score=225, message_id=100), "new")
        self.assertEqual(save(self.store, puzzle=90, user=1, score=400, message_id=101), "duplicate")
        self.assertEqual(save(self.store, puzzle=90, user=1, score=225, message_id=100), "same")
        self.assertEqual([r["score"] for r in self.store.puzzle_scores(GUILD, 90)], [225])

    def test_older_post_found_later_wins(self):
        save(self.store, puzzle=90, user=1, score=300, message_id=105)
        self.assertEqual(save(self.store, puzzle=90, user=1, score=200, message_id=100), "replaced")
        self.assertEqual(self.store.puzzle_best(GUILD, 90)["score"], 200)

    def test_record_tie_goes_to_first_poster(self):
        save(self.store, puzzle=89, user=2, score=320, message_id=50)
        save(self.store, puzzle=90, user=1, score=320, message_id=100)
        save(self.store, puzzle=90, user=3, score=180, message_id=101)
        self.assertEqual(self.store.record(GUILD)["user_id"], 2)
        self.assertEqual([r["user_id"] for r in self.store.top_scores(GUILD)], [2, 1, 3])

    def test_removed_score_is_gone_and_remembered(self):
        save(self.store, puzzle=90, user=1, score=595, message_id=100)
        save(self.store, puzzle=90, user=2, score=225, message_id=101)
        self.assertEqual(self.store.remove_score(GUILD, 90, 1)["score"], 595)
        self.assertTrue(self.store.is_removed(100))
        self.assertEqual(self.store.record(GUILD)["score"], 225)
        self.assertIsNone(self.store.remove_score(GUILD, 90, 1))

    def test_daily_wins_only_count_finished_puzzles(self):
        save(self.store, puzzle=89, user=1, score=300, message_id=1)
        save(self.store, puzzle=89, user=2, score=300, message_id=2)
        save(self.store, puzzle=90, user=1, score=250, message_id=3)
        self.assertEqual(self.store.daily_wins(GUILD, 1), 1)  # #90 is still going
        self.assertEqual(self.store.daily_wins(GUILD, 2), 1)  # ties both win
        self.store.mark_results_posted(GUILD, 90)
        self.assertEqual(self.store.daily_wins(GUILD, 1), 2)

    def test_latest_puzzle(self):
        self.assertIsNone(self.store.latest_puzzle(GUILD))
        save(self.store, puzzle=90, user=1, score=1, message_id=1)
        save(self.store, puzzle=88, user=2, score=1, message_id=2)
        self.assertEqual(self.store.latest_puzzle(GUILD), 90)


class WatchTests(unittest.TestCase):
    def test_checkpoint_only_moves_forward_and_resets_on_new_channel(self):
        store = Store(":memory:")
        store.set_channel(GUILD, 10)
        store.advance_checkpoint(GUILD, 500)
        store.advance_checkpoint(GUILD, 400)
        self.assertEqual(store.watches()[0]["last_message_id"], 500)
        store.set_channel(GUILD, 11)
        self.assertEqual(store.watched_channel(GUILD), 11)
        self.assertIsNone(store.watches()[0]["last_message_id"])


if __name__ == "__main__":
    unittest.main()
