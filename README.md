# Companion

**English** · [Español](README.es.md)

A module for [Invasor](../invasor) that **builds a game's Steam launch options** (`VAR=value … mangohud mako-launch %command%`)
from the panel, with the gamepad, and copies them to the clipboard. Paste the result into the game's Properties › General ›
Launch options. It adds a **Compa** tab (not shown in the Quick Access) with four pages:

- **Lanzador** (Launcher): a live preview of the command and a *Copy* button on top, then the options in sections:
  FG/upscalers (MAKO, lsfg-vk, FSR 4), MangoHud (FPS limit, API and FPS), graphics (wined3d, Zink, HDR, Direct3D),
  Proton (32-bit compatibility, large address aware, esync/fsync, PROTON LOG = `PROTON_LOG=1` at the very start of the command, so Proton writes `~/steam-<AppID>.log`, prefix chosen in a folder browser that starts at `compatdata` and can go anywhere), environment (DLL overrides, "not a Steam Deck" = `SteamDeck=0`, custom variables)
  and *Reset all*. Incompatible or empty combinations show a warning. The choices are not saved: they reset when the tab reloads.
  MAKO and lsfg-vk exclude each other: turning one on turns the other off.
  HelixSR has moved to the [Opti](https://github.com/Gamemode-Invasor/invasor-opti) module (Opti tab → Global → Custom DLLs), and the upscalers section says so where its switch was. What earlier versions of Companion installed isn't touched: games that have HelixSR Scaler in their prefix keep it, and `~/.local/share/HelixSR/` can be removed by hand.
- **Game**: everything Steam's files say about the current game (the open page, else the highlighted one, else the
  running one), grouped in sections: general, installation (library, folder, size, state, build, updates), play (last
  played, play time, launch options), compatibility (tool, prefix) and, for non-Steam shortcuts, its executable, start
  directory and tags, plus the store and SteamDB links. Pressing a row copies its value (the AppID included).
- **Steam**: choose any file (a browser that starts at your home folder, any extension) and press *Add to Steam*. It asks
  Steam to add it as a non-Steam game the way Steam supports: it creates `/tmp/addnonsteamgamefile` and opens
  `steam://addnonsteamgame/<encoded path>` with `xdg-open`. `xdg-open` runs with the graphical session's environment (the service has none) and its result is checked. Steam shows its own dialog to confirm; the module then waits for the shortcut to show up in `shortcuts.vdf`.
  Below it, a folded **Cleaning** section lists the `compatdata`/`shadercache` folders of games that are no longer installed (in every library) and the grid images in `userdata/*/config/grid` that belong to no game or shortcut. Everything is marked; you choose and confirm, and only items from a fresh scan are ever deleted. Game names are remembered in `~/.local/share/invasor/companion/names.json` (refreshed on every Steam start) so a leftover folder can say what it was.
- **Créditos** (Credits): the author.

The texts follow Steam's language (Spanish or English). The logic is a port of the Companion launcher in
`../companion`; it only builds the text and never touches the game's files.

## Requirements
Invasor 0.2.0 or newer (`min_core`): it uses `ctx.events`.

## Build, test and install
With the core checked out next to this repository (`../invasor`):

```sh
python3 ../invasor/tools/pack_module.py companion       # check, tests -> companion-<version>.zip
python3 ../invasor/tools/install_module.py companion    # or install that zip from ⚙ Settings › Install module
```

## License
[GNU General Public License v3.0 or later](LICENSE) (GPL-3.0-or-later).
