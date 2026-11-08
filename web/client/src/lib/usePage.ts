// Which page shows beside the chat: an address of its own (#logs, #coaches), so a reload keeps it and the
// back button closes it. The Settings drawer and the pickers are moments, not places: they stay out of it.
import { useCallback, useEffect, useState } from "react";

export type Page = "chat" | "logs" | "coaches";
const PAGES: Page[] = ["logs", "coaches"];

function read(): Page {
  const h = window.location.hash.slice(1);
  return (PAGES as string[]).includes(h) ? (h as Page) : "chat";
}

export function usePage() {
  const [page, setPage] = useState<Page>(read);
  useEffect(() => {
    const f = () => setPage(read());
    window.addEventListener("hashchange", f);
    window.addEventListener("popstate", f);
    return () => { window.removeEventListener("hashchange", f); window.removeEventListener("popstate", f); };
  }, []);
  const go = useCallback((p: Page) => {
    if (p === read()) return;
    if (p === "chat") window.history.pushState(null, "", window.location.pathname + window.location.search);
    else window.history.pushState(null, "", `#${p}`);
    setPage(p);
  }, []);
  return [page, go] as const;
}
