// What the coach took from a workout's feedback: "Feedback saved." at once, then, once the background job that
// reads it ends (two minutes at most), its summary in place of those words, if it has one.
import { useCallback, useEffect, useRef, useState } from "react";
import { waitForJob } from "./api";

export function useFeedbackNote() {
  /** Null until feedback is saved. */
  const [noted, setNoted] = useState<string | null>(null);
  const live = useRef(true);
  useEffect(() => () => { live.current = false; }, []);

  /** The feedback went in: follow its job (`id`), or with none, say it's saved. */
  const saved = useCallback(async (id?: number | null) => {
    if (!id) { setNoted("Feedback saved."); return; }
    setNoted("Feedback saved. Noting what that tells me…");
    let end;
    try {
      end = await waitForJob(id, { every: 2000, within: 120_000, live: () => live.current });
    } catch {
      end = { state: "failed" as const };
    }
    if (!live.current) return;
    const summary = end.state === "done" ? (end.result as { summary?: unknown } | null)?.summary : null;
    setNoted(typeof summary === "string" && summary.trim() ? summary : "Feedback saved.");
  }, []);

  return { noted, saved };
}
