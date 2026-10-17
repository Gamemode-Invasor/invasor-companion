import importlib.util
import io
import json
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

    class Task:
        def __init__(self, label):
            self.label, self.calls, self.end = label, [], None

        def __enter__(self):
            return self

        def __exit__(self, kind, error, tb):
            if self.end is None:
                self.end = ("fail", str(error)) if error else ("done", "")

        def update(self, fraction, text):
            self.calls.append((fraction, text))

        def done(self, text=""):
            self.end = ("done", text)

    class events:
        handlers = {}

        @classmethod
        def on(cls, name, callback):
            cls.handlers[name] = callback

    tasks = []

    @classmethod
    def task(cls, label):
        cls.tasks.append(cls.Task(label))
        return cls.tasks[-1]

    class game:
        selected = None
        running = None

        @staticmethod
        def info(appid):
            return {"appid": appid, "name": "Game " + appid}


class BackendTest(unittest.TestCase):
    def test_methods(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        self.assertEqual(set(backend.METHODS), {
            "build", "language", "browse", "add_to_steam", "is_added", "game_info", "helixsr_status",
            "helixsr_check", "helixsr_download", "helixsr_copy", "clean_scan", "clean_delete"})

    def test_helixsr_status(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with tempfile.TemporaryDirectory() as d:
            backend.HELIXSR_DIR = Path(d) / "HelixSR"
            self.assertFalse(backend.helixsr_status()["found"])
            backend.HELIXSR_DIR.mkdir()
            (backend.HELIXSR_DIR / "helixsr.ini").write_text("x")
            self.assertFalse(backend.helixsr_status()["found"])
            (backend.HELIXSR_DIR / backend.HELIXSR_DLL).write_text("x")
            self.assertEqual(backend.helixsr_status(),
                             {"found": True, "dir": str(backend.HELIXSR_DIR), "version": None, "game": None})
            (backend.HELIXSR_DIR / ".version").write_text("v1.9.3\n")
            self.assertEqual(backend.helixsr_status()["version"], "v1.9.3")

    def test_helixsr_copy(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d) / "lib"
            backend.HELIXSR_DIR = Path(d) / "HelixSR"
            backend.HELIXSR_DIR.mkdir()
            for name in ("helixsr.dll", "helixsr.ini"):
                (backend.HELIXSR_DIR / name).write_text("new")
            (backend.HELIXSR_DIR / ".version").write_text("v1.9.3\n")
            dest = lib / "compatdata" / "42" / "pfx" / "drive_c" / "HelixSR"
            with mock.patch.object(backend.steam, "libraries", return_value=[lib]):
                self.assertIsNone(backend.helixsr_status()["game"])
                self.assertEqual(backend.helixsr_status("42")["game"], {"prefix": False, "copy": False, "version": None})
                with self.assertRaises(FakeCtx.Unavailable):
                    backend.helixsr_copy("42")
                with self.assertRaises(FakeCtx.InvalidArgument):
                    backend.helixsr_status("../x")
                dest.parent.mkdir(parents=True)
                self.assertEqual(backend.helixsr_status("42")["game"], {"prefix": True, "copy": True, "version": None})
                self.assertEqual(backend.helixsr_copy("42")["game"], {"prefix": True, "copy": False, "version": "v1.9.3"})
                for name in ("helixsr.dll", "helixsr.ini"):
                    self.assertEqual((dest / name).read_text(), "new")
                self.assertEqual((dest / ".version").read_text(), "v1.9.3\n")
                self.assertFalse(list(dest.glob("*.new")))
                (dest / ".version").write_text("v1.9.2\n")  # older: proposed again
                self.assertTrue(backend.helixsr_status("42")["game"]["copy"])
                backend.helixsr_copy("42")
                self.assertFalse(backend.helixsr_status("42")["game"]["copy"])
                (dest / ".version").write_text("v1.10.0\n")  # newer than ours: left alone
                self.assertFalse(backend.helixsr_status("42")["game"]["copy"])
                (dest / ".version").unlink()  # no version: proposed
                self.assertTrue(backend.helixsr_status("42")["game"]["copy"])
                backend.helixsr_copy("42")
                (dest / "amd_fidelityfx_dx12.dll").write_text("legacy")  # left by an earlier version
                self.assertTrue(backend.helixsr_status("42")["game"]["copy"])
                backend.helixsr_copy("42")
                self.assertFalse((dest / "amd_fidelityfx_dx12.dll").exists())

    def test_helixsr_game_needs_copy(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with tempfile.TemporaryDirectory() as d:
            backend.HELIXSR_DIR = Path(d) / "HelixSR"
            dest = Path(d) / "game"
            backend.HELIXSR_DIR.mkdir()
            dest.mkdir()
            self.assertTrue(backend._game_needs_copy(dest, "v1"))  # no DLL
            (dest / "helixsr.dll").write_text("a")
            (backend.HELIXSR_DIR / "helixsr.dll").write_text("a")
            self.assertFalse(backend._game_needs_copy(dest, None))  # no versions anywhere: the DLLs are the same
            (backend.HELIXSR_DIR / "helixsr.dll").write_text("b")
            self.assertTrue(backend._game_needs_copy(dest, None))  # ... and now they differ
            self.assertTrue(backend._game_needs_copy(dest, "v1.9.3"))  # the game has no .version
            (dest / ".version").write_text("v1.9.3")
            self.assertFalse(backend._game_needs_copy(dest, "v1.9.3"))
            (dest / ".version").write_text("v1.9.9")
            self.assertTrue(backend._game_needs_copy(dest, "v1.10.0"))  # by numbers, not as text

    def test_helixsr_copy_merges_the_game_ini(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d) / "lib"
            backend.HELIXSR_DIR = Path(d) / "HelixSR"
            backend.HELIXSR_DIR.mkdir()
            (backend.HELIXSR_DIR / "helixsr.dll").write_text("dll")
            (backend.HELIXSR_DIR / "helixsr.ini").write_bytes(
                b"[Sharpening]\r\n; mode\r\nSharpener = off\r\n; new\r\nStrength = 2\r\n")
            dest = lib / "compatdata" / "42" / "pfx" / "drive_c" / "HelixSR"
            dest.mkdir(parents=True)
            (dest / "helixsr.ini").write_bytes(b"[sharpening]\r\nsharpener=rcas\r\nGone = 1\r\n")
            with mock.patch.object(backend.steam, "libraries", return_value=[lib]):
                backend.helixsr_copy("42")
            self.assertEqual((dest / "helixsr.ini").read_bytes(),
                             b"[Sharpening]\r\n; mode\r\nSharpener = rcas\r\n; new\r\nStrength = 2\r\n")

    @staticmethod
    def release(tag):
        resp = mock.MagicMock()
        resp.__enter__.return_value = io.BytesIO(json.dumps({"tag_name": tag}).encode())
        return resp

    def test_helixsr_latest_is_cached_and_tolerant(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with mock.patch.object(backend.urllib.request, "urlopen", side_effect=OSError("offline")) as urlopen:
            self.assertIsNone(backend._helixsr_latest())
            self.assertIsNone(backend._helixsr_latest())  # a failure is retried later, not on every call
            self.assertEqual(urlopen.call_count, 1)
        backend._helixsr_latest_cache.update(at=0.0, ttl=0, tag=None)
        with mock.patch.object(backend.urllib.request, "urlopen", return_value=self.release("v1.9.3")) as urlopen:
            self.assertEqual(backend._helixsr_latest(), "v1.9.3")
            self.assertEqual(backend._helixsr_latest(), "v1.9.3")
            self.assertEqual(urlopen.call_count, 1)
        backend._helixsr_latest_cache.update(at=0.0, ttl=0, tag=None)
        bad = mock.MagicMock()
        bad.__enter__.return_value = io.BytesIO(b"not json")
        with mock.patch.object(backend.urllib.request, "urlopen", return_value=bad):
            self.assertIsNone(backend._helixsr_latest())

    def test_helixsr_check(self):
        backend = load_backend()
        backend.setup(FakeCtx())
        with tempfile.TemporaryDirectory() as d:
            backend.HELIXSR_DIR = Path(d) / "HelixSR"
            check = lambda latest: (setattr(backend, "_helixsr_latest", lambda: latest), backend.helixsr_check())[1]
            self.assertFalse(check("v1.9.3")["update"])  # nothing installed: the download button, not an update
            backend.HELIXSR_DIR.mkdir()
            (backend.HELIXSR_DIR / backend.HELIXSR_DLL).write_text("x")
            self.assertFalse(check("v1.9.3")["update"])  # no .version: nothing to compare
            (backend.HELIXSR_DIR / ".version").write_text("v1.9.2\n")
            out = check("v1.9.3")
            self.assertEqual((out["update"], out["latest"], out["version"]), (True, "v1.9.3", "v1.9.2"))
            self.assertTrue(check("v1.10.0")["update"])  # numbers, not strings
            self.assertFalse(check("v1.9.2")["update"])
            self.assertFalse(check("v1.9.1")["update"])
            self.assertFalse(check(None)["update"])  # offline
            self.assertFalse(check("nightly")["update"])

    def test_helixsr_failed_update_keeps_the_previous_build(self):
        with tempfile.TemporaryDirectory() as d:
            backend = self.helixsr_backend(d)
            backend.HELIXSR_DIR.mkdir()
            (backend.HELIXSR_DIR / backend.HELIXSR_DLL).write_text("old")
            (backend.HELIXSR_DIR / ".version").write_text("v1.9.2\n")
            backend.HELIXSR_SCRIPT.write_text("#!/bin/bash\n")
            proc = self.fake_proc(["[helixsr-fetch] error: build failed\n"], code=1)
            with mock.patch.object(backend.subprocess, "Popen", return_value=proc):
                with self.assertRaises(FakeCtx.Unavailable):
                    backend.helixsr_download()
            status = backend.helixsr_status()
            self.assertEqual((status["found"], status["version"]), (True, "v1.9.2"))
            self.assertEqual((backend.HELIXSR_DIR / backend.HELIXSR_DLL).read_text(), "old")

    @staticmethod
    def fake_proc(lines, code=0):
        proc = mock.Mock(returncode=code, stdout=iter(lines))
        proc.poll.return_value = code
        return proc

    def helixsr_backend(self, d):
        backend = load_backend()
        FakeCtx.tasks = []
        backend.setup(FakeCtx())
        backend.language = lambda: "en"
        backend.HELIXSR_DIR = Path(d) / "HelixSR"
        backend.HELIXSR_SCRIPT = Path(d) / "fetch.sh"
        return backend

    def test_helixsr_download(self):
        with tempfile.TemporaryDirectory() as d:
            backend = self.helixsr_backend(d)
            with self.assertRaises(FakeCtx.Unavailable):
                backend.helixsr_download()
            backend.HELIXSR_SCRIPT.write_text("#!/bin/bash\n")
            lines = ["[helixsr-fetch] buscando la última versión (stable)...\n", "[helixsr-fetch] versión: v1\n",
                     "noise from the setup\n", "[helixsr-fetch] descargando...\n",
                     "[helixsr-fetch] compilando HelixSR (puede tardar unos minutos)...\n", "[helixsr-fetch] listo: x\n"]
            with mock.patch.object(backend.subprocess, "Popen", return_value=self.fake_proc(lines)) as popen:
                self.assertFalse(backend.helixsr_download()["found"])
            self.assertEqual(popen.call_args.args[0], ["bash", str(backend.HELIXSR_SCRIPT), "--yes", "--out", str(backend.HELIXSR_DIR)])
            task = FakeCtx.tasks[-1]
            self.assertEqual(task.label, "Downloading HelixSR")
            self.assertEqual([c[0] for c in task.calls], [0.0, 0.05, 0.10, 0.20, None])
            self.assertEqual(task.end, ("done", "Done"))

    def test_helixsr_download_failure_fails_the_task(self):
        with tempfile.TemporaryDirectory() as d:
            backend = self.helixsr_backend(d)
            backend.HELIXSR_SCRIPT.write_text("#!/bin/bash\n")
            proc = self.fake_proc(["[helixsr-fetch] error: no network\n"], code=1)
            with mock.patch.object(backend.subprocess, "Popen", return_value=proc):
                with self.assertRaises(FakeCtx.Unavailable):
                    backend.helixsr_download()
            self.assertEqual(FakeCtx.tasks[-1].end[0], "fail")
            self.assertIn("no network", FakeCtx.tasks[-1].end[1])
            # the lock is free again
            with mock.patch.object(backend.subprocess, "Popen", return_value=self.fake_proc([])):
                backend.helixsr_download()

    def test_helixsr_download_times_out(self):
        with tempfile.TemporaryDirectory() as d:
            backend = self.helixsr_backend(d)
            backend.HELIXSR_SCRIPT.write_text("#!/bin/bash\n")
            backend.HELIXSR_TIMEOUT = 0
            proc = mock.Mock(returncode=-9)
            proc.stdout = iter(())
            proc.poll.return_value = -9
            proc.kill.side_effect = lambda: None

            def slow_wait():
                import time
                time.sleep(0.2)  # the timer fires while "waiting"
            proc.wait.side_effect = slow_wait
            with mock.patch.object(backend.subprocess, "Popen", return_value=proc):
                with self.assertRaises(FakeCtx.Unavailable):
                    backend.helixsr_download()
            proc.kill.assert_called()
            self.assertEqual(FakeCtx.tasks[-1].end[0], "fail")

    def test_helixsr_download_refused_while_a_game_runs(self):
        with tempfile.TemporaryDirectory() as d:
            backend = self.helixsr_backend(d)
            backend.HELIXSR_SCRIPT.write_text("#!/bin/bash\n")
            with mock.patch.object(FakeCtx.game, "running", {"appid": "1", "name": "G", "shortcut": False}):
                with mock.patch.object(backend.subprocess, "Popen") as popen:
                    with self.assertRaises(FakeCtx.Unavailable):
                        backend.helixsr_download()
                popen.assert_not_called()
            self.assertEqual(FakeCtx.tasks, [])
            # nothing stuck: with the game closed it runs
            with mock.patch.object(backend.subprocess, "Popen", return_value=self.fake_proc([])):
                backend.helixsr_download()

    def test_helixsr_download_is_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            backend = self.helixsr_backend(d)
            backend.HELIXSR_SCRIPT.write_text("#!/bin/bash\n")

            def second(*a, **k):
                with self.assertRaises(FakeCtx.Unavailable):
                    backend.helixsr_download()  # a click while the first one runs
                return self.fake_proc([])
            with mock.patch.object(backend.subprocess, "Popen", side_effect=second) as popen:
                backend.helixsr_download()
                self.assertEqual(popen.call_count, 1)

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
