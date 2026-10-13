"""Cleaning of what Steam leaves behind: compatdata/shadercache of games that are gone, and unused grid images."""
import json
import os
import re
import shutil
from pathlib import Path

from . import kv, steam

PREFIX_DIRS = ("compatdata", "shadercache")
LEADING_ID = re.compile(r"^(\d+)")


def _size(path):
    """Bytes under path (a file or a folder); what can't be read counts as 0. Symlinks aren't followed."""
    try:
        if not os.path.isdir(path) or os.path.islink(path):
            return os.lstat(path).st_size
    except OSError:
        return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def _shortcut_names(steam_root):
    """{appid: name} of the non-Steam shortcuts."""
    ids = {}
    for f in Path(steam_root).glob("userdata/*/config/shortcuts.vdf"):
        try:
            shortcuts = kv.loads_binary(f.read_bytes()).get("shortcuts", {})
        except (OSError, ValueError):
            continue
        for entry in shortcuts.values():
            low = {k.lower(): v for k, v in entry.items()}
            if isinstance(low.get("appid"), int):
                ids[str(low["appid"] & 0xFFFFFFFF)] = str(low.get("appname") or "")
    return ids


def _installed_names(libraries):
    """{appid: name} of the installed games."""
    ids = {}
    for lib in libraries:
        for acf in Path(lib).glob("appmanifest_*.acf"):
            try:
                state = kv.get(kv.loads_text(acf.read_text(errors="replace")), "AppState", default={})
            except OSError:
                continue
            if kv.get(state, "appid"):
                ids[str(kv.get(state, "appid"))] = str(kv.get(state, "name") or "")
    return ids


def _prefix_folders(libraries):
    """(library, kind, folder) of every numeric, non-zero folder in compatdata and shadercache."""
    for lib in libraries:
        for kind in PREFIX_DIRS:
            try:
                entries = sorted(os.scandir(Path(lib) / kind), key=lambda e: e.name)
            except OSError:
                continue
            for e in entries:
                if e.name.isascii() and e.name.isdigit() and int(e.name) != 0 and (e.is_dir() or e.is_symlink()):
                    yield Path(lib), kind, Path(e.path)


def _load_names(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}


def _remember(path, names):
    """Saves the names of the games seen, so an orphan can still say what it was. Failing to save is harmless."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(json.dumps(names, ensure_ascii=False, sort_keys=True))
        os.replace(tmp, path)
    except OSError:
        pass


def scan(steam_root=steam.STEAM_ROOT, libraries=None, names_file=None, name_of=lambda appid: None):
    """{"prefixes": [{"path", "appid", "name", "kind", "library", "size"}], "grids": [{"path", "appid", "name", "size"}]}.

    name: what the app was called, from names_file (a {appid: name} cache of every game seen by past scans,
    updated here) or name_of(appid); "" if unknown.

    prefixes: compatdata/shadercache folders of an app that is neither installed nor a shortcut.
    grids: images of userdata/*/config/grid whose AppID is not installed, a shortcut or a game with a prefix.
    """
    libraries = steam.libraries(steam_root) if libraries is None else libraries
    seen = {**_installed_names(libraries), **_shortcut_names(steam_root)}
    known = set(seen)
    names = _load_names(names_file) if names_file else {}
    fresh = {k: v for k, v in seen.items() if v and names.get(k) != v}
    if fresh and names_file:
        names.update(fresh)
        _remember(names_file, names)
    names.update(fresh)

    def name(appid):
        return names.get(appid) or str(name_of(appid) or "")
    folders = list(_prefix_folders(libraries))
    # A game with a prefix keeps its art, as Grid Cleaner did.
    in_use = known | {f.name for _lib, _kind, f in folders}
    prefixes = [
        {"path": str(f), "appid": f.name, "name": name(f.name), "kind": kind, "library": str(lib), "size": _size(f)}
        for lib, kind, f in folders
        if f.name not in known
    ]
    grids = []
    for grid_dir in sorted(Path(steam_root).glob("userdata/*/config/grid")):
        try:
            entries = sorted(os.scandir(grid_dir), key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            m = LEADING_ID.match(e.name)
            if m and e.is_file(follow_symlinks=False) and m.group(1) not in in_use:
                grids.append({"path": e.path, "appid": m.group(1), "name": name(m.group(1)), "size": _size(e.path)})
    return {"prefixes": prefixes, "grids": grids}


def delete(paths, steam_root=steam.STEAM_ROOT, libraries=None):
    """Deletes the given paths, but only those a fresh scan() lists. {"deleted": [...], "failed": [...]}."""
    found = scan(steam_root, libraries)
    allowed = {item["path"] for item in found["prefixes"] + found["grids"]}
    deleted, failed = [], []
    for path in dict.fromkeys(paths):
        if path not in allowed:
            failed.append(path)
            continue
        try:
            if os.path.islink(path) or not os.path.isdir(path):
                os.unlink(path)
            else:
                shutil.rmtree(path)
            deleted.append(path)
        except OSError:
            failed.append(path)
    return {"deleted": deleted, "failed": failed}
