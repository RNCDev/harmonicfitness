// What kind of site this is, and the few sentences more than one page says about it. `clerk`: sign-in goes through
// Clerk, so there is no password here. The app provides it once the server says who is signed in.
import { createContext, useContext } from "react";

export type Site = { clerk: boolean };

export const SiteContext = createContext<Site>({ clerk: false });

export const useSite = () => useContext(SiteContext);

/** "1 minute", "20 minutes". */
export const minutesSaid = (n: number) => `${n} ${n === 1 ? "minute" : "minutes"}`;

/** The voice services' names as people say them, for an offer that names only the id. */
const SERVICE_NAMES: Record<string, string> = {
  fish: "Fish Audio", elevenlabs: "ElevenLabs", gemini: "Gemini", inworld: "Inworld", openrouter: "OpenRouter",
};

/** Said once, before the first recording (on its Record card, or on the first screen's form for a new listener):
 * where the script goes, and what that means. */
export const privacyNote = (service: string) => `Recording sends the script to ${SERVICE_NAMES[service] ?? service}, `
  + `and it can mention your injuries ("easy on that left knee").`;
