import importlib.util
import logging
import subprocess
import sys
import tempfile
import urllib.parse
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


class FakeCtx:
    log = logging.getLogger("test.companion")

    class InvalidArgument(Exception):
        pass

    class Unavailable(Exception):
        pass

    class events:
        handlers = {}

        @classmethod
        def on(cls, name, callback):
            cls.handlers[name] = callback

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
            "build", "language", "browse", "add_to_steam", "is_added", "game_info", "clean_scan", "clean_delete"})

    def test_build_uses_home_and_ignores_garbage(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        self.assertEqual(backend.build("nope")["command"], "")
        out = backend.build({"mako": {"on": True, "profile": "p"}})["command"]
        self.assertTrue(out.endswith("/.local/bin/mako-launch %command%"))

    def _ready(self, d):
        backend = load_backend()
        backend.setup(FakeCtx())
        exe = Path(d) / "My Game & Co.exe"
        exe.write_text("x")
        backend.MARKER = Path(d) / "marker"
        return backend, exe

    def _run(self, backend, path, added=False, **run_kw):
        run_kw = run_kw or {"return_value": mock.Mock(returncode=0, stderr="")}
        with mock.patch.object(backend.steam, "shortcut_added", return_value=added), \
                mock.patch.object(backend.steam, "session_env", return_value={"WAYLAND_DISPLAY": "wayland-0"}), \
                mock.patch.object(backend.subprocess, "run", **run_kw) as run:
            return run, backend.add_to_steam(path)

    def test_add_to_steam(self):
        with tempfile.TemporaryDirectory() as d:
            backend, exe = self._ready(d)
            backend.MARKER.write_text("old")
            run, out = self._run(backend, str(exe))
            self.assertEqual(out, {"ok": True, "already": False})
            self.assertEqual(backend.MARKER.read_text(), "")
            url = "steam://addnonsteamgame/" + urllib.parse.quote(str(exe), safe="")
            self.assertEqual(run.call_args.args[0], ["xdg-open", url])
            self.assertEqual(run.call_args.kwargs["env"]["WAYLAND_DISPLAY"], "wayland-0")
            self.assertIn("/usr/bin", run.call_args.kwargs["env"]["PATH"])
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_add_to_steam_already_there(self):
        with tempfile.TemporaryDirectory() as d:
            backend, exe = self._ready(d)
            run, out = self._run(backend, str(exe), added=True)
            self.assertEqual(out, {"ok": True, "already": True})
            run.assert_not_called()

    def test_add_to_steam_rejects_bad_paths(self):
        with tempfile.TemporaryDirectory() as d:
            backend, _ = self._ready(d)
            for bad in ("relative.exe", str(Path(d) / "missing.exe"), d, None):
                with mock.patch.object(backend.subprocess, "run") as run:
                    with self.assertRaises(FakeCtx.InvalidArgument):
                        backend.add_to_steam(bad)
                    with self.assertRaises(FakeCtx.InvalidArgument):
                        backend.is_added(bad)
                run.assert_not_called()

    def test_add_to_steam_failures(self):
        with tempfile.TemporaryDirectory() as d:
            backend, exe = self._ready(d)
            with self.assertRaises(FakeCtx.Unavailable):
                self._run(backend, str(exe), side_effect=FileNotFoundError("xdg-open"))
            bad = mock.Mock(returncode=3, stderr="no handler")
            with self.assertRaisesRegex(FakeCtx.Unavailable, "no handler"):
                self._run(backend, str(exe), return_value=bad)
            _, out = self._run(backend, str(exe), side_effect=subprocess.TimeoutExpired("xdg-open", 10))
            self.assertTrue(out["ok"])

    def test_is_added(self):
        with tempfile.TemporaryDirectory() as d:
            backend, exe = self._ready(d)
            with mock.patch.object(backend.steam, "shortcut_added", return_value=True):
                self.assertTrue(backend.is_added(str(exe)))

    def test_browse_home_and_files(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        out = backend.browse("/nonexistent-companion-dir", files=True, home=True)
        self.assertEqual(out["path"], str(Path.home().resolve()))

    def test_names_are_refreshed_on_steam_start(self):
        backend = load_backend()
        ctx = FakeCtx()
        backend.setup(ctx)
        self.assertIs(ctx.events.handlers["steam_start"], backend.refresh_names)
        with mock.patch.object(backend.cleaner, "remember_names", return_value=(set(), {"1": "A"})) as remember:
            backend.refresh_names({})
            self.assertIs(remember.call_args.kwargs["save_names"], backend._save_names)
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
            self.assertEqual(info.call_args.args, ("42",))
            self.assertEqual(info.call_args.kwargs, {"name": "Game 42", "shortcut": None})
            backend.game_info("7")
            self.assertEqual(info.call_args.args, ("7",))
        for bad in ("../../etc", "12a", "-1", "1/2", "\u0661"):
            with self.assertRaises(FakeCtx.InvalidArgument):
                backend.game_info(bad)
        ctx.game.selected = None
        with self.assertRaises(FakeCtx.InvalidArgument):
            backend.game_info()


if __name__ == "__main__":
    unittest.main()
