// The listener's level as three cards side by side, each the sentence that fits someone at it: Settings (Your
// level) and a new listener's first screen (About you) pick the same way.
import type { Level } from "../lib/api";
import { LEVEL_NAMES } from "../lib/levels";
import { Button } from "./Button";

export function LevelCards({ choices, value, onChoose, labelledBy }: {
  /** Each level and the sentence said for it, in order. */
  choices: { level: Level; said: string }[];
  value: Level | null;
  onChoose: (level: Level) => void;
  /** The id of the question or heading that names the group. */
  labelledBy: string;
}) {
  return (
    <div className="level-opts" role="radiogroup" aria-labelledby={labelledBy}>
      {choices.map((c) => (
        <Button key={c.level} variant="bare" className="level-card" role="radio" aria-checked={value === c.level}
          onClick={() => onChoose(c.level)}>
          <span className="level-name">{LEVEL_NAMES[c.level]}</span>
          <span className="level-said">{c.said}</span>
        </Button>
      ))}
    </div>
  );
}
