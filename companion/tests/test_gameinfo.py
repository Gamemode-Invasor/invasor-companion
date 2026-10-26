import importlib
import struct
import sys
import tempfile
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


from invasor import vdf  # noqa: E402  (the core, found by tests/__init__.py)

gameinfo = load("gameinfo")
gameinfo.vdf = vdf

CONFIG = '"InstallConfigStore" { "Software" { "Valve" { "Steam" { "CompatToolMapping" { "0" { "name" "proton_experimental" } "100" { "name" "GE-Proton" } } } } } }'
MANIFEST = """"AppState"
{
	"appid"		"100"
	"name"		"The Game"
	"StateFlags"		"4"
	"installdir"		"The Game Dir"
	"LastUpdated"		"1764531875"
	"SizeOnDisk"		"7076631877"
	"buildid"		"11"
	"TargetBuildID"		"12"
	"AutoUpdateBehavior"		"1"
	"BytesToDownload"		"500"
	"BytesDownloaded"		"200"
}
"""
LOCAL = ('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { "100" { "LastPlayed" "1770673563" '
         '"Playtime" "150" "LaunchOptions" "STEAM_COMPAT_DATA_PATH=\\"/x y/compat\\" %command%" } } } } } }')


def shortcut_vdf(appid, **fields):
    def s(k, v):
        return b"\x01" + k.encode() + b"\x00" + v.encode() + b"\x00"

    body = b"\x02appid\x00" + struct.pack("<i", appid - (1 << 32) if appid > 0x7FFFFFFF else appid)
    body += b"".join(s(k, v) for k, v in fields.items()) + b"\x00tags\x00\x010\x00one\x00\x08\x08"
    return b"\x00shortcuts\x00\x000\x00" + body + b"\x08\x08"


class Tree:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "config").mkdir(parents=True)
        (self.root / "config/config.vdf").write_text(CONFIG)
        (self.root / "steamapps/compatdata/100").mkdir(parents=True)
        (self.root / "steamapps/appmanifest_100.acf").write_text(MANIFEST)
        cfg = self.root / "userdata/1/config"
        cfg.mkdir(parents=True)
        (cfg / "localconfig.vdf").write_text(LOCAL)
        self.cfg = cfg
        self.libs = [self.root / "steamapps"]

    def info(self, appid, **kw):
        return gameinfo.game_info(appid, self.root, self.libs, **kw)


def rows(info):
    return {g["id"]: {r["key"]: r for r in g["rows"]} for g in info["groups"]}


class SteamGameTest(unittest.TestCase):
    def test_steam_game(self):
        with tempfile.TemporaryDirectory() as d:
            t = Tree(d)
            info = t.info(100)
            self.assertEqual((info["name"], info["kind"]), ("The Game", "steam"))
            r = rows(info)
            self.assertEqual(r["general"]["appid"]["value"], "100")
            self.assertEqual(r["install"]["size"], {"key": "size", "value": 7076631877, "type": "bytes"})
            self.assertEqual(r["install"]["folder"]["value"], str(t.root / "steamapps/common/The Game Dir"))
            self.assertEqual(r["install"]["library"]["value"], str(t.root))
            self.assertEqual((r["install"]["build"]["value"], r["install"]["target_build"]["value"]), ("11", "12"))
            self.assertEqual(r["install"]["pending"]["value"], 300)
            self.assertEqual(r["install"]["autoupdate"]["type"], "autoupdate")
            self.assertEqual((r["play"]["last_played"]["value"], r["play"]["playtime"]["value"]), (1770673563, 150))
            self.assertEqual(r["compat"]["tool"]["value"], "GE-Proton")
            self.assertEqual(r["compat"]["prefix"]["value"], str(t.root / "steamapps/compatdata/100"))
            self.assertEqual(r["compat"]["prefix_override"]["value"], "/x y/compat")
            # Steam's own answer wins over localconfig.vdf, which lags behind it; "" is "none".
            r = rows(t.info(100, launch_options="-novid %command%"))
            self.assertEqual(r["play"]["launch_options"]["value"], "-novid %command%")
            self.assertNotIn("prefix_override", r["compat"])
            self.assertNotIn("launch_options", rows(t.info(100, launch_options=""))["play"])
            self.assertEqual(r["links"]["store"]["value"], "https://store.steampowered.com/app/100")
            self.assertNotIn("shortcut", r)

    def test_empty_values_and_groups_are_left_out(self):
        with tempfile.TemporaryDirectory() as d:
            t = Tree(d)
            (t.root / "steamapps/appmanifest_100.acf").unlink()
            (t.cfg / "localconfig.vdf").write_text("")
            info = t.info(100, name="From Steam")
            r = rows(info)
            self.assertEqual(set(r), {"general", "compat", "links"})
            self.assertEqual(info["name"], "From Steam")
            self.assertNotIn("install", r)
            self.assertEqual(rows(t.info(999))["compat"]["tool"]["value"], "proton_experimental")
            self.assertNotIn("prefix", rows(t.info(999))["compat"])


class ShortcutTest(unittest.TestCase):
    def test_shortcut(self):
        with tempfile.TemporaryDirectory() as d:
            t = Tree(d)
            appid = 3898997642
            (t.cfg / "shortcuts.vdf").write_bytes(shortcut_vdf(
                appid, AppName="Witcher", Exe='"/games/w3.exe"', StartDir='"/games"', LaunchOptions="-x %command%",
                icon="/i.png"))
            info = t.info(appid)
            self.assertEqual((info["name"], info["kind"]), ("Witcher", "shortcut"))
            r = rows(info)
            self.assertNotIn("gameid", r["general"])
            self.assertEqual(r["shortcut"]["exe"]["value"], "/games/w3.exe")
            self.assertEqual(r["shortcut"]["start_dir"]["value"], "/games")
            self.assertEqual(r["shortcut"]["tags"]["value"], "one")
            self.assertEqual(r["play"]["launch_options"]["value"], "-x %command%")
            self.assertNotIn("links", r)
            self.assertNotIn("install", r)
            # The Steam side can say it's a shortcut even without reading the file.
            self.assertEqual(t.info(appid, shortcut=True)["kind"], "shortcut")


if __name__ == "__main__":
    unittest.main()
