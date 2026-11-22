// Recording, in Settings: whether a checked script records at once, with no Record button and no price shown (in
// dollars, or in minutes on a site that sells them).
import { useSite } from "../../lib/site";
import { Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

export function RecordBox({ on, onChange, error }: { on: boolean; onChange: (on: boolean) => void; error?: string | null }) {
  const { hosted } = useSite();
  const said = hosted
    ? { on: "A checked script records without showing you its minutes first.",
        off: "Shows you how many minutes it takes first, and waits for you to press Record." }
    : { on: "A checked script records without showing you the price first (usually less than 1 USD).",
        off: "Shows you the price first (usually less than 1 USD) and waits for you to press Record." };
  return (
    <Section id="cx-rec" title="Recording">
      <label className="switch">
        <input type="checkbox" role="switch" checked={on} onChange={(e) => onChange(e.target.checked)} />
        <span className="switch-name">Record without asking</span>
      </label>
      <p className="cx-s switch-note">
        {on ? said.on : said.off}
      </p>
      <Notice tone="error">{error}</Notice>
    </Section>
  );
}
