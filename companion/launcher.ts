import { ui, type ModuleCtx } from "invasor";
import type { Strings } from "./texts";

interface Warning { code: string; name?: string }
interface Built { command: string; warnings: Warning[] }
interface Custom { name: string; value: string }
/** The profiles of MAKO and lsfg-vk, as their conf.toml lists them (see backend.profiles). */
interface Profiles { mako: string[]; lsfg: string[] }

function defaults() {
  return {
    mako: { on: false, profile: "default" },
    lsfg: { on: false, profile: "default" },
    fsr4: { on: false },
    fsr4Indicator: false,
    fpsLimit: { on: false, value: 30 },
    showInfo: false,
    wined3d: false, zink: false, hdr: false, noD3d11: false, noD3d10: false, dxvkD3d8: false,
    wow64: false, noEsync: false, noFsync: false, largeAddressAware: false, protonLog: false,
    prefix: { on: false, path: "" },
    dllOverrides: { on: false, value: "dxgi.dll=n,b" },
    steamDeck: false,
    custom: [] as Custom[],
  };
}
type State = ReturnType<typeof defaults>;

/** Copies text and says whether it worked. */
export async function copyToast(ctx: ModuleCtx, t: Strings, text: string) {
  const ok = await ctx.copy(text);
  ctx.toast(ok ? t.copied : t.copyFailed, ok ? "ok" : "error");
}

export async function launcher(el: HTMLElement, ctx: ModuleCtx, t: Strings) {
  const profiles = await ctx.call<Profiles>("profiles").catch((): Profiles => ({ mako: [], lsfg: [] }));
  // The profile an option starts with: "default" when the program has it (or when there's no list), else its first.
  const firstProfile = (names: string[]) => (names.length && !names.includes("default") ? names[0] : "default");
  function fresh(): State {
    const fresh = defaults();
    fresh.mako.profile = firstProfile(profiles.mako);
    fresh.lsfg.profile = firstProfile(profiles.lsfg);
    return fresh;
  }
  let state: State = fresh();
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
    await copyToast(ctx, t, command);
  }

  const toggle = (label: string, get: () => boolean, set: (v: boolean) => void, hint?: string) =>
    track(ui.toggle({ label, value: get(), hint, onChange: (v) => (set(v), change()) }), get);
  const text = (label: string, get: () => string, set: (v: string) => void) =>
    track(ui.text({ label, value: get(), onChange: (v) => (set(v), change()) }), get);

  const prefixLabel = ui.info("");
  const paintPrefix = () => (prefixLabel.textContent = state.prefix.path);
  // pickPath answers null (and tells the user why) where there's no room, e.g. the Quick Access in a game.
  const chooseFolder = ui.button({
    label: t.chooseFolder,
    onClick: async () => {
      const start = state.prefix.path || (await ctx.call<string | null>("compatdata_dir")) || undefined;
      const path = await ctx.pickPath({ title: t.chooseFolderMsg, start, chooseLabel: t.chooseThis });
      if (path) {
        state.prefix.path = path;
        paintPrefix();
        change();
      }
    },
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
      state = fresh();
      controls.forEach((c) => c.set(c.get() as never));
      paintPrefix();
      drawCustom();
      change();
    },
  });

  const s = () => state;
  // Fields that only show while their option is on (see sync).
  // ←→ picks one of the installed profiles; with none found (not installed, or its file can't be read), it's typed.
  const profile = (names: string[], get: () => string, set: (v: string) => void) =>
    names.length
      ? track(ui.select({
        label: t.profile, value: get(), options: names.map((n) => ({ value: n, label: n })),
        onChange: (v) => (set(String(v)), change()),
      }), get)
      : text(t.profile, get, set);
  const makoProfile = profile(profiles.mako, () => s().mako.profile, (v) => (s().mako.profile = v));
  const lsfgProfile = profile(profiles.lsfg, () => s().lsfg.profile, (v) => (s().lsfg.profile = v));
  const fsr4Indicator = toggle(t.fsr4Indicator, () => s().fsr4Indicator, (v) => (s().fsr4Indicator = v));
  const fpsValue = track(
    ui.number({
      label: t.fps, value: s().fpsLimit.value, min: 0, max: 240, step: 1,
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
    dep(fpsValue, s().fpsLimit.on);
    dep(chooseFolder, s().prefix.on);
    dep(dllValue, s().dllOverrides.on);
  }

  const fsr4Toggle = toggle(t.fsr4, () => s().fsr4.on, (v) => {
    s().fsr4.on = v;
    if (!v) {
      s().fsr4Indicator = false;
      fsr4Indicator.set(false);
    }
  }, t.fsr4Hint);

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
      ui.info(t.helixsrMoved),
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
      toggle(t.protonLog, () => s().protonLog, (v) => (s().protonLog = v), t.protonLogHint),
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
  el.append(preview, copy, warnings, ...sections, reset);
  await refresh();
}
