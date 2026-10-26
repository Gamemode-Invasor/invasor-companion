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


command = load("command")


def build(**kw):
    return command.build(kw, home="/home/u")


class BuildTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(build(), {"command": "", "warnings": []})
        self.assertEqual(build(mako={"on": False, "profile": "x"})["command"], "")

    def test_flags_in_order(self):
        out = build(wow64=True, wined3d=True, steamDeck=True)["command"]
        self.assertEqual(out, "PROTON_USE_WINED3D=1 PROTON_USE_WOW64=1 SteamDeck=0 %command%")

    def test_proton_log_goes_first(self):
        self.assertEqual(build(protonLog=True)["command"], "PROTON_LOG=1 %command%")
        out = build(protonLog=True, mako={"on": True, "profile": "default"}, wow64=True)["command"]
        self.assertTrue(out.startswith("PROTON_LOG=1 MAKO_PROFILE="))

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


if __name__ == "__main__":
    unittest.main()
