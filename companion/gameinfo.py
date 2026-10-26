"""Everything Steam's own files say about a game, for the Game tab (read-only)."""
import re
from pathlib import Path

vdf = None  # the core's ctx.vdf, set by backend.setup

COMPAT_PATH = re.compile(r"""STEAM_COMPAT_DATA_PATH=(?:"([^"]*)"|'([^']*)'|(\S+))""")


def _read_text(path):
    try:
        return vdf.loads_text(Path(path).read_text(errors="replace"))
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
        apps = vdf.get(_read_text(f), "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", default={})
        entry = vdf.get(apps, str(appid))
        if isinstance(entry, dict):
            return entry
    return {}


def shortcuts(steam_root):
    """{appid: entry} of every account's non-Steam shortcuts: the (unsigned 32-bit) appid as a string, the
    entry's keys lowercased."""
    out = {}
    for f in sorted((Path(steam_root) / "userdata").glob("*/config/shortcuts.vdf")):
        try:
            entries = vdf.loads_binary(f.read_bytes()).get("shortcuts", {})
        except (OSError, ValueError):
            continue
        for entry in entries.values():
            low = {k.lower(): v for k, v in entry.items()}
            if isinstance(low.get("appid"), int):
                out.setdefault(str(low["appid"] & 0xFFFFFFFF), low)
    return out


def _manifest(appid, libraries):
    for lib in libraries:
        acf = _read_text(Path(lib) / f"appmanifest_{appid}.acf")
        state = vdf.get(acf, "AppState")
        if isinstance(state, dict):
            return Path(lib), state
    return None, {}


def _tool(appid, steam_root):
    mapping = vdf.get(_read_text(Path(steam_root) / "config/config.vdf"),
                     "InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping", default={})
    for key in (str(appid), "0"):
        name = vdf.get(mapping, key, "name")
        if name:
            return name
    return None


def _compat_override(options):
    m = COMPAT_PATH.search(options or "")
    return next((g for g in m.groups() if g), None) if m else None


def game_info(appid, steam_root, libraries, name=None, shortcut=None, launch_options=None):
    """{"appid", "name", "kind": "steam"|"shortcut", "groups": [{"id", "rows": [{"key", "value", "type"}]}]}.

    Values are raw (numbers, timestamps, paths); `type` tells the UI how to show them: text, code, path, bytes,
    timestamp, minutes, url, state, autoupdate. Rows without a value are left out, and so are empty groups.
    launch_options: Steam's own answer, when there is one; else the files' (localconfig.vdf lags behind Steam).
    """
    appid = str(appid)
    entry = shortcuts(steam_root).get(appid)
    is_shortcut = bool(shortcut) if shortcut is not None else entry is not None
    lib, manifest = (None, {}) if is_shortcut else _manifest(appid, libraries)
    local = _local_app(appid, steam_root)
    groups = {}

    def add(group, key, value, type="text"):
        if value in (None, "", 0, [], {}):
            return
        groups.setdefault(group, []).append({"key": key, "value": value, "type": type})

    name = name or vdf.get(manifest, "name") or (entry or {}).get("appname")
    add("general", "name", name)
    add("general", "appid", appid, "code")
    add("general", "kind", "shortcut" if is_shortcut else "steam")

    if manifest:
        folder = vdf.get(manifest, "installdir")
        add("install", "library", str(lib.parent), "path")
        add("install", "folder", str(lib / "common" / folder) if folder else None, "path")
        add("install", "size", _int(vdf.get(manifest, "SizeOnDisk")), "bytes")
        add("install", "state", _int(vdf.get(manifest, "StateFlags")), "state")
        add("install", "build", vdf.get(manifest, "buildid"), "code")
        target = vdf.get(manifest, "TargetBuildID")
        if target != vdf.get(manifest, "buildid"):
            add("install", "target_build", target, "code")
        add("install", "updated", _int(vdf.get(manifest, "LastUpdated")), "timestamp")
        add("install", "autoupdate", vdf.get(manifest, "AutoUpdateBehavior"), "autoupdate")
        add("install", "language", vdf.get(manifest, "language"))
        pending = _int(vdf.get(manifest, "BytesToDownload")) - _int(vdf.get(manifest, "BytesDownloaded"))
        add("install", "pending", pending if pending > 0 else 0, "bytes")

    last = _int(vdf.get(local, "LastPlayed")) or _int(vdf.get(manifest, "LastPlayed")) or _int((entry or {}).get("lastplaytime"))
    add("play", "last_played", last, "timestamp")
    add("play", "playtime", _int(vdf.get(local, "Playtime")), "minutes")
    add("play", "playtime_2wks", _int(vdf.get(local, "Playtime2wks")), "minutes")
    options = launch_options
    if options is None:
        options = (entry or {}).get("launchoptions") if is_shortcut else vdf.get(local, "LaunchOptions")
    add("play", "launch_options", options, "code")
    add("play", "resolution", vdf.get(local, "ResolutionOverride"))

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
