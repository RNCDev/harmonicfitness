// Recording, in Settings: whether a checked script records at once, with no Record button and no price shown.
import { Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

export function RecordBox({ on, onChange, error }: { on: boolean; onChange: (on: boolean) => void; error?: string | null }) {
  return (
    <Section id="cx-rec" title="Recording">
      <label className="switch">
        <input type="checkbox" role="switch" checked={on} onChange={(e) => onChange(e.target.checked)} />
        <span className="switch-name">Record without asking</span>
      </label>
      <p className="cx-s switch-note">
        {on
          ? "A checked script records without showing you the price first (usually less than 1 USD)."
          : "Shows you the price first (usually less than 1 USD) and waits for you to press Record."}
      </p>
      <Notice tone="error">{error}</Notice>
    </Section>
  );
}
