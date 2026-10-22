import { ui, type ModuleCtx, type WindowHandle, type WindowSpec } from "invasor";
import type { Strings } from "./texts";

interface Dir {
  path: string;
  parent: string | null;
  dirs: { name: string; label: string }[];
  files: { name: string }[];
  error: string | null;
}

const join = (dir: string, name: string) => (dir === "/" ? "/" : dir + "/") + name;

// Steam's CEF may not give navigator.clipboard to this page: fall back to execCommand.
export async function copyText(text: string): Promise<boolean> {
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
export function openBrowser(ctx: ModuleCtx, t: Strings, o: BrowseOpts): WindowHandle | null {
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
