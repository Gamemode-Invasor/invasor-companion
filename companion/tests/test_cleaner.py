import struct
import tempfile
import unittest
from pathlib import Path

from companion import cleaner


def shortcuts_vdf(appid):
    # {"shortcuts": {"0": {"appid": appid}}}
    return (b"\x00shortcuts\x00\x000\x00\x02appid\x00" + struct.pack("<i", appid) + b"\x08\x08\x08")


class CleanerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.lib = self.root / "steamapps"
        self.grid = self.root / "userdata/1/config/grid"
        self.grid.mkdir(parents=True)
        for kind in ("compatdata", "shadercache"):
            (self.lib / kind).mkdir(parents=True)
        (self.lib / "appmanifest_10.acf").write_text('"AppState"\n{\n"appid"\t"10"\n}\n')
        (self.root / "userdata/1/config/shortcuts.vdf").write_bytes(shortcuts_vdf(-2))  # 4294967294
        for appid in ("10", "99", "4294967294", "0"):
            (self.lib / "compatdata" / appid).mkdir()
            (self.lib / "compatdata" / appid / "f").write_text("x" * 5)
        (self.lib / "shadercache/99").mkdir()

    def scan(self):
        return cleaner.scan(self.root, [self.lib])

    def test_only_orphans_are_listed(self):
        out = self.scan()
        self.assertEqual(sorted((p["kind"], p["appid"]) for p in out["prefixes"]),
                         [("compatdata", "99"), ("shadercache", "99")])
        self.assertEqual(next(p for p in out["prefixes"] if p["kind"] == "compatdata")["size"], 5)

    def test_names_are_remembered_for_orphans(self):
        names = {}
        save = names.update
        (self.lib / "appmanifest_99.acf").write_text('"AppState"\n{\n"appid"\t"99"\n"name"\t"Old Game"\n}\n')
        self.assertEqual(cleaner.scan(self.root, [self.lib], names, save)["prefixes"], [])
        (self.lib / "appmanifest_99.acf").unlink()  # uninstalled
        out = cleaner.scan(self.root, [self.lib], names, save, name_of=lambda a: "Fallback" if a == "5" else None)
        self.assertEqual({p["name"] for p in out["prefixes"]}, {"Old Game"})
        (self.lib / "compatdata/5").mkdir()
        out = cleaner.scan(self.root, [self.lib], names, save, name_of=lambda a: "Fallback" if a == "5" else None)
        self.assertEqual({p["appid"]: p["name"] for p in out["prefixes"] if p["kind"] == "compatdata"},
                         {"99": "Old Game", "5": "Fallback"})

    def test_grids_in_use_are_kept(self):
        for name in ("10_icon.png", "99p.jpg", "555_hero.png", "4294967294.png", "notes.txt"):
            (self.grid / name).write_text("x")
        # 99 has a prefix, 10 is installed, 4294967294 is a shortcut: only 555 is lost.
        self.assertEqual([g["appid"] for g in self.scan()["grids"]], ["555"])

    def test_delete_only_what_was_scanned(self):
        (self.grid / "555_hero.png").write_text("x")
        keep = self.lib / "compatdata/10"
        orphan = self.lib / "compatdata/99"
        grid = self.grid / "555_hero.png"
        out = cleaner.delete([str(keep), str(orphan), str(grid), "/etc/passwd"], self.root, [self.lib])
        self.assertEqual(sorted(out["deleted"]), sorted([str(orphan), str(grid)]))
        self.assertEqual(sorted(out["failed"]), sorted([str(keep), "/etc/passwd"]))
        self.assertTrue(keep.is_dir())
        self.assertFalse(orphan.exists())

    def test_symlinked_prefix_is_unlinked_not_followed(self):
        target = self.root / "elsewhere"
        target.mkdir()
        (target / "f").write_text("x")
        link = self.lib / "compatdata/77"
        link.symlink_to(target)
        cleaner.delete([str(link)], self.root, [self.lib])
        self.assertFalse(link.is_symlink())
        self.assertTrue((target / "f").is_file())


if __name__ == "__main__":
    unittest.main()
