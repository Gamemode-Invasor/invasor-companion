"""Steam facts the Launcher tab needs: the user's language and the compatdata prefixes."""
import os
import re
import urllib.parse
from pathlib import Path

HOME = Path.home()
STEAM_ROOT = HOME / ".local/share/Steam"
REGISTRY = HOME / ".steam/registry.vdf"
# SD cards and other disks mounted by the system, even if Steam doesn't list them.
MEDIA_GLOBS = ("/run/media/*/steamapps", "/run/media/*/*/steamapps")

LANGUAGE = re.compile(r'"language"\s+"(\w+)"')
VDF_PATH = re.compile(r'^\s*"path"\s+"(.*)"', re.MULTILINE)


def language(registry=REGISTRY, default="en"):
    """"es" or "en", from Steam's language ("spanish" and "latam" give es)."""
    try:
        m = LANGUAGE.search(Path(registry).read_text(errors="replace"))
    except OSError:
        return default
    if not m:
        return default
    value = m.group(1).lower()
    if value in ("spanish", "latam"):
        return "es"
    return "en" if value == "english" else default


def libraries(steam_root=STEAM_ROOT, media_globs=MEDIA_GLOBS):
    """Every existing steamapps folder (Steam's own, libraryfolders.vdf, mounted media), each once."""
    found = [Path(steam_root) / "steamapps"]
    try:
        text = (Path(steam_root) / "steamapps/libraryfolders.vdf").read_text(errors="replace")
        found += [Path(p.replace("\\\\", "\\")) / "steamapps" for p in VDF_PATH.findall(text)]
    except OSError:
        pass
    for pattern in media_globs:
        found += sorted(Path("/").glob(pattern.lstrip("/")))
    return sorted({Path(os.path.realpath(p)) for p in found if p.is_dir()})


def start_dir(steam_root=STEAM_ROOT, media_globs=MEDIA_GLOBS):
    """Where the folder browser starts: the first library's compatdata, else the home folder."""
    for lib in libraries(steam_root, media_globs):
        if (lib / "compatdata").is_dir():
            return str(lib / "compatdata")
    return str(HOME)


def listdir(path, name_of=lambda appid: None, limit=1000, files=False):
    """{"path", "parent", "dirs": [{"name", "label"}], "files": [{"name"}], "error"} for the browser.

    Hidden entries left out, sorted, folders before files ("files" stays empty unless asked for), at most
    `limit` entries in all. Inside a compatdata folder each folder's label is "appid - game". A folder that
    can't be read comes back with "error" and nothing listed (the path is still the one asked for).
    """
    folder = Path(os.path.realpath(path))
    parent = None if folder == folder.parent else str(folder.parent)
    out = {"path": str(folder), "parent": parent, "dirs": [], "files": [], "error": None}
    try:
        entries = [e for e in os.scandir(folder) if not e.name.startswith(".")]
        dirs = sorted(e.name for e in entries if e.is_dir())
        names = sorted(e.name for e in entries if files and not e.is_dir() and e.is_file())
    except OSError as e:
        out["error"] = e.strerror or str(e)
        return out
    in_compatdata = folder.name == "compatdata"
    for name in dirs[:limit]:
        label = name
        if in_compatdata and name.isascii() and name.isdigit():
            game = name_of(name)
            label = f"{name} - {game}" if game else name
        out["dirs"].append({"name": name, "label": label})
    out["files"] = [{"name": n} for n in names[: max(0, limit - len(out["dirs"]))]]
    return out


def steam_url(path):
    """The steam:// link that makes Steam offer to add `path` as a non-Steam game."""
    return "steam://addnonsteamgame/" + urllib.parse.quote(path, safe="")


# The graphical session's variables: the Invasor service doesn't have them, and xdg-open needs them to
# hand the steam:// link to the running Steam.
SESSION_VARS = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE",
                "XDG_RUNTIME_DIR", "XDG_DATA_DIRS", "DBUS_SESSION_BUS_ADDRESS")


def _environ(pid_dir):
    try:
        raw = (pid_dir / "environ").read_bytes()
    except OSError:
        return {}
    pairs = (item.partition(b"=") for item in raw.split(b"\0") if b"=" in item)
    return {k.decode(errors="replace"): v.decode(errors="replace") for k, _, v in pairs}


def session_env(proc_root="/proc"):
    """The session variables of the user's running Steam (else of any of their graphical processes)."""
    steam, other = {}, {}
    try:
        pids = [d for d in Path(proc_root).iterdir() if d.name.isdigit()]
    except OSError:
        return {}
    for d in pids:
        env = _environ(d)
        if not (env.get("WAYLAND_DISPLAY") or env.get("DISPLAY")):
            continue
        try:
            comm = (d / "comm").read_text().strip()
        except OSError:
            comm = ""
        picked = {k: env[k] for k in SESSION_VARS if k in env}
        if comm in ("steam", "steamwebhelper"):
            steam = steam or picked
        elif not other:
            other = picked
        if steam:
            break
    return steam or other


def steam_handler_registered(mimeapps=HOME / ".config/mimeapps.list"):
    """Is steam:// handled (x-scheme-handler/steam= in mimeapps.list)? Without it the link opens nothing."""
    try:
        text = Path(mimeapps).read_text(errors="replace")
    except OSError:
        return False
    return any("x-scheme-handler/steam=" in line.lower() for line in text.splitlines())


def shortcut_added(path, steam_root=STEAM_ROOT):
    """Is `path` already the executable of a non-Steam shortcut of any local Steam user?

    The path must be a whole value of the file ("path" in quotes, or between NULs), not part of a longer one.
    """
    raw = str(path).encode()
    needles = (b'"' + raw + b'"', b"\0" + raw + b"\0")
    for f in sorted((Path(steam_root) / "userdata").glob("*/config/shortcuts.vdf")):
        try:
            data = f.read_bytes()
            if any(n in data for n in needles):
                return True
        except OSError:
            continue
    return False
