import { currentGame, defineModule, ui, type ModuleCtx, type WindowHandle, type WindowSpec } from "invasor";

type Lang = "es" | "en";
interface Warning { code: string; name?: string }
interface Built { command: string; warnings: Warning[] }
interface Dir {
  path: string;
  parent: string | null;
  dirs: { name: string; label: string }[];
  files: { name: string }[];
  error: string | null;
}
interface Custom { name: string; value: string }

const T = {
  es: {
    preview: "Opciones de lanzamiento",
    nothingPreview: "(nada seleccionado)",
    copy: "Copiar al portapapeles",
    copied: "Copiado",
    copyFailed: "No se pudo copiar",
    nothing: "Nada seleccionado",
    reset: "Restablecer todo",
    resetAsk: "¿Restablecer todas las opciones?",
    yes: "Restablecer",
    cancel: "Cancelar",
    frames: "FG/Escaladores",
    mako: "MAKO",
    makoHint: "Añade MAKO_PROFILE y el envoltorio mako-launch.",
    lsfg: "Lossless Scaling (lsfg-vk)",
    lsfgHint: "Con el plugin de Decky el perfil debe ser decky-lsfg-vk.",
    profile: "Perfil",
    fsr4: "FSR4 (última versión)",
    fsr4Hint: "Usa la última versión de GE-Proton / proton-cachyos.",
    fsr4Indicator: "Indicador de FSR 4",
    helixsr: "Escalador HelixSR",
    helixsrHint: "Añade PROTON_USE_OPTISCALER y su configuración. Incompatible con FSR4.",
    helixsrFound: "DLL encontradas (en %dir%)",
    helixsrMissing: "DLL no encontradas",
    helixsrDownload: "Descargar y generar DLL",
    helixsrCopy: "Copiar DLL al juego",
    helixsrCopied: "DLL copiadas al juego",
    helixsrCopyFailed: "No se pudieron copiar las DLL",
    helixsrDownloading: "Descargando HelixSR…",
    helixsrDone: "HelixSR descargado",
    helixsrFailed: "No se pudo descargar HelixSR",
    cleaning: "Limpieza",
    cleanScan: "Buscar archivos sobrantes",
    cleanPrefixes: "Prefijos y shaders de juegos que ya no están",
    cleanGrids: "Imágenes no usadas",
    cleanNothing: "No hay nada que limpiar",
    cleanDelete: "Eliminar seleccionados",
    cleanAsk: "¿Eliminar %n% elementos? No se puede deshacer.",
    cleanDone: "Eliminados: %n%",
    cleanFailed: "No se pudieron eliminar: %n%",
    helixsrHeavy: "Tarea pesada: puedes seguirla en Tareas (Select en el panel de Invasor)",
    helixsrGameRunning: "Hay un juego en ejecución: ciérralo para descargar HelixSR, es una tarea pesada",
    mangohud: "MangoHud",
    mangohudHint: "Con cualquier opción de MangoHud se añade el comando mangohud antes de %command%.",
    fpsLimit: "Limitar FPS",
    fps: "FPS",
    showInfo: "Mostrar API y FPS",
    graphics: "Gráficos",
    wined3d: "Forzar OpenGL (wined3d)",
    zink: "Zink (OpenGL sobre Vulkan)",
    hdr: "HDR",
    noD3d11: "Sin Direct3D 11",
    noD3d10: "Sin Direct3D 10",
    dxvkD3d8: "DXVK para Direct3D 8",
    proton: "Proton",
    wow64: "Compatibilidad con 32 bits",
    largeAddressAware: "Large address aware",
    noEsync: "Sin esync",
    noFsync: "Sin fsync",
    prefix: "Prefijo (STEAM_COMPAT_DATA_PATH)",
    chooseFolder: "Elegir carpeta",
    chooseFolderMsg: "Elige el prefijo de Proton",
    chooseThis: "Elegir esta carpeta",
    chooseFile: "Elige un archivo para añadir a Steam",
    chooseFileMsg: "Elige el archivo que añadir a Steam",
    addToSteam: "Añadir a Steam",
    sentToSteam: "Enviado a Steam: confirma en su diálogo",
    addFailed: "No se pudo añadir",
    gameNone: "Selecciona un juego para ver su información",
    gameCopyValue: "Pulsa para copiar",
    gameKindSteam: "Juego de Steam",
    gameKindShortcut: "Acceso directo no Steam",
    gg_general: "General",
    gg_install: "Instalación",
    gg_play: "Juego",
    gg_compat: "Compatibilidad",
    gg_shortcut: "Acceso directo",
    gg_links: "Enlaces",
    gk_name: "Nombre",
    gk_appid: "AppID",
    gk_kind: "Tipo",
    gk_library: "Biblioteca",
    gk_folder: "Carpeta",
    gk_size: "Tamaño en disco",
    gk_state: "Estado",
    gk_build: "Compilación",
    gk_target_build: "Compilación objetivo",
    gk_updated: "Última actualización",
    gk_autoupdate: "Actualizaciones",
    gk_language: "Idioma",
    gk_pending: "Pendiente de descargar",
    gk_last_played: "Última partida",
    gk_playtime: "Tiempo de juego",
    gk_playtime_2wks: "Últimas dos semanas",
    gk_launch_options: "Opciones de lanzamiento",
    gk_resolution: "Resolución forzada",
    gk_tool: "Herramienta de compatibilidad",
    gk_prefix: "Prefijo",
    gk_prefix_override: "Prefijo (opciones de lanzamiento)",
    gk_exe: "Ejecutable",
    gk_start_dir: "Directorio de inicio",
    gk_icon: "Icono",
    gk_tags: "Etiquetas",
    gk_store: "Tienda",
    gk_steamdb: "SteamDB",
    st_installed: "Instalado",
    st_update_required: "Actualización pendiente",
    st_updating: "Actualizando",
    st_other: "Otro",
    au_0: "Siempre al día",
    au_1: "Solo al lanzar",
    au_2: "Prioridad alta",
    unit_h: "h",
    unit_min: "min",
    alreadyInSteam: "Ya está en Steam",
    addedToSteam: "Añadido a Steam",
    notAddedInTime: "No se añadió: ¿Steam abierto y diálogo confirmado?",
    unreadable: "No se puede leer",
    environment: "Entorno",
    dll: "Sobrescribir DLL (WINEDLLOVERRIDES)",
    dllValue: "Valor",
    steamDeck: "No es una Steam Deck",
    customVars: "Variables personalizadas",
    varName: "Nombre",
    varValue: "Valor",
    addVar: "Añadir variable",
    removeVar: "Quitar",
    w_lsfg_wined3d: "Forzar OpenGL NO es compatible con Lossless Scaling Frame Generation.",
    w_lsfg_mangohud: "MangoHud con Lossless Scaling: lsfg-vk recomienda desactivar otras capas de Vulkan.",
    w_empty_mako: "MAKO está activado pero el perfil está vacío.",
    w_empty_lsfg: "lsfg-vk está activado pero el perfil está vacío.",
    w_empty_prefix: "El prefijo está activado pero no hay carpeta elegida.",
    w_mako_lsfg: "MAKO y lsfg-vk son incompatibles: solo se usa MAKO.",
    w_helixsr_fsr4: "HelixSR y FSR4 son incompatibles: solo se usa HelixSR.",
    w_empty_dll: "Las DLL están activadas pero el valor está vacío.",
    w_custom_invalid: "Nombre de variable no válido: ",
    w_custom_reserved: "Nombre reservado por otra opción: ",
    w_custom_duplicate: "Variable repetida: ",
    credits: "Créditos",
    author: "Autor",
  },
  en: {
    preview: "Launch options",
    nothingPreview: "(nothing selected)",
    copy: "Copy to clipboard",
    copied: "Copied",
    copyFailed: "Couldn't copy",
    nothing: "Nothing selected",
    reset: "Reset all",
    resetAsk: "Reset every option?",
    yes: "Reset",
    cancel: "Cancel",
    frames: "FG/Upscalers",
    mako: "MAKO",
    makoHint: "Adds MAKO_PROFILE and the mako-launch wrapper.",
    lsfg: "Lossless Scaling (lsfg-vk)",
    lsfgHint: "With the Decky plugin the profile must be decky-lsfg-vk.",
    profile: "Profile",
    fsr4: "FSR4 (latest)",
    fsr4Hint: "Uses the latest version of GE-Proton / proton-cachyos.",
    fsr4Indicator: "FSR 4 indicator",
    helixsr: "HelixSR upscaler",
    helixsrHint: "Adds PROTON_USE_OPTISCALER and its config. Not compatible with FSR4.",
    helixsrFound: "DLLs found (in %dir%)",
    helixsrMissing: "DLLs not found",
    helixsrDownload: "Download and generate DLLs",
    helixsrCopy: "Copy DLLs to the game",
    helixsrCopied: "DLLs copied to the game",
    helixsrCopyFailed: "Could not copy the DLLs",
    helixsrDownloading: "Downloading HelixSR…",
    helixsrDone: "HelixSR downloaded",
    helixsrFailed: "Could not download HelixSR",
    cleaning: "Cleaning",
    cleanScan: "Look for leftover files",
    cleanPrefixes: "Prefixes and shaders of games that are gone",
    cleanGrids: "Unused images",
    cleanNothing: "Nothing to clean",
    cleanDelete: "Delete selected",
    cleanAsk: "Delete %n% items? This can't be undone.",
    cleanDone: "Deleted: %n%",
    cleanFailed: "Could not delete: %n%",
    helixsrHeavy: "Heavy task: you can follow it in Tasks (Select in the Invasor panel)",
    helixsrGameRunning: "A game is running: close it to download HelixSR, it is a heavy task",
    mangohud: "MangoHud",
    mangohudHint: "With any MangoHud option, the mangohud command is added before %command%.",
    fpsLimit: "Limit FPS",
    fps: "FPS",
    showInfo: "Show API and FPS",
    graphics: "Graphics",
    wined3d: "Force OpenGL (wined3d)",
    zink: "Zink (OpenGL over Vulkan)",
    hdr: "HDR",
    noD3d11: "No Direct3D 11",
    noD3d10: "No Direct3D 10",
    dxvkD3d8: "DXVK for Direct3D 8",
    proton: "Proton",
    wow64: "32-bit compatibility",
    largeAddressAware: "Large address aware",
    noEsync: "No esync",
    noFsync: "No fsync",
    prefix: "Prefix (STEAM_COMPAT_DATA_PATH)",
    chooseFolder: "Choose folder",
    chooseFolderMsg: "Choose the Proton prefix",
    chooseThis: "Choose this folder",
    chooseFile: "Choose a file to add to Steam",
    chooseFileMsg: "Choose the file to add to Steam",
    addToSteam: "Add to Steam",
    sentToSteam: "Sent to Steam: confirm in its dialog",
    addFailed: "Couldn't add it",
    gameNone: "Select a game to see its information",
    gameCopyValue: "Press to copy",
    gameKindSteam: "Steam game",
    gameKindShortcut: "Non-Steam shortcut",
    gg_general: "General",
    gg_install: "Installation",
    gg_play: "Play",
    gg_compat: "Compatibility",
    gg_shortcut: "Shortcut",
    gg_links: "Links",
    gk_name: "Name",
    gk_appid: "AppID",
    gk_kind: "Type",
    gk_library: "Library",
    gk_folder: "Folder",
    gk_size: "Size on disk",
    gk_state: "State",
    gk_build: "Build",
    gk_target_build: "Target build",
    gk_updated: "Last updated",
    gk_autoupdate: "Updates",
    gk_language: "Language",
    gk_pending: "Left to download",
    gk_last_played: "Last played",
    gk_playtime: "Play time",
    gk_playtime_2wks: "Last two weeks",
    gk_launch_options: "Launch options",
    gk_resolution: "Forced resolution",
    gk_tool: "Compatibility tool",
    gk_prefix: "Prefix",
    gk_prefix_override: "Prefix (launch options)",
    gk_exe: "Executable",
    gk_start_dir: "Start directory",
    gk_icon: "Icon",
    gk_tags: "Tags",
    gk_store: "Store",
    gk_steamdb: "SteamDB",
    st_installed: "Installed",
    st_update_required: "Update required",
    st_updating: "Updating",
    st_other: "Other",
    au_0: "Always up to date",
    au_1: "Only on launch",
    au_2: "High priority",
    unit_h: "h",
    unit_min: "min",
    alreadyInSteam: "Already in Steam",
    addedToSteam: "Added to Steam",
    notAddedInTime: "Not added: is Steam open and the dialog confirmed?",
    unreadable: "Can't read",
    environment: "Environment",
    dll: "DLL overrides (WINEDLLOVERRIDES)",
    dllValue: "Value",
    steamDeck: "Not a Steam Deck",
    customVars: "Custom variables",
    varName: "Name",
    varValue: "Value",
    addVar: "Add variable",
    removeVar: "Remove",
    w_lsfg_wined3d: "Force OpenGL is NOT compatible with Lossless Scaling Frame Generation.",
    w_lsfg_mangohud: "MangoHud with Lossless Scaling: lsfg-vk recommends turning off other Vulkan layers.",
    w_empty_mako: "MAKO is on but its profile is empty.",
    w_empty_lsfg: "lsfg-vk is on but its profile is empty.",
    w_empty_prefix: "The prefix is on but no folder is chosen.",
    w_mako_lsfg: "MAKO and lsfg-vk are not compatible: only MAKO is used.",
    w_helixsr_fsr4: "HelixSR and FSR4 are not compatible: only HelixSR is used.",
    w_empty_dll: "DLL overrides are on but the value is empty.",
    w_custom_invalid: "Invalid variable name: ",
    w_custom_reserved: "Name reserved by another option: ",
    w_custom_duplicate: "Duplicate variable: ",
    credits: "Credits",
    author: "Author",
  },
};
type Strings = typeof T.es;

function defaults() {
  return {
    mako: { on: false, profile: "default" },
    lsfg: { on: false, profile: "default" },
    fsr4: { on: false },
    fsr4Indicator: false,
    helixsr: { on: false },
    fpsLimit: { on: false, value: 30 },
    showInfo: false,
    wined3d: false, zink: false, hdr: false, noD3d11: false, noD3d10: false, dxvkD3d8: false,
    wow64: false, noEsync: false, noFsync: false, largeAddressAware: false,
    prefix: { on: false, path: "" },
    dllOverrides: { on: false, value: "dxgi.dll=n,b" },
    steamDeck: false,
    custom: [] as Custom[],
  };
}
type State = ReturnType<typeof defaults>;

const join = (dir: string, name: string) => (dir === "/" ? "/" : dir + "/") + name;

// Steam's CEF may not give navigator.clipboard to this page: fall back to execCommand.
async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    try {
      return document.execCommand("copy");
    } catch {
      return false;
    } finally {
      area.remove();
    }
  }
}

interface BrowseOpts {
  title: string;
  /** List files too, and pick one by pressing it (else a folder is picked with "choose this folder"). */
  files: boolean;
  start?: string;
  onPick(path: string): void;
}

// File/folder browser in a big window: ".." goes up and any folder can be entered.
// ctx.openWindow returns null (and tells the user why) where there's no room.
function openBrowser(ctx: ModuleCtx, t: Strings, o: BrowseOpts): WindowHandle | null {
  let win: WindowHandle | null = null;
  const pick = (path: string) => {
    o.onPick(path);
    win?.close();
  };
  const spec: WindowSpec = {
    title: o.title,
    async render(box, wctx) {
      async function show(path?: string) {
        const dir = await wctx.call<Dir>("browse", { ...(path ? { path } : {}), files: o.files, home: o.files });
        const items: HTMLElement[] = [ui.info(dir.path)];
        if (!o.files) items.push(ui.button({ label: t.chooseThis, onClick: () => pick(dir.path) }));
        if (dir.error) {
          const err = ui.info(`${t.unreadable}: ${dir.error}`);
          err.style.color = "#e5534b";
          items.push(err);
        }
        const go = (p: string) => () => void show(p);
        if (dir.parent) items.push(ui.button({ label: "..", onClick: go(dir.parent) }));
        for (const d of dir.dirs) items.push(ui.button({ label: d.label, onClick: go(join(dir.path, d.name)) }));
        for (const f of dir.files) {
          items.push(ui.button({ label: f.name, onClick: () => pick(join(dir.path, f.name)) }));
        }
        box.replaceChildren(...items);
      }
      await show(o.start);
    },
    onClose: () => (win = null),
  };
  win = ctx.openWindow(spec);
  return win;
}

async function launcher(el: HTMLElement, ctx: ModuleCtx, t: Strings) {
  let state: State = defaults();
  let command = "";
  let seq = 0;

  const preview = ui.info("");
  const warnings = document.createElement("div");
  const copy = ui.button({ label: t.copy, onClick: () => void doCopy() });
  const customBox = document.createElement("div");
  // Controls to put back to their default on Reset all.
  // Each one with a function that reads its default from the (fresh) state.
  const controls: { set(v: never): void; get: () => unknown }[] = [];
  const track = <C extends { set(v: never): void }>(c: C, get: () => unknown) => (controls.push({ set: (v) => c.set(v), get }), c);

  async function refresh() {
    const mine = ++seq;
    const built = await ctx.call<Built>("build", { state });
    if (mine !== seq) return;
    command = built.command;
    preview.textContent = command || t.nothingPreview;
    warnings.replaceChildren(
      ...built.warnings.map((w) => {
        const p = ui.info(t[`w_${w.code}` as keyof Strings] + (w.name ?? ""));
        p.style.color = "#e5534b";
        return p;
      }),
    );
  }
  const change = () => (sync(), void refresh());

  async function doCopy() {
    if (!command) return ctx.toast(t.nothing, "error");
    if (await copyText(command)) ctx.toast(t.copied, "ok");
    else ctx.toast(t.copyFailed, "error");
  }

  const toggle = (label: string, get: () => boolean, set: (v: boolean) => void, hint?: string) =>
    track(ui.toggle({ label, value: get(), hint, onChange: (v) => (set(v), change()) }), get);
  const text = (label: string, get: () => string, set: (v: string) => void) =>
    track(ui.text({ label, value: get(), onChange: (v) => (set(v), change()) }), get);

  const prefixLabel = ui.info("");
  const paintPrefix = () => (prefixLabel.textContent = state.prefix.path);
  // openWindow returns null (and tells the user why) where there's no room, e.g. the Quick Access in a game.
  const chooseFolder = ui.button({
    label: t.chooseFolder,
    onClick: () =>
      void openBrowser(ctx, t, {
        title: t.chooseFolderMsg,
        files: false,
        start: state.prefix.path || undefined,
        onPick: (path) => {
          state.prefix.path = path;
          paintPrefix();
          change();
        },
      }),
  });

  function drawCustom() {
    const rows = state.custom.map((v, i) =>
      ui.section(v.name || `#${i + 1}`, [
        ui.text({ label: t.varName, value: v.name, onChange: (n) => ((v.name = n), change()) }),
        ui.text({ label: t.varValue, value: v.value, onChange: (n) => ((v.value = n), change()) }),
        ui.button({
          label: t.removeVar,
          onClick: () => {
            state.custom.splice(i, 1);
            drawCustom();
            change();
          },
        }),
      ]),
    );
    customBox.replaceChildren(
      ...rows,
      ui.button({
        label: t.addVar,
        onClick: () => {
          state.custom.push({ name: "", value: "" });
          drawCustom();
          change();
        },
      }),
    );
  }

  const reset = ui.button({
    label: t.reset,
    onClick: async () => {
      if (!(await ui.confirm(t.resetAsk, { ok: t.yes, cancel: t.cancel }))) return;
      state = defaults();
      controls.forEach((c) => c.set(c.get() as never));
      paintPrefix();
      drawCustom();
      change();
    },
  });

  const s = () => state;
  // Fields that only show while their option is on (see sync).
  const makoProfile = text(t.profile, () => s().mako.profile, (v) => (s().mako.profile = v));
  const lsfgProfile = text(t.profile, () => s().lsfg.profile, (v) => (s().lsfg.profile = v));
  const fsr4Indicator = toggle(t.fsr4Indicator, () => s().fsr4Indicator, (v) => (s().fsr4Indicator = v));
  const helixsrStatus = ui.info("");
  let helixsrFound = false;
  let helixsrCopyNeeded = false;
  let helixsrBusy = false;
  async function paintHelixsr() {
    if (helixsrBusy) return; // the download repaints when it ends
    const appid = currentGame(ctx.game())?.game.appid ?? "";
    try {
      const st = await ctx.call<{ found: boolean; dir: string; game: { copy: boolean } | null }>(
        "helixsr_status",
        appid ? { appid } : {},
      );
      helixsrFound = st.found;
      helixsrCopyNeeded = !!st.game?.copy;
      helixsrStatus.textContent = st.found ? t.helixsrFound.replace("%dir%", st.dir) : t.helixsrMissing;
    } catch {
      helixsrFound = false;
      helixsrCopyNeeded = false;
      helixsrStatus.textContent = t.helixsrMissing;
    }
    sync();
  }
  const helixsrDownload = ui.button({
    label: t.helixsrDownload,
    onClick: async () => {
      if (helixsrBusy) return;
      // Heavy: not while a game is running (the backend refuses too).
      if (ctx.game().running) return ctx.toast(t.helixsrGameRunning, "error");
      helixsrBusy = true;
      helixsrDownload.style.display = "none";
      helixsrStatus.textContent = `${t.helixsrDownloading} ${t.helixsrHeavy}`;
      ctx.toast(t.helixsrHeavy, "ok");
      try {
        await ctx.call("helixsr_download");
        ctx.toast(t.helixsrDone, "ok");
      } catch {
        ctx.toast(t.helixsrFailed, "error");
      } finally {
        helixsrBusy = false;
      }
      await paintHelixsr();
    },
  });
  const helixsrCopy = ui.button({
    label: t.helixsrCopy,
    onClick: async () => {
      const appid = currentGame(ctx.game())?.game.appid ?? "";
      try {
        await ctx.call("helixsr_copy", { appid });
        ctx.toast(t.helixsrCopied, "ok");
      } catch {
        ctx.toast(t.helixsrCopyFailed, "error");
      }
      await paintHelixsr();
    },
  });
  refreshHelixsr = paintHelixsr;
  const fpsValue = track(
    ui.number({
      label: t.fps, value: 30, min: 0, max: 240, step: 1,
      onChange: (v) => ((s().fpsLimit.value = v), change()),
    }),
    () => s().fpsLimit.value,
  );
  const dllValue = text(t.dllValue, () => s().dllOverrides.value, (v) => (s().dllOverrides.value = v));
  function sync() {
    // display:none also takes them out of the gamepad's navigation.
    const dep = (c: HTMLElement, on: boolean) => (c.style.display = on ? "" : "none");
    dep(makoProfile, s().mako.on);
    dep(lsfgProfile, s().lsfg.on);
    dep(fsr4Indicator, s().fsr4.on);
    dep(helixsrStatus, s().helixsr.on);
    dep(helixsrDownload, s().helixsr.on && !helixsrFound && !helixsrBusy);
    dep(helixsrCopy, s().helixsr.on && helixsrFound && helixsrCopyNeeded);
    dep(fpsValue, s().fpsLimit.on);
    dep(chooseFolder, s().prefix.on);
    dep(dllValue, s().dllOverrides.on);
  }

  // FSR4 and HelixSR exclude each other: picking one turns the other off.
  const fsr4Toggle = toggle(t.fsr4, () => s().fsr4.on, (v) => {
    s().fsr4.on = v;
    if (!v) {
      s().fsr4Indicator = false;
      fsr4Indicator.set(false);
    } else if (s().helixsr.on) {
      s().helixsr.on = false;
      helixsrToggle.set(false);
    }
  }, t.fsr4Hint);
  const helixsrToggle = toggle(t.helixsr, () => s().helixsr.on, (v) => {
    s().helixsr.on = v;
    if (v) {
      s().fsr4.on = false;
      s().fsr4Indicator = false;
      fsr4Toggle.set(false);
      fsr4Indicator.set(false);
      void paintHelixsr();
    }
  }, t.helixsrHint);

  // MAKO and lsfg-vk exclude each other: picking one turns the other off.
  const makoToggle = toggle(t.mako, () => s().mako.on, (v) => {
    s().mako.on = v;
    if (v && s().lsfg.on) {
      s().lsfg.on = false;
      lsfgToggle.set(false);
    }
  }, t.makoHint);
  const lsfgToggle = toggle(t.lsfg, () => s().lsfg.on, (v) => {
    s().lsfg.on = v;
    if (v && s().mako.on) {
      s().mako.on = false;
      makoToggle.set(false);
    }
  }, t.lsfgHint);

  const sections = [
    ui.section(t.frames, [
      makoToggle,
      makoProfile,
      ui.separator(),
      lsfgToggle,
      lsfgProfile,
      ui.separator(),
      fsr4Toggle,
      fsr4Indicator,
      ui.separator(),
      helixsrToggle,
      helixsrStatus,
      helixsrDownload,
      helixsrCopy,
    ], { open: false }),
    ui.section(t.mangohud, [
      toggle(t.fpsLimit, () => s().fpsLimit.on, (v) => (s().fpsLimit.on = v), t.mangohudHint),
      fpsValue,
      toggle(t.showInfo, () => s().showInfo, (v) => (s().showInfo = v)),
    ], { open: false }),
    ui.section(t.graphics, [
      toggle(t.wined3d, () => s().wined3d, (v) => (s().wined3d = v)),
      toggle(t.zink, () => s().zink, (v) => (s().zink = v)),
      toggle(t.hdr, () => s().hdr, (v) => (s().hdr = v)),
      toggle(t.noD3d11, () => s().noD3d11, (v) => (s().noD3d11 = v)),
      toggle(t.noD3d10, () => s().noD3d10, (v) => (s().noD3d10 = v)),
      toggle(t.dxvkD3d8, () => s().dxvkD3d8, (v) => (s().dxvkD3d8 = v)),
    ], { open: false }),
    ui.section(t.proton, [
      toggle(t.wow64, () => s().wow64, (v) => (s().wow64 = v)),
      toggle(t.largeAddressAware, () => s().largeAddressAware, (v) => (s().largeAddressAware = v)),
      toggle(t.noEsync, () => s().noEsync, (v) => (s().noEsync = v)),
      toggle(t.noFsync, () => s().noFsync, (v) => (s().noFsync = v)),
      toggle(t.prefix, () => s().prefix.on, (v) => (s().prefix.on = v)),
      chooseFolder,
      prefixLabel,
    ], { open: false }),
    ui.section(t.environment, [
      toggle(t.dll, () => s().dllOverrides.on, (v) => (s().dllOverrides.on = v)),
      dllValue,
      ui.separator(),
      toggle(t.steamDeck, () => s().steamDeck, (v) => (s().steamDeck = v)),
    ], { open: false }),
    ui.section(t.customVars, [customBox], { open: false }),
  ];

  drawCustom();
  paintPrefix();
  sync();
  void paintHelixsr();
  el.append(preview, copy, warnings, ...sections, reset);
  await refresh();
}

function addTo(el: HTMLElement, ctx: ModuleCtx, t: Strings) {
  let file = "";
  const path = ui.info("");
  // Bumped on every send and every new file, so an older wait for Steam's dialog stops.
  let run = 0;
  const add = ui.button({
    label: t.addToSteam,
    onClick: async () => {
      const mine = ++run;
      const target = file;
      try {
        const sent = await ctx.call<{ already: boolean }>("add_to_steam", { path: target });
        if (sent.already) return ctx.toast(t.alreadyInSteam, "ok");
        ctx.toast(t.sentToSteam, "ok");
        // Steam adds it only after the user confirms its dialog: wait for it to show up in shortcuts.vdf.
        for (let waited = 0; waited < 60_000 && mine === run; waited += 1500) {
          await new Promise((r) => setTimeout(r, 1500));
          if (mine === run && (await ctx.call<boolean>("is_added", { path: target }))) {
            return ctx.toast(t.addedToSteam, "ok");
          }
        }
        if (mine === run) ctx.toast(t.notAddedInTime, "error");
      } catch (e) {
        ctx.toast(`${t.addFailed}: ${e instanceof Error ? e.message : e}`, "error");
      }
    },
  });
  // The path and the button only show once a file is chosen.
  const paint = () => {
    path.textContent = file;
    path.style.display = add.style.display = file ? "" : "none";
  };
  const choose = ui.button({
    label: t.chooseFile,
    onClick: () =>
      void openBrowser(ctx, t, {
        title: t.chooseFileMsg,
        files: true,
        onPick: (p) => {
          run++;
          file = p;
          paint();
        },
      }),
  });
  paint();
  el.append(choose, path, add);
}

interface CleanItem { path: string; appid: string; name: string; size: number; kind?: string }
interface CleanScan { prefixes: CleanItem[]; grids: CleanItem[] }

const formatSize = (n: number) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${(n / 1e6).toFixed(1)} MB`);

// Cleaning: orphan compatdata/shadercache and unused grid images, picked one by one (all marked) and deleted.
function cleaning(el: HTMLElement, ctx: ModuleCtx, t: Strings) {
  const list = document.createElement("div");
  const picked = new Set<string>();
  let busy = false;

  const group = (title: string, items: CleanItem[], label: (i: CleanItem) => string) =>
    items.length
      ? [
          ui.info(title),
          ...items.map((i) => {
            picked.add(i.path);
            return ui.toggle({
              label: `${label(i)} (${formatSize(i.size)})`,
              value: true,
              onChange: (v) => void (v ? picked.add(i.path) : picked.delete(i.path)),
            });
          }),
        ]
      : [];

  async function scan() {
    if (busy) return;
    busy = true;
    try {
      const found = await ctx.call<CleanScan>("clean_scan");
      picked.clear();
      const rows = [
        ...group(t.cleanPrefixes, found.prefixes, (i) => `${i.appid} - ${i.name || "¿?"} · ${i.kind}`),
        ...group(t.cleanGrids, found.grids, (i) => `${i.path.split("/").pop() ?? i.path}${i.name ? ` - ${i.name}` : ""}`),
      ];
      if (!rows.length) return list.replaceChildren(ui.info(t.cleanNothing));
      list.replaceChildren(
        ...rows,
        ui.button({
          label: t.cleanDelete,
          onClick: async () => {
            if (busy || !picked.size) return;
            const n = String(picked.size);
            if (!(await ui.confirm(t.cleanAsk.replace("%n%", n), { ok: t.cleanDelete, cancel: t.cancel }))) return;
            busy = true;
            try {
              const out = await ctx.call<{ deleted: string[]; failed: string[] }>("clean_delete", { paths: [...picked] });
              ctx.toast(t.cleanDone.replace("%n%", String(out.deleted.length)), "ok");
              if (out.failed.length) ctx.toast(t.cleanFailed.replace("%n%", String(out.failed.length)), "error");
            } catch {
              ctx.toast(t.cleanFailed.replace("%n%", n), "error");
            } finally {
              busy = false;
            }
            await scan();
          },
        }),
      );
    } catch {
      list.replaceChildren(ui.info(t.cleanNothing));
    } finally {
      busy = false;
    }
  }

  el.append(ui.button({ label: t.cleanScan, onClick: () => void scan() }), list);
}

interface GameRow { key: string; value: string | number; type: string }
interface GameInfo { appid: string; name: string | null; kind: string; groups: { id: string; rows: GameRow[] }[] }

function gameValue(r: GameRow, t: Strings, lang: Lang): string {
  const text = t as Record<string, string>;
  const n = Number(r.value);
  switch (r.type) {
    case "bytes":
      return n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${(n / 1e6).toFixed(1)} MB`;
    case "timestamp":
      return new Date(n * 1000).toLocaleString(lang === "es" ? "es-ES" : "en-GB");
    case "minutes": {
      const h = Math.floor(n / 60);
      return h ? `${h} ${t.unit_h} ${n % 60} ${t.unit_min}` : `${n} ${t.unit_min}`;
    }
    case "state": {
      const parts = [];
      if (n & 4) parts.push(t.st_installed);
      if (n & 2) parts.push(t.st_update_required);
      if (n & (256 | 1024)) parts.push(t.st_updating);
      return parts.length ? parts.join(", ") : `${t.st_other} (${n})`;
    }
    case "autoupdate":
      return text[`au_${r.value}`] ?? String(r.value);
    case "text":
      return r.key === "kind" ? (r.value === "shortcut" ? t.gameKindShortcut : t.gameKindSteam) : String(r.value);
    default:
      return String(r.value);
  }
}

async function copyToast(ctx: ModuleCtx, t: Strings, text: string) {
  const ok = await copyText(text);
  ctx.toast(ok ? t.copied : t.copyFailed, ok ? "ok" : "error");
}

// Every row is a navigation stop (so the gamepad can scroll through them): A copies its value.
function gameRow(ctx: ModuleCtx, t: Strings, lang: Lang, r: GameRow): HTMLElement {
  const text = gameValue(r, t, lang);
  const el = document.createElement("div");
  el.className = "ctl";
  el.dataset.nav = "";
  el.dataset.hint = t.gameCopyValue;
  el.style.cssText = "display:flex;flex-wrap:wrap;gap:4px 16px;justify-content:space-between;align-items:baseline";
  const label = document.createElement("span");
  label.className = "ctl-label";
  label.style.opacity = "0.7";
  label.textContent = (t as Record<string, string>)[`gk_${r.key}`] ?? r.key;
  const value = document.createElement("span");
  const mono = r.type === "path" || r.type === "code" || r.type === "url";
  value.style.cssText = `text-align:right;margin-left:auto;max-width:100%;word-break:break-all;${mono ? "font-family:monospace;font-size:0.9em" : ""}`;
  value.textContent = text;
  el.append(label, value);
  el.addEventListener("click", () => void copyToast(ctx, t, String(r.value)));
  return el;
}

// The Game tab: what Steam's files say about the current game. Returns the function that re-reads it.
function gameTab(el: HTMLElement, ctx: ModuleCtx, t: Strings, lang: Lang): () => Promise<void> {
  const body = document.createElement("div");
  async function refresh() {
    const current = currentGame(ctx.game());
    const appid = current?.game.appid ?? "";
    if (!appid) return void body.replaceChildren(ui.info(t.gameNone));
    const info = await ctx.call<GameInfo>("game_info", { appid });
    const title = document.createElement("div");
    title.style.cssText = "font-size:1.35em;font-weight:600;margin:4px 0 2px;word-break:break-word";
    title.textContent = info.name ?? info.appid;
    const kind = document.createElement("span");
    kind.textContent = info.kind === "shortcut" ? t.gameKindShortcut : t.gameKindSteam;
    kind.style.cssText = "display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.8em;margin-bottom:8px;background:rgba(var(--accent-rgb),.15)";
    const groups = info.groups.map((g) =>
      ui.section(
        (t as Record<string, string>)[`gg_${g.id}`] ?? g.id,
        // The name and the type are already in the header.
        g.rows.filter((r) => !(g.id === "general" && (r.key === "name" || r.key === "kind"))).map((r) => gameRow(ctx, t, lang, r)),
        { open: false },
      ),
    );
    body.replaceChildren(title, kind, ...groups);
  }
  el.append(body);
  void refresh();
  return refresh;
}

function credits(el: HTMLElement, t: Strings) {
  el.append(
    ui.info(`${t.author}: FranjeGueje`),
  );
}

let refreshGame: (() => Promise<void>) | null = null;
let refreshHelixsr: (() => Promise<void>) | null = null;

export default defineModule({
  tabsAlign: "justify",
  onGameChange: () => (void refreshGame?.(), void refreshHelixsr?.()),
  tabs: [
    {
      label: "Lanzador",
      async render(el, ctx) {
        const lang = await ctx.call<Lang>("language");
        await launcher(el, ctx, T[lang] ?? T.en);
      },
    },
    {
      label: "Game",
      async render(el, ctx) {
        const lang = await ctx.call<Lang>("language");
        refreshGame = gameTab(el, ctx, T[lang] ?? T.en, lang);
      },
      onShow: () => void refreshGame?.(),
    },
    {
      label: "Steam",
      async render(el, ctx) {
        const lang = await ctx.call<Lang>("language");
        const t = T[lang] ?? T.en;
        addTo(el, ctx, t);
        const clean = document.createElement("div");
        cleaning(clean, ctx, t);
        el.append(ui.separator(), ui.section(t.cleaning, [clean], { open: false }));
      },
    },
    {
      label: "Créditos",
      async render(el, ctx) {
        const lang = await ctx.call<Lang>("language");
        credits(el, T[lang] ?? T.en);
      },
    },
  ],
});
