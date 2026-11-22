// Clerk's provider, where sign-in goes through Clerk: everything inside can ask Clerk who is signed in on this
// browser and show its sign-in form. The form takes the page's own look, read from the tokens as the browser
// resolved them, so no colour is typed here; and when Clerk leaves its form for an address on this site (after
// signing in or out) only the address changes, never the page, which shows what's next itself.
import { useMemo, type ReactNode } from "react";
import { ClerkProvider } from "@clerk/clerk-react";

/** A token's value as the browser resolved it; undefined where there is none (Clerk then keeps its own). */
function token(name: string): string | undefined {
  try {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || undefined;
  } catch {
    return undefined;
  }
}

/** Only what's set, so a token that can't be read leaves Clerk's default in place. */
const set = <T extends Record<string, string | undefined>>(o: T) =>
  Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as { [K in keyof T]?: string };

function look() {
  return {
    variables: set({
      colorPrimary: token("--action"), colorPrimaryForeground: token("--on-action"),
      colorBackground: token("--surface-raised"), colorForeground: token("--text"),
      colorMutedForeground: token("--text-2"), colorNeutral: token("--text"),
      colorInput: token("--surface-2"), colorInputForeground: token("--text"),
      colorDanger: token("--danger"), fontFamily: token("--font"), borderRadius: token("--radius-sheet"),
    }),
  };
}

/** Clerk asks to go to an address on this site: the address changes and the page stays. */
function go(to: string): void {
  window.history.replaceState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function ClerkGate({ publishableKey, children }: { publishableKey: string; children: ReactNode }) {
  const appearance = useMemo(look, []);
  return (
    <ClerkProvider publishableKey={publishableKey} appearance={appearance} routerPush={go} routerReplace={go}
      signInUrl="/" signUpUrl="/" afterSignOutUrl="/">
      {children}
    </ClerkProvider>
  );
}
