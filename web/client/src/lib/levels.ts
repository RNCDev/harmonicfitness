// The listener's level, as the app names it and as they'd say it: Settings' cards and a new listener's first screen.
import type { Level } from "./api";

/** Each level's short name, over the sentence a listener would say. */
export const LEVEL_NAMES: Record<Level, string> = { novice: "New or returning", experienced: "Some experience",
  advanced: "Experienced" };

/** The three, as the setup skill's quick start asks them; novice first, the safe pick with nothing known yet. */
export const LEVEL_SAID: Record<Level, string> = {
  novice: "I'm new to this, or it's been a long while.",
  experienced: "I've trained before and know the basic moves, but I'm no expert.",
  advanced: "I know my way around and want to be pushed.",
};
export const LEVELS: Level[] = ["novice", "experienced", "advanced"];
