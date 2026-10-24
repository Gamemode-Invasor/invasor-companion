"""Companion: builds Steam launch options (VAR=value ... %command%) from the Launcher tab's choices."""
import json
import os
import subprocess
import threading
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


# Where MAKO and lsfg-vk read their profiles: the variable when it's set, else <XDG config>/<folder>/conf.toml.
PROFILE_CONFIGS = {"mako": ("MAKO_CONFIG", "mako-render"), "lsfg": ("LSFGVK_CONFIG", "lsfg-vk")}


def _profile_config(var, folder):
    if os.environ.get(var):
        return Path(os.environ[var])
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / folder / "conf.toml"


def profiles():
    """{"mako": [names], "lsfg": [names]}: the [[profile]] names of each program's conf.toml, in its order; []
    when it has none or can't be read (the Launcher tab then lets the user type one)."""
    out = {}
    for key, (var, folder) in PROFILE_CONFIGS.items():
        path = _profile_config(var, folder)
        try:
            data, _ = ctx.toml.load(path)
        except (ctx.InvalidArgument, ctx.Unavailable, OSError) as e:
            ctx.log.warning("can't read the %s profiles in %s: %s", key, path, e)
            data = {}
        items = data.get("profile")
        names = [p.get("name") for p in items if isinstance(p, dict)] if isinstance(items, list) else []
        out[key] = list(dict.fromkeys(n for n in names if isinstance(n, str) and n))
    return out


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
    except Exception as e:
        ctx.log.info("game info for %s not available: %s", appid, e)
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
           "is_added": is_added, "game_info": game_info, "profiles": profiles, "clean_scan": clean_scan,
           "clean_delete": clean_delete}
