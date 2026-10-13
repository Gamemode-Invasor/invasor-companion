"""Companion: builds Steam launch options (VAR=value ... %command%) from the Launcher tab's choices."""
import os
import subprocess
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


def helixsr_status():
    """{"found", "dir"}: found when both DLLs are in HELIXSR_DIR."""
    found = all((HELIXSR_DIR / name).is_file() for name in HELIXSR_DLLS)
    return {"found": found, "dir": str(HELIXSR_DIR)}


def helixsr_download():
    """Runs the download script, then says what is there (see helixsr_status)."""
    if not HELIXSR_SCRIPT.is_file():
        raise ctx.Unavailable(f"download script not found: {HELIXSR_SCRIPT}")
    try:
        # No shell; --yes accepts the DLSS licence prompt (the UI is the user's confirmation).
        done = subprocess.run(["bash", str(HELIXSR_SCRIPT), "--yes", "--out", str(HELIXSR_DIR)], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=HELIXSR_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise ctx.Unavailable("the HelixSR download timed out")
    except OSError as e:
        raise ctx.Unavailable(f"could not run the download script: {e}")
    if done.returncode != 0:
        ctx.log.error("%s exited %s: %s", HELIXSR_SCRIPT, done.returncode, done.stderr.strip())
        raise ctx.Unavailable(f"download script exited {done.returncode}: {done.stderr.strip()}")
    return helixsr_status()


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
           "helixsr_download": helixsr_download}
