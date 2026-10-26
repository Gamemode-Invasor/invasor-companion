# Companion

**English** · [Español](README.es.md)

A module for [Invasor](../invasor) that **builds a game's Steam launch options** (`VAR=value … mangohud mako-launch %command%`) from the panel, with the gamepad, and copies them to the clipboard. Paste the result into the game's Properties › General › Launch options. It adds a **Compa** tab (not shown in the Quick Access) with four pages:

- **Launcher**: a live preview of the command and a *Copy* button on top, then the options in sections: FG/upscalers (MAKO, lsfg-vk, FSR 4), MangoHud (FPS limit, API and FPS), graphics (wined3d, Zink, HDR, Direct3D), Proton (32-bit compatibility, large address aware, esync/fsync, PROTON LOG = `PROTON_LOG=1` at the very start of the command, so Proton writes `~/steam-<AppID>.log`, prefix chosen in a folder browser that starts at `compatdata` and can go anywhere), environment (DLL overrides, "not a Steam Deck" = `SteamDeck=0`, custom variables) and *Reset all*. Incompatible or empty combinations show a warning. The choices are not saved: they reset when the tab reloads. MAKO and lsfg-vk exclude each other: turning one on turns the other off. Their profile is picked with ←→ among the ones installed on this machine (the `[[profile]]` names of `~/.config/mako-render/conf.toml` and `~/.config/lsfg-vk/conf.toml`, or of `$MAKO_CONFIG` / `$LSFGVK_CONFIG`), read when the tab opens; when none is found (not installed, or the file can't be read), it's typed instead. HelixSR has moved to the [Opti](https://github.com/Gamemode-Invasor/invasor-opti) module (Opti tab → Global → Custom DLLs), and the upscalers section says so where its switch was. What earlier versions of Companion installed isn't touched: games that have HelixSR Scaler in their prefix keep it, and `~/.local/share/HelixSR/` can be removed by hand.
- **Game**: everything Steam's files say about the current game (the open page, else the highlighted one, else the running one), grouped in sections: general, installation (library, folder, size, state, build, updates), play (last played, play time, launch options, asked to Steam itself when it answers, else read from its files), compatibility (tool, prefix) and, for non-Steam shortcuts, its executable, start directory and tags, plus the store and SteamDB links. Pressing a row copies its value (the AppID included). Under the title, *Enrichers* asks for the game's scores, with no keys or accounts: Steam's reviews (rating, share of positive ones and the SteamDB score, from SteamSpy's counts), Metacritic (from Steam's store) and ProtonDB's tier; a non-Steam game is looked up in Steam's store by its title, and the match is shown. Below them, *Open ProtonDB* (the game's page, or a search by title for a non-Steam game) and *Open HowLongToBeat* (a search by title: HLTB has no public API to read the hours from) open in Steam's browser.
- **Steam**: choose any file (Invasor's file picker, which starts at your home folder; any extension) and press *Add to Steam*. Invasor adds it as a non-Steam game named after the file (without its extension), with no dialog to confirm, and Steam shows a notification; if a shortcut to that file is already there, it is left as it is. Below it, a folded **Cleaning** section lists the `compatdata`/`shadercache` folders of games that are no longer installed (in every library) and the grid images in `userdata/*/config/grid` that belong to no game or shortcut. Everything is marked; you choose and confirm, and only items from a fresh scan are ever deleted. Game names are remembered in the module's data (`ctx.data`, refreshed on every Steam start; the `names.json` of earlier versions is moved there and removed) so a leftover folder can say what it was.
- **Credits**: the author.

The texts follow Steam's language (Spanish or English). The logic is a port of the Companion launcher in `../companion`; it only builds the text and never touches the game's files.

## Screenshots

<p align="center">
  <img src="docs/launcher.png" alt="Launcher page" width="32%">
  <img src="docs/game.png" alt="Game page with the enrichers" width="32%">
  <img src="docs/steam.png" alt="Steam page" width="32%">
</p>

## Requirements
Invasor 0.3.0 or newer (`min_core`): it uses `ctx.events`, `ctx.toml`, `ctx.data`, `ctx.paths`, `ctx.vdf`, `ctx.steam` (adding shortcuts, reading launch options, opening pages), `ctx.http` (the enrichers), `ctx.steam_language`, and in the UI `ctx.copy` and `ctx.pickPath`.

## Build, test and install
With the core checked out next to this repository (`../invasor`):

```sh
python3 ../invasor/tools/pack_module.py companion       # check, tests -> companion-<version>.zip
python3 ../invasor/tools/install_module.py companion    # or install that zip from ⚙ Settings › Install module
```

## License
[GNU General Public License v3.0 or later](LICENSE) (GPL-3.0-or-later).
