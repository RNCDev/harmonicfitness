// A section of the Settings drawer: its heading, labelling it, then what it holds. The drawer shows one at a time,
// by its id (styles/settings.css, data-shown).
import type { ReactNode } from "react";

export function Section({ id, title, children }: { id: string; title: string; children?: ReactNode }) {
  return (
    <section className="cx-box cx-sec" id={id} aria-labelledby={`${id}-h`}>
      <h3 className="head cx-h" id={`${id}-h`}>{title}</h3>
      {children}
    </section>
  );
}
