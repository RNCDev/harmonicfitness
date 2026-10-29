// The settings drawer: keys first; then the account: bringing in a folder, signing in another device,
// the password, export and delete, signing out.
import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api, ApiError, NotSignedIn, type DeviceLink, type KeyState } from "../api";
import { PasswordForm } from "../SignIn";
import { KeysBox } from "./KeysBox";

function until(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function DeviceLinkBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [link, setLink] = useState<DeviceLink | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (link && canvas.current) {
      QRCode.toCanvas(canvas.current, link.url, {
        width: 200, margin: 2, color: { dark: "#000000", light: "#ffffff" },
      }).catch(() => setError("Couldn't draw the code; the link below still works."));
    }
  }, [link]);

  async function make() {
    setBusy(true);
    setError(null);
    try {
      setLink(await api.deviceLink());
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError("Couldn't make a link. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cx-box">
      <button type="button" className="quiet" onClick={make} disabled={busy}>
        {link ? "Make a new link" : "Sign in another device"}
      </button>
      {error && <p className="cx-s err" role="alert">{error}</p>}
      {link && (
        <div className="device">
          <p className="cx-s">Scan this, or open the link on the other device. It works once, within 10 minutes{until(link.expires_at) && ` (until ${until(link.expires_at)})`}.</p>
          <canvas ref={canvas} className="qr" aria-label="QR code of the sign-in link" role="img" />
          <p className="link"><code>{link.url}</code></p>
        </div>
      )}
    </div>
  );
}

function ImportBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function take(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      const r = await api.importFolder(file);
      setNote(`Brought in ${r.imported} files${r.left_out ? ` (left out ${r.left_out}: keys, audio, caches, backups)` : ""}.`);
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError(e instanceof ApiError ? e.message : "Couldn't send it. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cx-box">
      <p className="cx-s">Bring in your folder: a ZIP of your <code>me</code> folder from HarmonicFitness on your computer. Its files replace the starter ones here. Key files are never kept.</p>
      <label className="quiet import">
        {busy ? "Bringing it in…" : "Choose a ZIP"}
        <input type="file" accept=".zip,application/zip" disabled={busy} className="sr"
          onChange={(e) => { void take(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      {note && <p className="cx-s" role="status">{note}</p>}
      {error && <p className="cx-s err" role="alert">{error}</p>}
    </div>
  );
}

function AccountBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount(password);
      onSignedOut();
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError(e instanceof ApiError ? e.message : "Couldn't delete it. Try again.");
      setBusy(false);
    }
  }

  return (
    <div className="cx-box">
      <p className="cx-s">Your files, as a ZIP you can open on your computer as HarmonicFitness's <code>me</code> folder. Keys are never in it.</p>
      <a className="quiet import" href="/api/export" download>Download your files</a>
      {!open ? (
        <p className="cx-s"><button type="button" className="quiet danger" onClick={() => setOpen(true)}>Delete my account</button></p>
      ) : (
        <form className="auth" onSubmit={(e) => { e.preventDefault(); void remove(); }}>
          <p className="cx-s err">This deletes your account and everything in it: your files, keys, chats and audio. It can't be undone.</p>
          <label>
            Your password
            <input type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <p className="err" role="alert">{error}</p>}
          <div className="keys-actions">
            <button type="submit" className="go danger" disabled={busy || !password}>
              {busy ? "Deleting…" : "Delete everything"}
            </button>
            <button type="button" className="quiet" onClick={() => { setOpen(false); setPassword(""); setError(null); }}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}

function PasswordBox({ username, onSignedOut }: { username: string; onSignedOut: () => void }) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  return (
    <div className="cx-box">
      <p className="cx-s">Signed in as <strong>{username}</strong></p>
      {open ? (
        <PasswordForm username={username} needsCurrent onSignedOut={onSignedOut}
          onDone={() => { setOpen(false); setDone(true); }} />
      ) : (
        <button type="button" className="quiet" onClick={() => { setOpen(true); setDone(false); }}>
          Change password
        </button>
      )}
      {done && <p className="cx-s" role="status">Password changed.</p>}
    </div>
  );
}

type Props = {
  username: string;
  open: boolean;
  onClose: () => void;
  onSignedOut: () => void;
  onSignOut: () => void;
  onKeys?: (keys: KeyState[]) => void;
  /** A key row to open in edit mode (the welcome card's "Add your key"). */
  openRow?: { service: string; n: number } | null;
};

export function ContextColumn({ username, open, onClose, onSignedOut, onSignOut, onKeys, openRow }: Props) {
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Keys and settings">
        <div className="ctx-top">
          <h2>Keys and settings</h2>
          <button type="button" className="ctx-close" onClick={onClose}>Close</button>
        </div>
        <div className="cx-list">
          <KeysBox onSignedOut={onSignedOut} onKeys={onKeys} openRow={openRow} />
          <section className="cx-account" aria-labelledby="cx-account-h">
            <h3 className="cx-h" id="cx-account-h">Account</h3>
            <PasswordBox username={username} onSignedOut={onSignedOut} />
            <DeviceLinkBox onSignedOut={onSignedOut} />
            <ImportBox onSignedOut={onSignedOut} />
            <AccountBox onSignedOut={onSignedOut} />
            <button type="button" className="quiet signout" onClick={onSignOut}>Sign out</button>
          </section>
        </div>
      </aside>
    </>
  );
}
