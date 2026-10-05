"""Everything Steam's own files say about a game, for the Game tab (read-only)."""
import re
from pathlib import Path

from . import kv, steam

COMPAT_PATH = re.compile(r"""STEAM_COMPAT_DATA_PATH=(?:"([^"]*)"|'([^']*)'|(\S+))""")


def _read_text(path):
    try:
        return kv.loads_text(Path(path).read_text(errors="replace"))
    except OSError:
        return {}


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _local_app(appid, steam_root):
    """The game's entry in the first localconfig.vdf that has one."""
    for f in sorted((Path(steam_root) / "userdata").glob("*/config/localconfig.vdf")):
        apps = kv.get(_read_text(f), "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", default={})
        entry = kv.get(apps, str(appid))
        if isinstance(entry, dict):
            return entry
    return {}


def _shortcut(appid, steam_root):
    """The non-Steam shortcut with this (unsigned 32-bit) appid, keys lowercased, else None."""
    for f in sorted((Path(steam_root) / "userdata").glob("*/config/shortcuts.vdf")):
        try:
            shortcuts = kv.loads_binary(f.read_bytes()).get("shortcuts", {})
        except (OSError, ValueError):
            continue
        for entry in shortcuts.values():
            low = {k.lower(): v for k, v in entry.items()}
            if str(_int(low.get("appid")) & 0xFFFFFFFF) == str(appid):
                return low
    return None


def _manifest(appid, libraries):
    for lib in libraries:
        acf = _read_text(Path(lib) / f"appmanifest_{appid}.acf")
        state = kv.get(acf, "AppState")
        if isinstance(state, dict):
            return Path(lib), state
    return None, {}


def _tool(appid, steam_root):
    mapping = kv.get(_read_text(Path(steam_root) / "config/config.vdf"),
                     "InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping", default={})
    for key in (str(appid), "0"):
        name = kv.get(mapping, key, "name")
        if name:
            return name
    return None


def _compat_override(options):
    m = COMPAT_PATH.search(options or "")
    return next((g for g in m.groups() if g), None) if m else None


def game_info(appid, steam_root=steam.STEAM_ROOT, libraries=None, name=None, shortcut=None):
    """{"appid", "name", "kind": "steam"|"shortcut", "groups": [{"id", "rows": [{"key", "value", "type"}]}]}.

    Values are raw (numbers, timestamps, paths); `type` tells the UI how to show them: text, code, path, bytes,
    timestamp, minutes, url, state, autoupdate. Rows without a value are left out, and so are empty groups.
    """
    appid = str(appid)
    libraries = steam.libraries(steam_root) if libraries is None else libraries
    entry = _shortcut(appid, steam_root)
    is_shortcut = bool(shortcut) if shortcut is not None else entry is not None
    lib, manifest = (None, {}) if is_shortcut else _manifest(appid, libraries)
    local = _local_app(appid, steam_root)
    groups = {}

    def add(group, key, value, type="text"):
        if value in (None, "", 0, [], {}):
            return
        groups.setdefault(group, []).append({"key": key, "value": value, "type": type})

    name = name or kv.get(manifest, "name") or (entry or {}).get("appname")
    add("general", "name", name)
    add("general", "appid", appid, "code")
    add("general", "kind", "shortcut" if is_shortcut else "steam")

    if manifest:
        folder = kv.get(manifest, "installdir")
        add("install", "library", str(lib.parent), "path")
        add("install", "folder", str(lib / "common" / folder) if folder else None, "path")
        add("install", "size", _int(kv.get(manifest, "SizeOnDisk")), "bytes")
        add("install", "state", _int(kv.get(manifest, "StateFlags")), "state")
        add("install", "build", kv.get(manifest, "buildid"), "code")
        target = kv.get(manifest, "TargetBuildID")
        if target != kv.get(manifest, "buildid"):
            add("install", "target_build", target, "code")
        add("install", "updated", _int(kv.get(manifest, "LastUpdated")), "timestamp")
        add("install", "autoupdate", kv.get(manifest, "AutoUpdateBehavior"), "autoupdate")
        add("install", "language", kv.get(manifest, "language"))
        pending = _int(kv.get(manifest, "BytesToDownload")) - _int(kv.get(manifest, "BytesDownloaded"))
        add("install", "pending", pending if pending > 0 else 0, "bytes")

    last = _int(kv.get(local, "LastPlayed")) or _int(kv.get(manifest, "LastPlayed")) or _int((entry or {}).get("lastplaytime"))
    add("play", "last_played", last, "timestamp")
    add("play", "playtime", _int(kv.get(local, "Playtime")), "minutes")
    add("play", "playtime_2wks", _int(kv.get(local, "Playtime2wks")), "minutes")
    options = (entry or {}).get("launchoptions") if is_shortcut else kv.get(local, "LaunchOptions")
    add("play", "launch_options", options, "code")
    add("play", "resolution", kv.get(local, "ResolutionOverride"))

    add("compat", "tool", _tool(appid, steam_root), "code")
    override = _compat_override(options)
    add("compat", "prefix_override", override, "path")
    for lib_dir in libraries:
        prefix = Path(lib_dir) / "compatdata" / appid
        if prefix.is_dir():
            add("compat", "prefix", str(prefix), "path")
            break

    if is_shortcut and entry:
        exe = str(entry.get("exe", "")).strip('"')
        add("shortcut", "exe", exe, "path")
        add("shortcut", "start_dir", str(entry.get("startdir", "")).strip('"'), "path")
        add("shortcut", "icon", entry.get("icon"), "path")
        tags = entry.get("tags")
        add("shortcut", "tags", ", ".join(str(v) for v in tags.values()) if isinstance(tags, dict) else None)

    if not is_shortcut:
        add("links", "store", f"https://store.steampowered.com/app/{appid}", "url")
        add("links", "steamdb", f"https://steamdb.info/app/{appid}/", "url")

    order = ("general", "install", "play", "compat", "shortcut", "links")
    return {"appid": appid, "name": name, "kind": "shortcut" if is_shortcut else "steam",
            "groups": [{"id": g, "rows": groups[g]} for g in order if g in groups]}
