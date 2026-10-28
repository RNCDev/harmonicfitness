// The settings drawer: keys, signing in another device, the password, signing out.
import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api, NotSignedIn, type DeviceLink } from "../api";
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
};

export function ContextColumn({ username, open, onClose, onSignedOut, onSignOut }: Props) {
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Keys and settings">
        <div className="ctx-top">
          <h2>Keys and settings</h2>
          <button type="button" className="ctx-close" onClick={onClose}>Close</button>
        </div>
        <div className="cx-list">
          <KeysBox onSignedOut={onSignedOut} />
          <DeviceLinkBox onSignedOut={onSignedOut} />
          <PasswordBox username={username} onSignedOut={onSignedOut} />
          <button type="button" className="quiet signout" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>
    </>
  );
}
