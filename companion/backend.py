"""Companion: builds Steam launch options (VAR=value ... %command%) from the Launcher tab's choices."""
import filecmp
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from . import cleaner, command, gameinfo, steam

ctx = None


def setup(context):
    global ctx
    ctx = context
    # Also runs now if Steam is already up: the names are kept fresh without opening the Cleaning section.
    ctx.events.on("steam_start", refresh_names)


def build(state):
    return command.build(state if isinstance(state, dict) else {}, home=str(Path.home()))


def language():
    return steam.language()


def browse(path=None, files=False, home=False):
    """One folder of the browser. Without a valid path it starts at compatdata, or at home with home=True."""

    def name_of(appid):
        try:
            return (ctx.game.info(appid) or {}).get("name")
        except Exception:
            return None

    if not isinstance(path, str) or not Path(path).is_dir():
        path = str(Path.home()) if home else steam.start_dir()
    return steam.listdir(path, name_of, files=bool(files))


# Steam's handler for steam://addnonsteamgame looks for this file, as in the documented shell snippet.
MARKER = Path("/tmp/addnonsteamgamefile")
OPEN_TIMEOUT = 10


def _check_file(path):
    if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file():
        raise ctx.InvalidArgument("path must be an existing file")


def add_to_steam(path):
    """Asks Steam to add a file as a non-Steam game (its own dialog confirms it).

    Same steps as Relic: a fresh marker file, then xdg-open on the steam:// link, run with the graphical
    session's environment (the service has none) and waited for. {"ok", "already"}; poll is_added() after.
    """
    _check_file(path)
    if steam.shortcut_added(path):
        return {"ok": True, "already": True}
    if not steam.steam_handler_registered():
        ctx.log.warning("steam:// isn't registered in mimeapps.list: the link may open nothing")
    url = steam.steam_url(path)
    try:
        MARKER.unlink()
    except OSError:
        pass
    MARKER.touch()
    env = dict(os.environ, **steam.session_env())
    env["PATH"] = os.pathsep.join(filter(None, [env.get("PATH"), "/usr/local/bin", "/usr/bin", "/bin"]))
    try:
        # No shell: the path never gets interpreted.
        done = subprocess.run(["xdg-open", url], env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=OPEN_TIMEOUT)
    except subprocess.TimeoutExpired:
        ctx.log.warning("xdg-open still running after %ss, going on", OPEN_TIMEOUT)
        return {"ok": True, "already": False}
    except OSError as e:
        raise ctx.Unavailable(f"xdg-open failed: {e}")
    if done.returncode != 0:
        ctx.log.error("xdg-open %s exited %s: %s", url, done.returncode, done.stderr.strip())
        raise ctx.Unavailable(f"xdg-open exited {done.returncode}: {done.stderr.strip()}")
    ctx.log.info("asked Steam to add %s (display %s)", path, env.get("WAYLAND_DISPLAY") or env.get("DISPLAY"))
    return {"ok": True, "already": False}


def is_added(path):
    """Has Steam written the file into a shortcuts.vdf yet? (After the user confirms its dialog.)"""
    _check_file(path)
    return steam.shortcut_added(path)


# Data, not config, and outside the module's folder (a reinstall replaces it): the script keeps the last good
# build here, plus the installed version in ".version".
HELIXSR_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "HelixSR"
HELIXSR_DLL = "helixsr.dll"
HELIXSR_INI = "helixsr.ini"
HELIXSR_FILES = (HELIXSR_DLL, HELIXSR_INI, ".version")  # what goes into a game's prefix (the version last)
HELIXSR_OLD_NAMES = ("amd_fidelityfx_dx12.dll", "amd_fidelityfx_upscaler_dx12.dll")  # earlier versions of the module
# The script that fetches and builds the DLLs into HELIXSR_DIR (shipped in the module's bin/).
HELIXSR_SCRIPT = Path(__file__).resolve().parent / "bin" / "helixsr-fetch.sh"
HELIXSR_TIMEOUT = 1800
HELIXSR_RELEASE_API = "https://api.github.com/repos/lonewolf0622/HelixSR/releases/latest"  # the stable one
HELIXSR_CHECK_TTL = 3600  # seconds a found tag is reused; a failed check is retried after HELIXSR_CHECK_RETRY
HELIXSR_CHECK_RETRY = 120
_helixsr_busy = threading.Lock()
_helixsr_latest_cache = {"at": 0.0, "ttl": 0, "tag": None}
_helixsr_latest_lock = threading.Lock()


def _appid(appid):
    """The digits of a real AppID (it ends up in paths), or None for no game."""
    if appid in (None, ""):
        return None
    appid = str(appid)
    if not (appid.isascii() and appid.isdigit()):
        raise ctx.InvalidArgument("appid must be a number")
    return appid


def _game_dest(appid):
    """compatdata/<appid>/pfx/drive_c/HelixSR of the first library that has the game's prefix, else None."""
    for lib in steam.libraries():
        drive_c = lib / "compatdata" / appid / "pfx" / "drive_c"
        if drive_c.is_dir():
            return drive_c / "HelixSR"
    return None


def _read_version(folder):
    """The .version of a HelixSR folder, or None."""
    try:
        return (folder / ".version").read_text().strip() or None
    except OSError:
        return None


def _older(version, than):
    """Is version older than `than`? By their numbers (v1.10.0 > v1.9.9); different text if they have none."""
    a, b = _version_key(version), _version_key(than)
    return a < b if a and b else version != than


def _game_needs_copy(dest, installed):
    """Should HelixSR be copied into dest? When it has no DLL, leftovers of earlier versions, no .version or an older
    one than the installed. Without an installed .version (a build by hand) the DLLs are compared instead."""
    if not (dest / HELIXSR_DLL).is_file() or any((dest / name).exists() for name in HELIXSR_OLD_NAMES):
        return True
    if installed:
        have = _read_version(dest)
        return have is None or _older(have, installed)
    return not filecmp.cmp(HELIXSR_DIR / HELIXSR_DLL, dest / HELIXSR_DLL, shallow=False)


def _merge_ini(mine, new):
    """The new ini with the values of `mine`: its structure and comments, your values; options it no longer has are
    dropped, new ones come with their default. (Same as the awk of helixsr-fetch.sh.)"""
    def parse(line):
        text = line.strip()
        if text.startswith("[") and text.endswith("]"):
            return text.lower(), None
        if not text or text[0] in ";#" or "=" not in text:
            return None, None
        return None, text.split("=", 1)[0].strip()

    values, section = {}, ""
    for line in mine.splitlines():
        sec, key = parse(line)
        if sec:
            section = sec
        elif key:
            values[(section, key.lower())] = line.split("=", 1)[1].strip()
    out, section = [], ""
    for line in new.splitlines(keepends=True):
        sec, key = parse(line)
        if sec:
            section = sec
        elif key and (section, key.lower()) in values:
            eol = line[len(line.rstrip("\r\n")):]
            line = f"{key} = {values[(section, key.lower())]}{eol}"
        out.append(line)
    return "".join(out)


def _replace(path, data):
    """Writes bytes to path atomically: a half copy never replaces a good file."""
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def helixsr_status(appid=None):
    """{"found", "dir", "version", "game"}: found when the DLL is in HELIXSR_DIR; version is its .version or None.

    game is None without a game; else {"prefix": bool, "copy": bool, "version": str|None}: does it have a prefix,
    does HelixSR need copying into it (see _game_needs_copy), and which version does it carry?
    """
    found = (HELIXSR_DIR / HELIXSR_DLL).is_file()
    version = _read_version(HELIXSR_DIR)
    game = None
    appid = _appid(appid)
    if appid:
        dest = _game_dest(appid)
        game = {"prefix": dest is not None,
                "copy": found and dest is not None and _game_needs_copy(dest, version),
                "version": _read_version(dest) if dest is not None else None}
    return {"found": found, "dir": str(HELIXSR_DIR), "version": version, "game": game}


def _helixsr_latest():
    """Tag of the latest stable HelixSR release, or None (offline, rate limit, odd answer). Cached in memory."""
    with _helixsr_latest_lock:
        cache = _helixsr_latest_cache
        if time.monotonic() - cache["at"] < cache["ttl"]:
            return cache["tag"]
        tag = None
        try:
            req = urllib.request.Request(HELIXSR_RELEASE_API, headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                tag = json.load(resp).get("tag_name")
            tag = tag if isinstance(tag, str) and tag else None
        except (OSError, ValueError, AttributeError) as e:
            ctx.log.info("could not check the latest HelixSR: %s", e)
        cache.update(at=time.monotonic(), ttl=HELIXSR_CHECK_TTL if tag else HELIXSR_CHECK_RETRY, tag=tag)
        return tag


def _version_key(tag):
    """(1, 9, 3) for "v1.9.3"; None when there are no numbers to compare."""
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums) if nums else None


def helixsr_check(appid=None):
    """helixsr_status plus "latest" (the latest stable tag, None when unknown) and "update" (installed is older).

    Asks GitHub (cached), so it is separate from helixsr_status, which stays local and quick. With no installed
    .version there is nothing to compare, so no update is offered.
    """
    status = helixsr_status(appid)
    latest = _helixsr_latest()
    installed, newest = _version_key(status["version"]), _version_key(latest)
    status["latest"] = latest
    status["update"] = bool(status["found"] and installed and newest and installed < newest)
    return status


def helixsr_copy(appid):
    """Copies HELIXSR_FILES into the game's prefix (C:\\HelixSR); returns helixsr_status(appid)."""
    appid = _appid(appid)
    if not appid:
        raise ctx.InvalidArgument("no game")
    if not helixsr_status()["found"]:
        raise ctx.Unavailable("HelixSR is not generated yet")
    dest = _game_dest(appid)
    if dest is None:
        raise ctx.Unavailable("the game has no Proton prefix yet (run it once)")
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for name in HELIXSR_OLD_NAMES:  # no leftovers of earlier versions
            (dest / name).unlink(missing_ok=True)
        for name in HELIXSR_FILES:  # the DLL first and the version last: a cut copy is proposed again
            src = HELIXSR_DIR / name
            if not src.is_file():
                continue
            data = src.read_bytes()
            if name == HELIXSR_INI and (dest / name).is_file():  # the game's own settings stay
                data = _merge_ini((dest / name).read_text(errors="replace"), data.decode(errors="replace")).encode()
            _replace(dest / name, data)
    except OSError as e:
        raise ctx.Unavailable(f"could not copy HelixSR: {e}")
    ctx.log.info("copied HelixSR to %s", dest)
    return helixsr_status(appid)


# Stages of helixsr-fetch.sh for the Tasks panel: line prefix -> (fraction, text es, text en).
# None as the fraction = no bar (the build takes an unknown while).
HELIXSR_STAGES = (
    ("buscando", 0.05, "Buscando la última versión", "Looking for the latest version"),
    ("versión:", 0.10, "Versión encontrada", "Version found"),
    ("descargando", 0.20, "Descargando", "Downloading"),
    ("compilando", None, "Compilando (puede tardar unos minutos)", "Building (it can take a few minutes)"),
)


def _helixsr_stage(line, es):
    """(fraction, text) for a "[helixsr-fetch] ..." line of the script, else None."""
    prefix = "[helixsr-fetch] "
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):]
    for key, fraction, text_es, text_en in HELIXSR_STAGES:
        if rest.startswith(key):
            return fraction, text_es if es else text_en
    return None


def helixsr_download(appid=None):
    """Runs the download script as a task in the Tasks panel, then says what is there (see helixsr_status)."""
    if not HELIXSR_SCRIPT.is_file():
        raise ctx.Unavailable(f"download script not found: {HELIXSR_SCRIPT}")
    # Heavy (download and build): not while a game is running. The UI says so before it gets here.
    if ctx.game.running:
        raise ctx.Unavailable("a game is running: close it to download HelixSR")
    # One download at a time: two scripts would write the same folder.
    if not _helixsr_busy.acquire(blocking=False):
        raise ctx.Unavailable("a HelixSR download is already running")
    try:
        es = language() == "es"
        with ctx.task("Descargando HelixSR" if es else "Downloading HelixSR") as task:
            task.update(0.0, "Iniciando" if es else "Starting")
            _helixsr_run(task, es)
    finally:
        _helixsr_busy.release()
    return helixsr_status(appid)


def _helixsr_run(task, es):
    try:
        # No shell; --yes accepts the DLSS licence prompt (the UI is the user's confirmation).
        proc = subprocess.Popen(["bash", str(HELIXSR_SCRIPT), "--yes", "--out", str(HELIXSR_DIR)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except OSError as e:
        raise ctx.Unavailable(f"could not run the download script: {e}")
    timed_out = threading.Event()

    def expire():
        timed_out.set()
        proc.kill()

    timer = threading.Timer(HELIXSR_TIMEOUT, expire)
    timer.start()
    tail = []
    try:
        for line in proc.stdout:
            line = line.rstrip()
            tail = (tail + [line])[-40:]
            stage = _helixsr_stage(line, es)
            if stage:
                task.update(*stage)
        proc.wait()
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if timed_out.is_set():
        raise ctx.Unavailable("the HelixSR download timed out")
    if proc.returncode != 0:
        last = "\n".join(tail)
        ctx.log.error("%s exited %s: %s", HELIXSR_SCRIPT, proc.returncode, last)
        error = next((l for l in reversed(tail) if "error" in l), tail[-1] if tail else "")
        raise ctx.Unavailable(f"download script exited {proc.returncode}: {error}")
    task.done("Listo" if es else "Done")


def game_info(appid=None):
    """What Steam's files say about a game (default: the selected one), for the Game tab."""
    if appid in (None, ""):
        appid = (ctx.game.selected or {}).get("appid")
    if not appid:
        raise ctx.InvalidArgument("no game")
    appid = str(appid)
    # It ends up in file names: only the digits of a real AppID.
    if not (appid.isascii() and appid.isdigit()):
        raise ctx.InvalidArgument("appid must be a number")
    known = {}
    try:
        known = ctx.game.info(appid) or {}
    except Exception:
        pass
    return gameinfo.game_info(appid, name=known.get("name"), shortcut=known.get("shortcut"))


# AppID -> name of every game seen, so an orphan can say what it was. Data, not config, and outside the
# module's folder (user-modules/companion), which a reinstall replaces.
NAMES_FILE = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "invasor/companion/names.json"


_names_lock = threading.Lock()  # the Steam-start thread and a scan both read, add and save the file


def _load_names():
    try:
        data = json.loads(NAMES_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}


def _save_names(names):
    """Failing to save is harmless: the next scan tries again."""
    try:
        NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = NAMES_FILE.with_suffix(".tmp")
        with _names_lock:
            tmp.write_text(json.dumps(names, ensure_ascii=False, sort_keys=True))
            os.replace(tmp, NAMES_FILE)
    except OSError as e:
        ctx.log.warning("could not save %s: %s", NAMES_FILE, e)


def refresh_names(payload=None):
    """Steam started: remember the names of the installed games and shortcuts (it runs in its own thread)."""
    try:
        _, names = cleaner.remember_names(names=_load_names(), save_names=_save_names)
        ctx.log.info("game names known: %d", len(names))
    except Exception:
        ctx.log.exception("could not refresh the game names")


def clean_scan():
    """What can be cleaned: orphan compatdata/shadercache folders and unused grid images (see cleaner.scan)."""

    def name_of(appid):
        try:
            return (ctx.game.info(appid) or {}).get("name")
        except Exception:
            return None

    return cleaner.scan(names=_load_names(), name_of=name_of, save_names=_save_names)


def clean_delete(paths):
    """Deletes the chosen items of clean_scan (a fresh scan decides which paths are allowed)."""
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise ctx.InvalidArgument("paths must be a list of strings")
    out = cleaner.delete(paths)
    ctx.log.info("cleaning: deleted %d, failed %d", len(out["deleted"]), len(out["failed"]))
    return out


METHODS = {"build": build, "language": language, "browse": browse, "add_to_steam": add_to_steam,
           "is_added": is_added, "game_info": game_info, "helixsr_status": helixsr_status,
           "helixsr_check": helixsr_check, "helixsr_download": helixsr_download, "helixsr_copy": helixsr_copy,
           "clean_scan": clean_scan, "clean_delete": clean_delete}
