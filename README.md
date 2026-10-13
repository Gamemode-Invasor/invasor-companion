# Companion

**English** · [Español](README.es.md)

A module for [Invasor](../invasor) that **builds a game's Steam launch options** (`VAR=value … mangohud mako-launch %command%`)
from the panel, with the gamepad, and copies them to the clipboard. Paste the result into the game's Properties › General ›
Launch options. It adds a **Compa** tab (not shown in the Quick Access) with four pages:

- **Lanzador** (Launcher): a live preview of the command and a *Copy* button on top, then the options in sections:
  FG/upscalers (MAKO, lsfg-vk, FSR 4, HelixSR), MangoHud (FPS limit, API and FPS), graphics (wined3d, Zink, HDR, Direct3D),
  Proton (32-bit compatibility, large address aware, esync/fsync, prefix chosen in a folder browser that starts at `compatdata` and can go anywhere), environment (DLL overrides, "not a Steam Deck" = `SteamDeck=0`, custom variables)
  and *Reset all*. Incompatible or empty combinations show a warning. The choices are not saved: they reset when the tab reloads.
- **Game**: everything Steam's files say about the current game (the open page, else the highlighted one, else the
  running one), grouped in sections: general, installation (library, folder, size, state, build, updates), play (last
  played, play time, launch options), compatibility (tool, prefix) and, for non-Steam shortcuts, its executable, start
  directory and tags, plus the store and SteamDB links. Pressing a row copies its value (the AppID included).
- **Steam**: choose any file (a browser that starts at your home folder, any extension) and press *Add to Steam*. It asks
  Steam to add it as a non-Steam game the way Steam supports: it creates `/tmp/addnonsteamgamefile` and opens
  `steam://addnonsteamgame/<encoded path>` with `xdg-open`. `xdg-open` runs with the graphical session's environment (the service has none) and its result is checked. Steam shows its own dialog to confirm; the module then waits for the shortcut to show up in `shortcuts.vdf`.
- **Créditos** (Credits): the author.

The texts follow Steam's language (Spanish or English). The logic is a port of the Companion launcher in
`../companion`; it only builds the text, it never writes to any game.

## Build, test and install
With the core checked out next to this repository (`../invasor`):

```sh
python3 ../invasor/tools/pack_module.py companion       # check, tests -> companion-<version>.zip
python3 ../invasor/tools/install_module.py companion    # or install that zip from ⚙ Settings › Install module
```

## License
[GNU General Public License v3.0 or later](LICENSE) (GPL-3.0-or-later).
