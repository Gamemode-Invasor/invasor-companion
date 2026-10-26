"""Companion: builds Steam launch options (VAR=value ... %command%) from the Launcher tab's choices."""
import json
import os
from pathlib import Path

from . import cleaner, command, gameinfo

ctx = None


def setup(context):
    global ctx
    ctx = context
    cleaner.vdf = gameinfo.vdf = ctx.vdf
    # Also runs now if Steam is already up: the names are kept fresh without opening the Cleaning section.
    ctx.events.on("steam_start", refresh_names)


def build(state):
    return command.build(state if isinstance(state, dict) else {}, home=str(Path.home()))


def language():
    """"es" or "en", from Steam's language ("spanish" and "latam" give es)."""
    return "es" if ctx.steam_language() == "es" else "en"


def compatdata_dir():
    """Where the prefix picker starts: the first library's compatdata, else None (the picker opens at home)."""
    try:
        libraries = ctx.paths.libraries()
    except ctx.Unavailable:
        return None
    return next((str(lib / "compatdata") for lib in libraries if (lib / "compatdata").is_dir()), None)


def add_to_steam(path):
    """Adds a file to Steam as a non-Steam game named after it, without its extension: {"appid", "existed"}."""
    if not isinstance(path, str):
        raise ctx.InvalidArgument("path must be a string")
    return ctx.steam.add_to(Path(path).stem, path)  # it checks the path


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
    options = None
    try:
        options = ctx.steam.launch_options(appid)
    except (ctx.InvalidArgument, ctx.Unavailable) as e:
        ctx.log.info("launch options of %s from Steam's files: %s", appid, e)
    return gameinfo.game_info(appid, ctx.paths.steam_root(), ctx.paths.libraries(), name=known.get("name"),
                              shortcut=known.get("shortcut"), launch_options=options)


# AppID -> name of every game seen, so an orphan can say what it was: {"names": {...}} in ctx.data. Up to
# Companion 0.3.0 it was a names.json of its own, read once when ctx.data has none.
OLD_NAMES_FILE = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "invasor/companion/names.json"


def _load_names():
    data = ctx.data.load()
    if "names" not in data:
        try:
            data = {"names": json.loads(OLD_NAMES_FILE.read_text())}
        except (OSError, ValueError):
            return {}
    names = data["names"]
    return {str(k): v for k, v in names.items() if isinstance(v, str)} if isinstance(names, dict) else {}


def _save_names(names):
    """Failing to save is harmless: the next scan tries again."""
    try:
        ctx.data.update(names=names)
    except (OSError, ctx.Unavailable) as e:
        ctx.log.warning("could not save the game names: %s", e)
        return
    try:
        OLD_NAMES_FILE.unlink(missing_ok=True)
        OLD_NAMES_FILE.parent.rmdir()
    except OSError:
        pass


def refresh_names(payload=None):
    """Steam started: remember the names of the installed games and shortcuts (it runs in its own thread)."""
    try:
        _, names = cleaner.remember_names(ctx.paths.steam_root(), ctx.paths.libraries(), _load_names(), _save_names)
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

    return cleaner.scan(ctx.paths.steam_root(), ctx.paths.libraries(), _load_names(), _save_names, name_of)


def clean_delete(paths):
    """Deletes the chosen items of clean_scan (a fresh scan decides which paths are allowed)."""
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise ctx.InvalidArgument("paths must be a list of strings")
    out = cleaner.delete(paths, ctx.paths.steam_root(), ctx.paths.libraries())
    ctx.log.info("cleaning: deleted %d, failed %d", len(out["deleted"]), len(out["failed"]))
    return out


METHODS = {"build": build, "language": language, "compatdata_dir": compatdata_dir, "add_to_steam": add_to_steam,
           "game_info": game_info, "profiles": profiles, "clean_scan": clean_scan, "clean_delete": clean_delete}
