import { currentGame, defineModule, ui, type ModuleCtx } from "invasor";
import { copyToast, launcher } from "./launcher";
import { T, type Lang, type Strings } from "./texts";

function addTo(el: HTMLElement, ctx: ModuleCtx, t: Strings) {
  let file = "";
  const path = ui.info("");
  const add = ui.button({
    label: t.addToSteam,
    onClick: async () => {
      try {
        const out = await ctx.call<{ appid: number; existed: boolean }>("add_to_steam", { path: file });
        ctx.toast(out.existed ? t.alreadyInSteam : t.addedToSteam, "ok");
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
    onClick: async () => {
      const picked = await ctx.pickPath({ title: t.chooseFileMsg, files: true });
      if (picked) {
        file = picked;
        paint();
      }
    },
  });
  paint();
  el.append(choose, path, add);
}

interface CleanItem { path: string; appid: string; name: string; size: number; kind?: string }
interface CleanScan { prefixes: CleanItem[]; grids: CleanItem[] }

const locale = (lang: Lang) => (lang === "es" ? "es-ES" : "en-GB");
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
      return formatSize(n);
    case "timestamp":
      return new Date(n * 1000).toLocaleString(locale(lang));
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

interface Enriched {
  steam: { rating: string; percent: number; total: number; steamdb: number | null } | null;
  metacritic: { score: number; url: string | null } | null;
  protondb: { tier: string; total: number } | null;
  match: { appid: string; name: string } | null;
  protondb_url: string;
  hltb_url: string;
}

// Bumped on every refresh of the Game tab, so a slow answer for the previous game is dropped.
let enrichSeq = 0;

// The enrichers: a button under the title that asks for the scores and the pages to look further.
function enrichers(ctx: ModuleCtx, t: Strings, lang: Lang, info: GameInfo): HTMLElement {
  const text = t as Record<string, string>;
  const box = document.createElement("div");
  const num = (n: number, digits = 0) => n.toLocaleString(locale(lang), { maximumFractionDigits: digits });
  const row = (key: string, value: string) => gameRow(ctx, t, lang, { key, value, type: "text" });
  const open = (url: string) => () =>
    void ctx.call("open_page", { url }).catch((e) => ctx.toast(`${t.openFailed}: ${e instanceof Error ? e.message : e}`, "error"));
  const show = async () => {
    const mine = enrichSeq;
    box.replaceChildren(ui.info(t.enrichLoading));
    let e: Enriched;
    try {
      e = await ctx.call<Enriched>("enrich", { appid: info.appid, name: info.name ?? "", shortcut: info.kind === "shortcut" });
    } catch (err) {
      if (mine === enrichSeq) box.replaceChildren(button, ui.info(`${t.enrichFailed}: ${err instanceof Error ? err.message : err}`));
      return;
    }
    if (mine !== enrichSeq) return;
    const rows: HTMLElement[] = [];
    if (e.match) rows.push(row("matched", e.match.name || e.match.appid));
    if (e.steam) {
      const parts = [text[`rv_${e.steam.rating}`] ?? e.steam.rating, `${e.steam.percent} %`, `${num(e.steam.total)} ${t.reviews}`];
      if (e.steam.steamdb !== null) parts.push(`SteamDB ${num(e.steam.steamdb, 1)}`);
      rows.push(row("score_steam", parts.join(" · ")));
    }
    if (e.metacritic) rows.push(row("score_metacritic", String(e.metacritic.score)));
    if (e.protondb) rows.push(row("score_protondb", `${text[`pdb_${e.protondb.tier}`] ?? e.protondb.tier} (${num(e.protondb.total)} ${t.reports})`));
    if (!rows.length) rows.push(ui.info(t.enrichNone));
    box.replaceChildren(
      ...rows,
      ui.button({ label: t.openProtonDb, onClick: open(e.protondb_url) }),
      ui.button({ label: t.openHltb, onClick: open(e.hltb_url) }),
    );
  };
  const button = ui.button({ label: t.enrichers, onClick: () => void show() });
  box.append(button);
  return box;
}

// The Game tab: what Steam's files say about the current game. Returns the function that re-reads it.
function gameTab(el: HTMLElement, ctx: ModuleCtx, t: Strings, lang: Lang): () => Promise<void> {
  const body = document.createElement("div");
  async function refresh() {
    enrichSeq++;
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
    body.replaceChildren(title, kind, enrichers(ctx, t, lang, info), ...groups);
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

// Steam's language, asked once for every tab (English if it can't be told).
let language: Promise<Lang> | null = null;
async function strings(ctx: ModuleCtx): Promise<[Lang, Strings]> {
  language ??= ctx.call<Lang>("language").catch((): Lang => "en");
  const lang = await language;
  return [lang, T[lang] ?? T.en];
}

export default defineModule({
  tabsAlign: "justify",
  onGameChange: () => void refreshGame?.(),
  tabs: [
    {
      label: "Launcher",
      async render(el, ctx) {
        const [, t] = await strings(ctx);
        await launcher(el, ctx, t);
      },
    },
    {
      label: "Game",
      async render(el, ctx) {
        const [lang, t] = await strings(ctx);
        refreshGame = gameTab(el, ctx, t, lang);
      },
      onShow: () => void refreshGame?.(),
    },
    {
      label: "Steam",
      async render(el, ctx) {
        const [, t] = await strings(ctx);
        addTo(el, ctx, t);
        const clean = document.createElement("div");
        cleaning(clean, ctx, t);
        el.append(ui.separator(), ui.section(t.cleaning, [clean], { open: false }));
      },
    },
    {
      label: "Credits",
      async render(el, ctx) {
        const [, t] = await strings(ctx);
        credits(el, t);
      },
    },
  ],
});
