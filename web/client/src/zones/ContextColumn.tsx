// The context column: the user's files by name, and signing in another device.
import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api, NotSignedIn, type ContextFile, type DeviceLink } from "../api";

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

type Props = {
  files: ContextFile[] | null;
  open: boolean;
  onClose: () => void;
  onSignedOut: () => void;
  onSignOut: () => void;
};

export function ContextColumn({ files, open, onClose, onSignedOut, onSignOut }: Props) {
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Your files">
        <div className="ctx-top">
          <h2>Your files</h2>
          <button type="button" className="ctx-close" onClick={onClose}>Close</button>
        </div>
        <div className="cx-list">
          <div className="cx-box">
            {files === null ? <p className="cx-s">Loading…</p> : files.length === 0 ? (
              <p className="cx-s">No files yet.</p>
            ) : (
              <ul className="files">
                {files.map((f) => <li key={f.path}>{f.path}</li>)}
              </ul>
            )}
          </div>
          <DeviceLinkBox onSignedOut={onSignedOut} />
          <button type="button" className="quiet signout" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>
    </>
  );
}
