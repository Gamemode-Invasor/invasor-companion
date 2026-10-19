import importlib
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


command = load("command")
steam = load("steam")


def build(**kw):
    return command.build(kw, home="/home/u")


class BuildTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(build(), {"command": "", "warnings": []})
        self.assertEqual(build(mako={"on": False, "profile": "x"})["command"], "")

    def test_flags_in_order(self):
        out = build(wow64=True, wined3d=True, steamDeck=True)["command"]
        self.assertEqual(out, "PROTON_USE_WINED3D=1 PROTON_USE_WOW64=1 SteamDeck=0 %command%")

    def test_mako_adds_wrapper(self):
        out = build(mako={"on": True, "profile": "default"})["command"]
        self.assertEqual(out, 'MAKO_PROFILE="default" /home/u/.local/bin/mako-launch %command%')

    def test_empty_profile_warns(self):
        out = build(mako={"on": True, "profile": "  "})
        self.assertEqual(out["command"], "")
        self.assertEqual([w["code"] for w in out["warnings"]], ["empty_mako"])
        out = build(lsfg={"on": True, "profile": ""})
        self.assertEqual([w["code"] for w in out["warnings"]], ["empty_lsfg"])

    def test_mako_excludes_lsfg(self):
        out = build(mako={"on": True, "profile": "m"}, lsfg={"on": True, "profile": "l"})
        self.assertNotIn("LSFGVK", out["command"])
        self.assertIn("MAKO_PROFILE", out["command"])
        self.assertEqual([w["code"] for w in out["warnings"]], ["mako_lsfg"])

    def test_lsfg_and_fsr4(self):
        out = build(lsfg={"on": True, "profile": "decky-lsfg-vk"}, fsr4={"on": True}, fsr4Indicator=True)
        self.assertEqual(
            out["command"],
            'LSFGVK_PROFILE="decky-lsfg-vk" ENABLE_GAMESCOPE_WSI=0 FSR4_UPGRADE=1 PROTON_FSR4_UPGRADE=1 '
            "PROTON_FSR4_INDICATOR=1 %command%",
        )

    def test_fsr4_indicator_needs_fsr4(self):
        self.assertEqual(build(fsr4Indicator=True)["command"], "")
        out = build(fsr4={"on": True}, fsr4Indicator=True)["command"]
        self.assertIn("PROTON_FSR4_INDICATOR=1", out)

    def test_helixsr(self):
        self.assertEqual(build(helixsr={"on": False})["command"], "")
        self.assertEqual(
            build(helixsr={"on": True})["command"],
            "PROTON_USE_OPTISCALER=1 PROTON_OPTISCALER_CONFIG='Upscalers.Dx12Upscaler=fsr31;"
            "Libraries.FfxDx12Path=C:\\HelixSR\\helixsr.dll;"
            "Libraries.FfxDx12SRPath=C:\\HelixSR\\helixsr_upscaler.dll' %command%",
        )

    def test_helixsr_excludes_fsr4(self):
        out = build(helixsr={"on": True}, fsr4={"on": True}, fsr4Indicator=True)
        self.assertNotIn("FSR4", out["command"])
        self.assertIn("PROTON_USE_OPTISCALER=1", out["command"])
        self.assertEqual([w["code"] for w in out["warnings"]], ["helixsr_fsr4"])

    def test_helixsr_variables_are_reserved(self):
        out = build(custom=[{"name": "PROTON_USE_OPTISCALER", "value": "1"}])
        self.assertEqual([w["code"] for w in out["warnings"]], ["custom_reserved"])

    def test_fps_limit_is_sanitized(self):
        for value, want in (("abc", 30), (None, 30), (-5, 0), (999, 240), ("60", 60), (59.9, 59), (float("inf"), 30)):
            out = build(fpsLimit={"on": True, "value": value})["command"]
            self.assertIn(f"fps_limit={want},", out, value)

    def test_mangohud_variants(self):
        both = build(fpsLimit={"on": True, "value": 60}, showInfo=True)["command"]
        self.assertEqual(both, 'MANGOHUD_CONFIG="fps_limit=60,legacy_layout=0,gpu_name,fps" mangohud %command%')
        fps = build(fpsLimit={"on": True, "value": 30})["command"]
        self.assertEqual(fps, 'MANGOHUD_CONFIG="fps_limit=30,no_display" mangohud %command%')
        info = build(showInfo=True)["command"]
        self.assertEqual(info, 'MANGOHUD_CONFIG="legacy_layout=0,gpu_name,fps" mangohud %command%')

    def test_wrapper_order(self):
        out = build(mako={"on": True, "profile": "p"}, showInfo=True)["command"]
        self.assertTrue(out.endswith("mangohud /home/u/.local/bin/mako-launch %command%"))

    def test_quoting(self):
        self.assertEqual(command.quote('a"b$c`d\\e'), '"a\\"b\\$c\\`d\\\\e"')
        self.assertEqual(command.quote_if_needed("a=b,c"), "a=b,c")
        self.assertEqual(command.quote_if_needed("a b"), '"a b"')
        out = build(prefix={"on": True, "path": "/run/media/sd card/compatdata/1"}, dllOverrides={"on": True, "value": "dxgi.dll=n,b"})
        self.assertIn('STEAM_COMPAT_DATA_PATH="/run/media/sd card/compatdata/1" WINEDLLOVERRIDES="dxgi.dll=n,b"', out["command"])

    def test_custom_variables(self):
        out = build(custom=[
            {"name": "FOO", "value": "bar baz"},
            {"name": "1BAD", "value": "x"},
            {"name": "SteamDeck", "value": "1"},
            {"name": "FOO", "value": "again"},
            {"name": "", "value": "ignored"},
            {"name": "OK_2", "value": "v"},
        ])
        self.assertEqual(out["command"], 'FOO="bar baz" OK_2=v %command%')
        self.assertEqual(
            out["warnings"],
            [{"code": "custom_invalid", "name": "1BAD"}, {"code": "custom_reserved", "name": "SteamDeck"},
             {"code": "custom_duplicate", "name": "FOO"}],
        )

    def test_compatibility_warnings(self):
        out = build(lsfg={"on": True, "profile": "p"}, wined3d=True, showInfo=True)
        self.assertEqual([w["code"] for w in out["warnings"]], ["lsfg_wined3d", "lsfg_mangohud"])


class SteamTest(unittest.TestCase):
    def test_language(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "registry.vdf"
            for text, want in (('"language"\t\t"latam"', "es"), ('"language" "spanish"', "es"),
                               ('"language" "english"', "en"), ('"language" "german"', "en"), ("nothing", "en")):
                f.write_text(text)
                self.assertEqual(steam.language(f), want, text)
            self.assertEqual(steam.language(Path(d) / "missing"), "en")

    def test_start_dir_and_listdir(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "Steam"
            compat = root / "steamapps/compatdata"
            for n in ("123", "0", "abc", ".hidden"):
                (compat / n).mkdir(parents=True)
            (compat / "file.txt").write_text("x")
            self.assertEqual(steam.start_dir(root, ()), str(compat.resolve()))
            out = steam.listdir(compat, lambda a: "Game " + a if a == "123" else None)
            self.assertEqual(out["parent"], str(compat.parent.resolve()))
            self.assertIsNone(out["error"])
            self.assertEqual([x["label"] for x in out["dirs"]], ["0", "123 - Game 123", "abc"])
            self.assertEqual([x["name"] for x in out["dirs"]], ["0", "123", "abc"])

    def test_listdir_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "b_dir").mkdir()
            (root / ".hidden_dir").mkdir()
            (root / "z.exe").write_text("x")
            (root / "a.txt").write_text("x")
            (root / ".secret").write_text("x")
            out = steam.listdir(root, files=True)
            self.assertEqual([x["name"] for x in out["dirs"]], ["b_dir"])
            self.assertEqual([x["name"] for x in out["files"]], ["a.txt", "z.exe"])
            self.assertEqual(steam.listdir(root)["files"], [])
            self.assertEqual(len(steam.listdir(root, files=True, limit=2)["files"]), 1)

    def test_steam_url(self):
        self.assertEqual(steam.steam_url("/run/media/SteamOS/Games/_Launchers/Explorer++.exe"),
                         "steam://addnonsteamgame/%2Frun%2Fmedia%2FSteamOS%2FGames%2F_Launchers%2FExplorer%2B%2B.exe")
        self.assertEqual(steam.steam_url("/a b/ñ#&.exe"), "steam://addnonsteamgame/%2Fa%20b%2F%C3%B1%23%26.exe")

    def _proc(self, root, pid, comm, env):
        d = root / str(pid)
        d.mkdir()
        (d / "comm").write_text(comm + "\n")
        (d / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in env.items()) + b"\0")

    def test_session_env(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(steam.session_env(root), {})
            self._proc(root, 10, "bash", {"HOME": "/h"})
            self._proc(root, 11, "plasmashell", {"WAYLAND_DISPLAY": "wayland-1", "XDG_CURRENT_DESKTOP": "KDE", "X": "y"})
            self.assertEqual(steam.session_env(root), {"WAYLAND_DISPLAY": "wayland-1", "XDG_CURRENT_DESKTOP": "KDE"})
            self._proc(root, 12, "steam", {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"})
            self.assertEqual(steam.session_env(root), {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"})
            self.assertEqual(steam.session_env(root / "missing"), {})

    def test_steam_handler_registered(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "mimeapps.list"
            self.assertFalse(steam.steam_handler_registered(f))
            f.write_text("[Default Applications]\nx-scheme-handler/http=a.desktop\n")
            self.assertFalse(steam.steam_handler_registered(f))
            f.write_text("[Default Applications]\nx-scheme-handler/steam=steam.desktop;\n")
            self.assertTrue(steam.steam_handler_registered(f))

    def test_shortcut_added(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "userdata/1234/config"
            cfg.mkdir(parents=True)
            (cfg / "shortcuts.vdf").write_bytes(b"\x00shortcuts\x00Exe\x00\"/home/deck/Games/a b.exe\"\x00")
            self.assertTrue(steam.shortcut_added("/home/deck/Games/a b.exe", d))
            self.assertFalse(steam.shortcut_added("/home/deck/Games/other.exe", d))
            self.assertFalse(steam.shortcut_added("/x", Path(d) / "nothing"))
            # Only a whole value counts: not the start or the end of a longer path.
            self.assertFalse(steam.shortcut_added("/home/deck/Games/a b", d))
            self.assertFalse(steam.shortcut_added("/Games/a b.exe", d))
            self.assertFalse(steam.shortcut_added("/home/deck/Games/a b.ex", d))
            (cfg / "shortcuts.vdf").write_bytes(b"\x00shortcuts\x00Exe\x00/home/deck/Games/c.exe\x00")
            self.assertTrue(steam.shortcut_added("/home/deck/Games/c.exe", d))
            self.assertFalse(steam.shortcut_added("/home/deck/Games/c.exe.bak", d))

    def test_listdir_errors_and_root(self):
        out = steam.listdir("/nonexistent-companion-dir")
        self.assertTrue(out["error"])
        self.assertEqual(out["dirs"], [])
        self.assertIsNone(steam.listdir("/")["parent"])


if __name__ == "__main__":
    unittest.main()
