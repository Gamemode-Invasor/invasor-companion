"""Cleaning of what Steam leaves behind: compatdata/shadercache of games that are gone, and unused grid images."""
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


def _shortcut_ids(steam_root):
    ids = set()
    for f in Path(steam_root).glob("userdata/*/config/shortcuts.vdf"):
        try:
            shortcuts = kv.loads_binary(f.read_bytes()).get("shortcuts", {})
        except (OSError, ValueError):
            continue
        for entry in shortcuts.values():
            appid = {k.lower(): v for k, v in entry.items()}.get("appid")
            if isinstance(appid, int):
                ids.add(str(appid & 0xFFFFFFFF))
    return ids


def _installed_ids(libraries):
    ids = set()
    for lib in libraries:
        for acf in Path(lib).glob("appmanifest_*.acf"):
            try:
                appid = kv.get(kv.loads_text(acf.read_text(errors="replace")), "AppState", "appid")
            except OSError:
                continue
            if appid:
                ids.add(str(appid))
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


def scan(steam_root=steam.STEAM_ROOT, libraries=None):
    """{"prefixes": [{"path", "appid", "kind", "library", "size"}], "grids": [{"path", "appid", "size"}]}.

    prefixes: compatdata/shadercache folders of an app that is neither installed nor a shortcut.
    grids: images of userdata/*/config/grid whose AppID is not installed, a shortcut or a game with a prefix.
    """
    libraries = steam.libraries(steam_root) if libraries is None else libraries
    known = _installed_ids(libraries) | _shortcut_ids(steam_root)
    folders = list(_prefix_folders(libraries))
    # A game with a prefix keeps its art, as Grid Cleaner did.
    in_use = known | {f.name for _lib, _kind, f in folders}
    prefixes = [
        {"path": str(f), "appid": f.name, "kind": kind, "library": str(lib), "size": _size(f)}
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
                grids.append({"path": e.path, "appid": m.group(1), "size": _size(e.path)})
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
