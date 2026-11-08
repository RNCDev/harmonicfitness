// The chat box's unsent text, kept for this tab across a reload.

/** The box's unsent text, kept for this tab across a reload. Storage may be missing or refuse: then it isn't kept. */
const DRAFT = "hf-chat-draft";
export function readDraft(): string {
  try {
    return sessionStorage.getItem(DRAFT) ?? "";
  } catch {
    return "";
  }
}
export function keepDraft(text: string): void {
  try {
    if (text) sessionStorage.setItem(DRAFT, text);
    else sessionStorage.removeItem(DRAFT);
  } catch {
    /* not kept */
  }
}
