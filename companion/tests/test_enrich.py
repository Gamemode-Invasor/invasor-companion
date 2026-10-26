import importlib
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def load(name):
    pkg = "companion_under_test"
    if pkg not in sys.modules:
        mod = types.ModuleType(pkg)
        mod.__path__ = [str(HERE)]
        sys.modules[pkg] = mod
    return importlib.import_module(f"{pkg}.{name}")


enrich = load("enrich")


class EnrichTest(unittest.TestCase):
    def test_steamdb_score_as_puntueitor(self):
        # Puntueitor's _bayesian_score gives 95.37, 75.71 and 50.0 (to two decimals).
        self.assertEqual(enrich.steamdb_score(802993, 32356), 95.4)
        self.assertEqual(enrich.steamdb_score(10, 0), 75.7)
        self.assertEqual(enrich.steamdb_score(1, 1), 50.0)
        self.assertIsNone(enrich.steamdb_score(0, 0))

    def test_rating(self):
        self.assertEqual(enrich.rating(96, 835349), "overwhelmingly_positive")
        self.assertEqual(enrich.rating(96, 100), "very_positive")
        self.assertEqual(enrich.rating(85, 10), "positive")
        self.assertEqual(enrich.rating(75, 10), "mostly_positive")
        self.assertEqual(enrich.rating(50, 10), "mixed")
        self.assertEqual(enrich.rating(30, 10), "mostly_negative")
        self.assertEqual(enrich.rating(10, 10), "negative")
        self.assertEqual(enrich.rating(10, 100), "very_negative")
        self.assertEqual(enrich.rating(10, 1000), "overwhelmingly_negative")

    def test_steam(self):
        self.assertEqual(enrich.steam({"appid": 292030, "positive": 802993, "negative": 32356}),
                         {"rating": "overwhelmingly_positive", "percent": 96, "total": 835349, "steamdb": 95.4})
        for bad in (None, [], {}, {"positive": 0, "negative": 0}, {"positive": "9", "negative": True}):
            self.assertIsNone(enrich.steam(bad))

    def test_metacritic(self):
        ok = {"292030": {"success": True, "data": {"metacritic": {"score": 93, "url": "https://www.metacritic.com/x"}}}}
        self.assertEqual(enrich.metacritic(ok, 292030), {"score": 93, "url": "https://www.metacritic.com/x"})
        self.assertIsNone(enrich.metacritic({"292030": {"success": True, "data": []}}, "292030"))
        self.assertIsNone(enrich.metacritic({"292030": {"success": False}}, "292030"))
        self.assertIsNone(enrich.metacritic(ok, "1"))
        bad_url = {"5": {"success": True, "data": {"metacritic": {"score": 70, "url": "javascript:x"}}}}
        self.assertEqual(enrich.metacritic(bad_url, 5), {"score": 70, "url": None})

    def test_protondb(self):
        self.assertEqual(enrich.protondb({"tier": "platinum", "total": 1876}), {"tier": "platinum", "total": 1876})
        self.assertIsNone(enrich.protondb({"tier": "<b>"}))
        self.assertIsNone(enrich.protondb(None))

    def test_best_match(self):
        search = {"items": [{"type": "sub", "id": 1}, {"type": "app", "id": 292030, "name": "The Witcher 3"}]}
        self.assertEqual(enrich.best_match(search), ("292030", "The Witcher 3"))
        for bad in (None, {"items": []}, {"items": "x"}, {"items": [{"type": "app", "id": "7"}]}):
            self.assertIsNone(enrich.best_match(bad))

    def test_urls(self):
        self.assertEqual(enrich.protondb_url("292030", "W3", False), "https://www.protondb.com/app/292030")
        self.assertEqual(enrich.protondb_url("3000000000", "A & B #2", True),
                         "https://www.protondb.com/search?q=A%20%26%20B%20%232")
        self.assertEqual(enrich.hltb_url("A & B #2"), "https://howlongtobeat.com/?q=A%20%26%20B%20%232")
        self.assertTrue(enrich.storesearch_url("a/b?c").startswith(
            "https://store.steampowered.com/api/storesearch/?term=a%2Fb%3Fc&"))


if __name__ == "__main__":
    unittest.main()
