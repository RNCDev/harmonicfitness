// Asking Settings to open one key's row: from the welcome card (and make it the writer, `choose`), or from a coach
// that needs that service's key. The app holds the latest ask and provides it; the keys list reads it, so nothing
// between them relays it. `n` grows with each ask, so the same row can be asked for again.
import { createContext, useContext } from "react";

export type KeyAsk = { service: string; n: number; choose?: boolean };

export const KeyAskContext = createContext<KeyAsk | null>(null);

/** The latest ask for a key's row, or null. */
export const useKeyAsk = () => useContext(KeyAskContext);
