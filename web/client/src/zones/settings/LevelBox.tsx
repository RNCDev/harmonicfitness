// The listener's level, picked by the sentence that fits them, as three cards side by side: it sets the
// movements, the doses and how much the coach explains. Novice until one is chosen, as the planning assumes.
// Chosen at once, then saved; put back if refused.
import { useState } from "react";
import { api, ApiError, NotSignedIn, type Level, type LevelState } from "../../lib/api";
import { SAID } from "../../lib/messages";
import { optimistic } from "../../lib/useAction";
import { useResource } from "../../lib/useResource";
import { LevelCards } from "../../ui/LevelCards";
import { Loadable, Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

export function LevelBox() {
  const res = useResource(api.level, SAID.level);
  const state = res.data;
  const setState = (s: LevelState | null) => res.set(() => s);
  const [error, setError] = useState<string | null>(null);

  async function choose(level: Level) {
    if (!state || level === state.level) return;
    setError(await optimistic(state, { ...state, level, set: true }, setState, async () => {
      try {
        await api.setLevel(level);
      } catch (e) {
        // a clash says what happened in the server's words; anything else in ours
        throw e instanceof NotSignedIn || (e instanceof ApiError && e.status === 409) ? e : new Error("not saved");
      }
    }, SAID.levelNotSaved));
  }

  return (
    <Section id="cx-level" title="Your level">
      <Loadable value={state} error={res.error} onRetry={res.reload} what="your level" room={150}>
        {(s) => (
          <>
            <LevelCards choices={s.choices} value={s.level} onChoose={(l) => void choose(l)} labelledBy="cx-level-h" />
            <p className="cx-s">
              {!s.set
                ? "Not chosen yet, so workouts are planned for someone new. Pick the one that fits."
                : "Setting your level adjusts your trainer's guidance."}
            </p>
          </>
        )}
      </Loadable>
      <Notice tone="error">{error}</Notice>
    </Section>
  );
}
