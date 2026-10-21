# Companion

**English** · [Español](README.es.md)

A module for [Invasor](../invasor) that **builds a game's Steam launch options** (`VAR=value … mangohud mako-launch %command%`)
from the panel, with the gamepad, and copies them to the clipboard. Paste the result into the game's Properties › General ›
Launch options. It adds a **Compa** tab (not shown in the Quick Access) with four pages:

- **Lanzador** (Launcher): a live preview of the command and a *Copy* button on top, then the options in sections:
  FG/upscalers (MAKO, lsfg-vk, FSR 4, HelixSR), MangoHud (FPS limit, API and FPS), graphics (wined3d, Zink, HDR, Direct3D),
  Proton (32-bit compatibility, large address aware, esync/fsync, PROTON LOG = `PROTON_LOG=1` at the very start of the command, so Proton writes `~/steam-<AppID>.log`, prefix chosen in a folder browser that starts at `compatdata` and can go anywhere), environment (DLL overrides, "not a Steam Deck" = `SteamDeck=0`, custom variables)
  and *Reset all*. Incompatible or empty combinations show a warning. The choices are not saved: they reset when the tab reloads.
  MAKO and lsfg-vk exclude each other, and so do FSR 4 and HelixSR: turning one on turns the other off.
  HelixSR needs its DLL: *Download and generate DLL* fetches the release and builds it with the official setup in a temporary folder (it asks to confirm the DLSS licence in the UI); its games step never runs, so **nothing is installed in any game** (per-game installation stays only with *Copy HelixSR to the game*). The result goes to `~/.local/share/HelixSR/`: HelixSR Scaler, the OptiScaler the release ships (`OptiScaler.dll`, `OptiScaler.ini`, `OptiScaler/`, `Licenses/` and its READMEs), with `helixsr.dll`, `helixsr.ini` and a `.version` file. `OptiScaler/` also gets NVIDIA's DLSS 310.7.0 `nvngx_dlss.dll`, `nvngx_dlssd.dll` and `nvngx_dlssg.dll` (downloaded if missing, kept from then on, for your machine only): HelixSR Scaler looks for `nvngx_dlss.dll` next to its DLL and, without it, turns spoofing off and the game never offers DLSS. A game that has the current version but lacks them gets the copy offered again. `OptiScaler.ini` comes set up to load from `C:\windows\system32\umu`, with HelixSR only in `FfxDx12SRPath`, and `Dx11Upscaler=ffx_12`, `Dx12Upscaler=ffx` and `VulkanUpscaler=ffx_12` so every API goes through HelixSR. Both inis are yours to edit: on updates your values are kept and any new options are added. Everything is put together and checked in the temporary folder, so if a build fails the previous one stays untouched; nothing is left behind either, and if the installed version is already the latest nothing is rebuilt. Companion also checks the latest stable release (cached for an hour) and, when yours is older, the button becomes *Update HelixSR (old → new)*. *Copy HelixSR to the game* puts all that in the game prefix's `C:\windows\system32\umu`, plus `dxgi.dll` and `d3d12.dll` symlinks to `OptiScaler.dll`, and the option adds `WINE_OPTISCALER_NAME=dxgi.dll`: the Wine of GE-Proton / proton-cachyos loads OptiScaler from there without touching the game's folder. Don't use `PROTON_USE_OPTISCALER` with HelixSR: Proton would put its own OptiScaler in that `umu`. If the game already has Proton's OptiScaler there, it is moved to `umu.proton` (or `umu.proton-<date>`) so you can go back to it, and what earlier versions of the module left in `C:\HelixSR` is removed (its `helixsr.ini` is kept). The copy is only offered when the game lacks something, has Proton's OptiScaler or leftovers in `C:\HelixSR`, or has no `.version` or an older one than the installed; the game's inis are merged (its values stay, new options are added). The download is a heavy task, so it shows as a task in Invasor's **Tasks** panel (Select in the Invasor panel) with its progress, runs one at a time and is refused while a game is running.
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
`../companion`; it only builds the text and never touches the game's files; the only thing it writes into a game is *Copy HelixSR to the game*, into its prefix (`C:\windows\system32\umu`) and only when you press it.

## Requirements
Invasor 0.2.0 or newer (`min_core`): it uses `ctx.task` and `ctx.events`.

## Build, test and install
With the core checked out next to this repository (`../invasor`):

```sh
python3 ../invasor/tools/pack_module.py companion       # check, tests -> companion-<version>.zip
python3 ../invasor/tools/install_module.py companion    # or install that zip from ⚙ Settings › Install module
```

## License
[GNU General Public License v3.0 or later](LICENSE) (GPL-3.0-or-later).
