import unittest

from krillion.parsing import Share, check_score, parse_share, unknown_tiles

# The four posts from the Discord screenshot, as pasted.
FIRE_ALARM = "Krillion #90 🦐\n225\n\n🏮🫧🫧⬛🐟🐟🦑"
DUCK_DADDY = "Krillion #90 🦐\n180\n\n🦑🐟🫧🫧🐟🐟🫧\nY'all over here with over 200pts is nuts"
ULTRAWIDE = "Krillion #90 🦐\n225\n\n🐟🫧🫧🐟🦑🏮⬛"
ASHCAT = "Krillion #90 🦐\n320\n\n🐟🏮🐟🏮⬛🦑🐟"


class ParseTests(unittest.TestCase):
    def test_screenshot_posts(self):
        self.assertEqual(parse_share(FIRE_ALARM), Share(90, 225, "🏮🫧🫧⬛🐟🐟🦑"))
        self.assertEqual(parse_share(DUCK_DADDY), Share(90, 180, "🦑🐟🫧🫧🐟🐟🫧"))
        self.assertEqual(parse_share(ULTRAWIDE).score, 225)
        self.assertEqual(parse_share(ASHCAT).score, 320)

    def test_loose_formatting(self):
        self.assertEqual(parse_share("krillion # 91\r\n 300 \r\n"), Share(91, 300, ""))
        self.assertEqual(parse_share("gg all\nKrillion #92 🦐\n150\n\n⬛⬛🫧"), Share(92, 150, "⬛⬛🫧"))

    def test_text_after_score_is_not_a_tile_row(self):
        self.assertEqual(parse_share("Krillion #90 🦐\n225\nnot bad").tiles, "")

    def test_ignores_things_that_only_look_like_scores(self):
        for text in [
            "> Krillion #90 🦐\n> 225",  # quoting someone else's score
            "did anyone finish Krillion #90? 225 is my best",
            "Krillion #90 was rough\n150",
            "Krillion #90 🦐\nso hard today",
            "Krillion #90 🦐",
            "Krillion 90\n225",
            "",
        ]:
            with self.subTest(text=text):
                self.assertIsNone(parse_share(text))


class CheckTests(unittest.TestCase):
    def test_screenshot_posts_add_up(self):
        for text in (FIRE_ALARM, DUCK_DADDY, ULTRAWIDE, ASHCAT):
            with self.subTest(text=text):
                self.assertEqual(check_score(parse_share(text)), "ok")

    def test_wrong_score_is_a_mismatch(self):
        self.assertEqual(check_score(parse_share("Krillion #90 🦐\n595\n\n🏮🫧🫧⬛🐟🐟🦑")), "mismatch")

    def test_variation_selectors_are_ignored(self):
        self.assertEqual(check_score(Share(90, 85, "🏮️⬛️ ⬛")), "ok")

    def test_no_tiles_or_unknown_tile_is_unchecked(self):
        self.assertEqual(check_score(Share(90, 225, "")), "unchecked")
        share = Share(90, 225, "🏮🐋🫧")
        self.assertEqual(check_score(share), "unchecked")
        self.assertEqual(unknown_tiles(share), ["🐋"])


if __name__ == "__main__":
    unittest.main()
