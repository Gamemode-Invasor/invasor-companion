"""Companion: the Launcher tab builds Steam launch options (VAR=value ... %command%); the Game tab shows what Steam
knows about a game and its scores (enrichers); the Steam tab adds files as non-Steam games and cleans what games
that are gone left behind."""
import json
import os
from pathlib import Path

from . import cleaner, command, enrich as enrichers, gameinfo

ctx = None


def setup(context):
    global ctx
    ctx = context
    gameinfo.vdf = ctx.vdf  # cleaner reads VDF through gameinfo too
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


def _appid(value):
    """A game's appid as a string of digits (it ends up in URLs and file names); else InvalidArgument."""
    appid = str(value)
    if not (appid.isascii() and appid.isdigit()):
        raise ctx.InvalidArgument("appid must be a number")
    return appid


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
    appid = _appid(appid)
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


_enriched = {}  # (appid, name, shortcut) -> enrich()'s answer, for this run: only those where every source answered


def enrich(appid, name=None, shortcut=False):
    """The Game tab's enrichers: {"steam", "metacritic", "protondb", "match", "protondb_url", "hltb_url"}.

    A non-Steam game is looked up in Steam's store by its name ("match": {"appid", "name"}). A source that
    fails leaves its part None. Slow (a few requests): a plain method, in a worker thread.
    """
    appid = _appid(appid)
    name = name if isinstance(name, str) else ""
    shortcut = bool(shortcut)
    key = (appid, name, shortcut)
    if key in _enriched:
        return _enriched[key]
    failed = False

    def get(url):
        nonlocal failed
        try:
            return ctx.http.get_json(url)
        except (ctx.InvalidArgument, ctx.Unavailable) as e:
            failed = failed or isinstance(e, ctx.Unavailable)
            ctx.log.info("enricher %s: %s", url.split("/")[2], e)
            return None

    match = None
    steam_id = None if shortcut else appid
    if shortcut and name:
        found = enrichers.best_match(get(enrichers.storesearch_url(name)))
        if found:
            steam_id = found[0]
            match = {"appid": found[0], "name": found[1]}
    out = {"steam": None, "metacritic": None, "protondb": None, "match": match,
           "protondb_url": enrichers.protondb_url(appid, name, shortcut), "hltb_url": enrichers.hltb_url(name)}
    if steam_id:
        out["steam"] = enrichers.steam(get(enrichers.STEAMSPY.format(steam_id)))
        out["metacritic"] = enrichers.metacritic(get(enrichers.APPDETAILS.format(steam_id)), steam_id)
        out["protondb"] = enrichers.protondb(get(enrichers.PROTONDB.format(steam_id)))
    if not failed:
        _enriched[key] = out
    return out


def open_page(url):
    """Opens an enricher's page (ProtonDB, HowLongToBeat) in Steam's browser; nothing else."""
    if not isinstance(url, str) or not url.startswith(enrichers.PAGES):
        raise ctx.InvalidArgument("not an enricher's page")
    ctx.steam.open_url(url)
    return True


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
           "game_info": game_info, "enrich": enrich, "open_page": open_page, "profiles": profiles,
           "clean_scan": clean_scan, "clean_delete": clean_delete}
