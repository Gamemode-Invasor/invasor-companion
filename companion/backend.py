"""Companion: builds Steam launch options (VAR=value ... %command%) from the Launcher tab's choices."""
import filecmp
import os
import shutil
import subprocess
import threading
from pathlib import Path

from . import command, gameinfo, steam

ctx = None


def setup(context):
    global ctx
    ctx = context


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


HELIXSR_DIR = Path.home() / ".local/share/invasor/user-modules/companion/HelixSR"
HELIXSR_DLLS = ("amd_fidelityfx_dx12.dll", "amd_fidelityfx_upscaler_dx12.dll")
# The script that fetches and builds the DLLs into HELIXSR_DIR (shipped in the module's bin/).
HELIXSR_SCRIPT = Path(__file__).resolve().parent / "bin" / "helixsr-fetch.sh"
HELIXSR_TIMEOUT = 1800
_helixsr_busy = threading.Lock()


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


def _in_sync(dest):
    """Does dest hold every file of HELIXSR_DIR, identical?"""
    files = [p for p in HELIXSR_DIR.rglob("*") if p.is_file()]
    return bool(files) and all(
        (dest / p.relative_to(HELIXSR_DIR)).is_file()
        and filecmp.cmp(p, dest / p.relative_to(HELIXSR_DIR), shallow=False)
        for p in files
    )


def helixsr_status(appid=None):
    """{"found", "dir", "game"}: found when both DLLs are in HELIXSR_DIR.

    game is None without a game; else {"prefix": bool, "copy": bool}: does it have a prefix, and does
    HelixSR need copying into it (missing folder or different files)?
    """
    found = all((HELIXSR_DIR / name).is_file() for name in HELIXSR_DLLS)
    game = None
    appid = _appid(appid)
    if appid:
        dest = _game_dest(appid)
        game = {"prefix": dest is not None, "copy": found and dest is not None and not _in_sync(dest)}
    return {"found": found, "dir": str(HELIXSR_DIR), "game": game}


def helixsr_copy(appid):
    """Copies HELIXSR_DIR into the game's prefix (C:\\HelixSR); returns helixsr_status(appid)."""
    appid = _appid(appid)
    if not appid:
        raise ctx.InvalidArgument("no game")
    if not helixsr_status()["found"]:
        raise ctx.Unavailable("the HelixSR DLLs are not generated yet")
    dest = _game_dest(appid)
    if dest is None:
        raise ctx.Unavailable("the game has no Proton prefix yet (run it once)")
    try:
        shutil.copytree(HELIXSR_DIR, dest, dirs_exist_ok=True)
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


METHODS = {"build": build, "language": language, "browse": browse, "add_to_steam": add_to_steam,
           "is_added": is_added, "game_info": game_info, "helixsr_status": helixsr_status,
           "helixsr_download": helixsr_download, "helixsr_copy": helixsr_copy}
