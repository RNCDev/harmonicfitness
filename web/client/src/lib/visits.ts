// What this browser remembers of signing in and out here.
//
// Signing out where sign-in goes through Clerk: this site's session ends at once, but Clerk keeps one of its own
// in the browser, and the sign-in page would trade it straight back for a new session here. So signing out (or
// deleting the account) leaves a note, and the sign-in page, once Clerk has loaded, ends Clerk's session instead
// of trading it, then takes the note away. Kept in the browser's storage so a reload in between still signs out;
// where storage refuses, in memory.
const LEAVING = "harmonicfitness.leaving";
let noted = false;

export function leave(): void {
  noted = true;
  try { localStorage.setItem(LEAVING, "1"); } catch { /* in memory only */ }
}

export function leaving(): boolean {
  if (noted) return true;
  try { return localStorage.getItem(LEAVING) === "1"; } catch { return false; }
}

export function left(): void {
  noted = false;
  try { localStorage.removeItem(LEAVING); } catch { /* nothing was kept */ }
}

/** Set once someone signs in here, so the next visit opens on the form, not the front page. */
const RETURNING = "harmonicfitness.returning";
export const returning = () => { try { return localStorage.getItem(RETURNING) === "1"; } catch { return false; } };
export const remember = () => { try { localStorage.setItem(RETURNING, "1"); } catch { /* the front next time */ } };
