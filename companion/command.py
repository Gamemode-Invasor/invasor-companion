"""Builds Steam launch options from the form state: VAR=value ... [mangohud] [mako-launch] %command%.

Pure functions (no I/O), a port of Companion's CommandBuilder.js.
"""
import re

BARE = re.compile(r"^[A-Za-z0-9_.,:/=+@%-]+$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Variables the options above set: a custom variable can't reuse them.
RESERVED = frozenset({
    "MAKO_PROFILE", "LSFGVK_PROFILE", "ENABLE_GAMESCOPE_WSI", "MANGOHUD_CONFIG", "PROTON_USE_WOW64",
    "PROTON_USE_WINED3D", "MESA_LOADER_DRIVER_OVERRIDE", "STEAM_COMPAT_DATA_PATH", "WINEDLLOVERRIDES",
    "FSR4_UPGRADE", "PROTON_FSR4_UPGRADE", "PROTON_FSR4_INDICATOR", "DXVK_HDR", "PROTON_ENABLE_HDR",
    "PROTON_NO_D3D11", "PROTON_NO_D3D10", "PROTON_DXVK_D3D8", "PROTON_NO_ESYNC", "PROTON_NO_FSYNC",
    "PROTON_FORCE_LARGE_ADDRESS_AWARE", "PROTON_LOG", "SteamDeck",
})

# Boolean options: state key -> what it adds.
FLAGS = (
    ("wined3d", "PROTON_USE_WINED3D=1"),
    ("zink", "MESA_LOADER_DRIVER_OVERRIDE=zink"),
    ("hdr", "DXVK_HDR=1 PROTON_ENABLE_HDR=1"),
    ("noD3d11", "PROTON_NO_D3D11=1"),
    ("noD3d10", "PROTON_NO_D3D10=1"),
    ("dxvkD3d8", "PROTON_DXVK_D3D8=1"),
    ("wow64", "PROTON_USE_WOW64=1"),
    ("noEsync", "PROTON_NO_ESYNC=1"),
    ("noFsync", "PROTON_NO_FSYNC=1"),
    ("largeAddressAware", "PROTON_FORCE_LARGE_ADDRESS_AWARE=1"),
)


def quote(value):
    """Inside double quotes, for the shell Steam runs the options with."""
    return '"' + re.sub(r'([\\"$`])', r"\\\1", str(value)) + '"'


def quote_if_needed(value):
    text = str(value)
    return text if BARE.match(text) else quote(text)


def is_valid_name(name):
    return bool(NAME.match(str(name)))


def _text(value):
    return str(value if value is not None else "").strip()


def _section(state, key):
    value = state.get(key)
    return value if isinstance(value, dict) else {}


def _fps(value, default=30, top=240):
    """The FPS limit as an int in 0..top; anything that isn't a number gives the default."""
    try:
        return max(0, min(top, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return default


def mangohud_config(state):
    fps_limit = _section(state, "fpsLimit")
    fps = f"fps_limit={_fps(fps_limit.get('value', 30))}" if fps_limit.get("on") else ""
    info = "legacy_layout=0,gpu_name,fps" if state.get("showInfo") else ""
    if fps and info:
        return f"{fps},{info}"
    if fps:
        return f"{fps},no_display"
    return info


def build(state, home="~"):
    """{"command", "warnings"}: command is "" when nothing is selected.

    Warnings are {"code", "name"?} for the UI to word: lsfg_wined3d, lsfg_mangohud, empty_mako,
    empty_lsfg, empty_prefix, empty_dll, mako_lsfg, custom_invalid / custom_reserved / custom_duplicate (name).
    """
    variables, warnings = [], []
    # PROTON_LOG=1 goes first of all: Proton writes ~/steam-<appid>.log.
    if state.get("protonLog"):
        variables.append("PROTON_LOG=1")
    mako, lsfg, fsr4 = _section(state, "mako"), _section(state, "lsfg"), _section(state, "fsr4")
    prefix, dll = _section(state, "prefix"), _section(state, "dllOverrides")

    mako_profile = _text(mako.get("profile"))
    use_mako = bool(mako.get("on")) and bool(mako_profile)
    if use_mako:
        variables.append("MAKO_PROFILE=" + quote(mako_profile))
    elif mako.get("on"):
        warnings.append({"code": "empty_mako"})

    # MAKO and lsfg-vk exclude each other (the UI turns one off when the other is picked).
    use_lsfg = bool(lsfg.get("on")) and not mako.get("on")
    if lsfg.get("on") and mako.get("on"):
        warnings.append({"code": "mako_lsfg"})
    lsfg_profile = _text(lsfg.get("profile"))
    if use_lsfg and lsfg_profile:
        variables.append("LSFGVK_PROFILE=" + quote(lsfg_profile) + " ENABLE_GAMESCOPE_WSI=0")
    elif use_lsfg:
        warnings.append({"code": "empty_lsfg"})

    use_fsr4 = bool(fsr4.get("on"))
    # PROTON_FSR4_UPGRADE=1: GE-Proton / proton-cachyos pick the latest version.
    if use_fsr4:
        variables.append("FSR4_UPGRADE=1 PROTON_FSR4_UPGRADE=1")
    if use_fsr4 and state.get("fsr4Indicator"):
        variables.append("PROTON_FSR4_INDICATOR=1")

    mangohud = mangohud_config(state)
    if mangohud:
        variables.append("MANGOHUD_CONFIG=" + quote(mangohud))

    for key, text in FLAGS:
        if state.get(key):
            variables.append(text)

    path = _text(prefix.get("path"))
    if prefix.get("on") and path:
        variables.append("STEAM_COMPAT_DATA_PATH=" + quote(path))
    elif prefix.get("on"):
        warnings.append({"code": "empty_prefix"})

    overrides = _text(dll.get("value"))
    if dll.get("on") and overrides:
        variables.append("WINEDLLOVERRIDES=" + quote(overrides))
    elif dll.get("on"):
        warnings.append({"code": "empty_dll"})

    if state.get("steamDeck"):
        variables.append("SteamDeck=0")

    seen = set()
    for item in state.get("custom") or []:
        name = _text(item.get("name")) if isinstance(item, dict) else ""
        if not name:
            continue
        if not is_valid_name(name):
            warnings.append({"code": "custom_invalid", "name": name})
        elif name in RESERVED:
            warnings.append({"code": "custom_reserved", "name": name})
        elif name in seen:
            warnings.append({"code": "custom_duplicate", "name": name})
        else:
            seen.add(name)
            variables.append(name + "=" + quote_if_needed(item.get("value", "")))

    if use_lsfg and state.get("wined3d"):
        warnings.append({"code": "lsfg_wined3d"})
    if use_lsfg and mangohud:
        warnings.append({"code": "lsfg_mangohud"})

    wrappers = []
    if mangohud:
        wrappers.append("mangohud")
    if use_mako:
        wrappers.append(f"{home}/.local/bin/mako-launch")

    command = ""
    if variables or wrappers:
        command = " ".join(variables + wrappers + ["%command%"])
    return {"command": command, "warnings": warnings}
