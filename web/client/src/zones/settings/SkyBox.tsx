// The background behind the page (the sky, in the code), in Settings: a tile for each, with its credit.
import { SKIES, SkyPreview, type SkyKind } from "../../ui/Sky";
import { Button } from "../../ui/Button";
import { Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

export function SkyBox({ sky, onSky, error }: { sky: SkyKind; onSky: (sky: SkyKind) => void; error?: string | null }) {
  return (
    <Section id="cx-sky" title="Background">
      <p className="cx-s sky-credit">
        Patterns after <a href="https://bookofshapes.com" target="_blank" rel="noopener noreferrer">Book of Shapes</a> by
        Nikolaj Sokolowski.
      </p>
      <div className="sky-opts" role="group" aria-labelledby="cx-sky-h">
        {SKIES.map((s) => (
          <Button key={s.kind} variant="tile" className="sky-opt" pressed={sky === s.kind} title={s.about}
            onClick={() => onSky(s.kind)}>
            <SkyPreview kind={s.kind} />
            <span className="sky-opt-name">{s.name}</span>
          </Button>
        ))}
      </div>
      <Notice tone="error">{error}</Notice>
    </Section>
  );
}
