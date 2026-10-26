import importlib.util
import logging
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]


def load_backend():
    name = "companion_backend_under_test"
    for n in [n for n in sys.modules if n == name or n.startswith(name + ".")]:
        del sys.modules[n]
    spec = importlib.util.spec_from_file_location(name, HERE / "backend.py", submodule_search_locations=[str(HERE)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


from invasor import vdf as core_vdf  # noqa: E402  (the core, found by tests/__init__.py)


class FakeCtx:
    log = logging.getLogger("test.companion")
    vdf = core_vdf
    language = "english"

    def __init__(self, root=None):
        self.root = Path(root or "/nonexistent-steam")
        self.steam = mock.Mock()
        self.steam.add_to.return_value = {"appid": 3000000000, "existed": False}
        self.data = self.Data()
        ctx = self

        class paths:
            @staticmethod
            def steam_root():
                return ctx.root

            @staticmethod
            def libraries():
                lib = ctx.root / "steamapps"
                return [lib] if lib.is_dir() else []

        self.paths = paths

    def steam_language(self):
        return {"spanish": "es", "latam": "es", "english": "en"}.get(self.language, "de")

    class Data:
        def __init__(self):
            self.stored = {}

        def load(self):
            return dict(self.stored)

        def update(self, **kw):
            self.stored.update(kw)

    class InvalidArgument(Exception):
        pass

    class Unavailable(Exception):
        pass

    class events:
        handlers = {}

        @classmethod
        def on(cls, name, callback):
            cls.handlers[name] = callback

    class toml:
        """ctx.toml.load as the core does it: ({}, None) when the file is missing, InvalidArgument if it isn't TOML."""

        @staticmethod
        def load(path):
            try:
                raw = Path(path).read_bytes()
            except FileNotFoundError:
                return {}, None
            try:
                return tomllib.loads(raw.decode()), 1
            except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
                raise FakeCtx.InvalidArgument(str(e)) from None

    class game:
        selected = None

        @staticmethod
        def info(appid):
            return {"appid": appid, "name": "Game " + appid}


class BackendTest(unittest.TestCase):
    def test_methods(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        self.assertEqual(set(backend.METHODS), {
            "build", "language", "compatdata_dir", "add_to_steam", "game_info", "profiles", "clean_scan",
            "clean_delete"})

    def test_language(self):
        backend = load_backend()
        ctx = FakeCtx()
        backend.setup(ctx)
        for steam, lang in (("spanish", "es"), ("latam", "es"), ("english", "en"), ("german", "en")):
            ctx.language = steam
            self.assertEqual(backend.language(), lang)

    def test_profiles(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with tempfile.TemporaryDirectory() as d:
            mako = Path(d) / "mako.toml"
            mako.write_text('version = 2\n[[profile]]\nname = "default"\n[[profile]]\nname = "The Witcher 3 — Remastered"\n'
                            '[[profile]]\nname = "default"\n[[profile]]\nmultiplier = 2\n')
            env = {"MAKO_CONFIG": str(mako), "XDG_CONFIG_HOME": d}  # no lsfg-vk/conf.toml there
            with mock.patch.dict("os.environ", env):
                self.assertEqual(backend.profiles(), {"mako": ["default", "The Witcher 3 — Remastered"], "lsfg": []})
                mako.write_text("not = = toml")
                self.assertEqual(backend.profiles()["mako"], [])  # broken: typed by hand
                lsfg = Path(d) / "lsfg-vk" / "conf.toml"
                lsfg.parent.mkdir()
                lsfg.write_text('[[profile]]\nname = "2x"\n')
                self.assertEqual(backend.profiles()["lsfg"], ["2x"])

    def test_build_uses_home_and_ignores_garbage(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        self.assertEqual(backend.build("nope")["command"], "")
        out = backend.build({"mako": {"on": True, "profile": "p"}})["command"]
        self.assertTrue(out.endswith("/.local/bin/mako-launch %command%"))

    def test_add_to_steam(self):
        backend = load_backend()
        ctx = FakeCtx()
        backend.setup(ctx)
        out = backend.add_to_steam("/games/My Game & Co.exe")
        self.assertEqual(out, {"appid": 3000000000, "existed": False})
        ctx.steam.add_to.assert_called_once_with("My Game & Co", "/games/My Game & Co.exe")
        with self.assertRaises(FakeCtx.InvalidArgument):
            backend.add_to_steam(None)

    def test_compatdata_dir(self):
        backend = load_backend()
        with tempfile.TemporaryDirectory() as d:
            ctx = FakeCtx(d)
            backend.setup(ctx)
            self.assertIsNone(backend.compatdata_dir())
            (Path(d) / "steamapps/compatdata").mkdir(parents=True)
            self.assertEqual(backend.compatdata_dir(), str(Path(d) / "steamapps/compatdata"))

    def test_names_move_from_the_old_file_to_ctx_data(self):
        backend = load_backend()
        ctx = FakeCtx()
        backend.setup(ctx)
        with tempfile.TemporaryDirectory() as d:
            backend.OLD_NAMES_FILE = Path(d) / "companion/names.json"
            self.assertEqual(backend._load_names(), {})
            backend.OLD_NAMES_FILE.parent.mkdir()
            backend.OLD_NAMES_FILE.write_text('{"10": "Old", "11": 5}')
            self.assertEqual(backend._load_names(), {"10": "Old"})
            backend._save_names({"10": "Old", "12": "New"})
            self.assertEqual(ctx.data.stored, {"names": {"10": "Old", "12": "New"}})
            self.assertFalse(backend.OLD_NAMES_FILE.parent.exists())
            self.assertEqual(backend._load_names(), {"10": "Old", "12": "New"})

    def test_names_are_refreshed_on_steam_start(self):
        backend = load_backend()
        ctx = FakeCtx()
        backend.setup(ctx)
        self.assertIs(ctx.events.handlers["steam_start"], backend.refresh_names)
        with mock.patch.object(backend.cleaner, "remember_names", return_value=(set(), {"1": "A"})) as remember:
            backend.refresh_names({})
            self.assertIs(remember.call_args.args[3], backend._save_names)
        with mock.patch.object(backend.cleaner, "remember_names", side_effect=OSError("x")):
            backend.refresh_names()  # a failure is logged, not raised

    def test_clean_delete_rejects_bad_arguments(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        for bad in ("/tmp/x", None, [1], {"a": "b"}):
            with self.assertRaises(FakeCtx.InvalidArgument):
                backend.clean_delete(bad)

    def test_game_info_defaults_to_the_selected_game(self):
        backend = load_backend()
        ctx = FakeCtx()
        ctx.game.selected = {"appid": "42", "name": "G", "shortcut": False}
        backend.setup(ctx)
        with mock.patch.object(backend.gameinfo, "game_info", return_value={"ok": 1}) as info:
            self.assertEqual(backend.game_info(), {"ok": 1})
            self.assertEqual(info.call_args.args, ("42", ctx.root, []))
            self.assertEqual(info.call_args.kwargs["name"], "Game 42")
            self.assertIs(info.call_args.kwargs["launch_options"], ctx.steam.launch_options.return_value)
            ctx.steam.launch_options.side_effect = FakeCtx.Unavailable("no Steam")
            backend.game_info("42")
            self.assertIsNone(info.call_args.kwargs["launch_options"])  # the files then
            ctx.steam.launch_options.side_effect = None
            backend.game_info("7")
            self.assertEqual(info.call_args.args[0], "7")
        for bad in ("../../etc", "12a", "-1", "1/2", "\u0661"):
            with self.assertRaises(FakeCtx.InvalidArgument):
                backend.game_info(bad)
        ctx.game.selected = None
        with self.assertRaises(FakeCtx.InvalidArgument):
            backend.game_info()


if __name__ == "__main__":
    unittest.main()
