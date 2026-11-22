// The Settings drawer, in three parts: tabs at the top, one per section (the minutes, what's used most; the
// listener's level; recording; the private podcast feed; the background behind the page, called the sky in the code,
// with its credit; their files); the chosen section alone; and the account at the foot (Account.tsx). While it's open it
// holds the keyboard: Tab stays inside, Escape closes it, and the page behind can't be reached. Each section is a
// file of its own beside this one.
import { useEffect, useRef, useState, type RefObject } from "react";
import { useFocusTrap } from "../../lib/useFocusTrap";
import type { Minutes } from "../../lib/useMinutes";
import type { SkyKind } from "../../ui/Sky";
import { Button } from "../../ui/Button";
import { Account } from "./Account";
import { FeedBox } from "./FeedBox";
import { FilesBox } from "./FilesBox";
import { LevelBox } from "./LevelBox";
import { MinutesBox } from "./MinutesBox";
import { RecordBox } from "./RecordBox";
import { SkyBox } from "./SkyBox";

type Props = {
  username: string;
  /** The app's version (and build), shown at the foot of Settings. */
  version?: string;
  open: boolean;
  onClose: () => void;
  /** Sign out, at the listener's ask. */
  onSignOut: () => void;
  /** The account is gone: back to the sign-in page. */
  onDeleted?: () => void;
  /** The background behind the page (the sky), the choice of it, and why the last choice didn't hold. */
  sky?: SkyKind;
  onSky?: (sky: SkyKind) => void;
  skyError?: string | null;
  /** Record without asking: a checked script records at once, with no Record button. */
  autoRecord?: boolean;
  onAutoRecord?: (on: boolean) => void;
  autoRecordError?: string | null;
  /** Where focus goes when the drawer closes (the Settings button). */
  returnFocus?: RefObject<HTMLElement>;
  /** The listener's minutes; and how they just came back from the checkout page. */
  minutes?: Minutes;
  back?: "bought" | "cancelled" | null;
  /** A section asked for from elsewhere (the header's minutes, "Get minutes"); `n` grows with each ask. */
  goTo?: { section: string; n: number } | null;
  /** The account signs in through Clerk: it proves who is asking with Clerk, not a password. */
  clerkLinked?: boolean;
};

export function Settings({ username, version, open, onClose, onSignOut, onDeleted = onSignOut,
  sky = "flow", onSky, skyError, autoRecord = false, onAutoRecord, autoRecordError, returnFocus, minutes, back = null, goTo = null,
  clerkLinked = false }: Props) {
  const drawer = useRef<HTMLElement>(null);
  useFocusTrap(drawer, open, { onEscape: onClose, returnFocus, inert: true });
  // the tabs: one per section, and only the chosen section shows (a button, not a link: the page's own address
  // already says which page is open)
  const sections = [
    ...(minutes ? [{ id: "cx-minutes", name: "Minutes" }] : []),
    { id: "cx-level", name: "Level" },
    ...(onAutoRecord ? [{ id: "cx-rec", name: "Recording" }] : []),
    { id: "cx-feed", name: "Podcast" },
    ...(onSky ? [{ id: "cx-sky", name: "Background" }] : []),
    { id: "cx-files", name: "Files" },
  ];
  const [shown, setShown] = useState(sections[0].id);
  const has = (id: string) => sections.some((x) => x.id === id);
  useEffect(() => { if (goTo && has(goTo.section)) setShown(goTo.section); }, [goTo]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" data-scrim="" />
      <aside ref={drawer} className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Settings" role="dialog"
        aria-modal={open || undefined}>
        <div className="ctx-top">
          <h2 className="head">Settings</h2>
          <Button variant="bare" className="ctx-close" onClick={onClose}>Close</Button>
        </div>
        <nav className="cx-tabs" aria-label="Settings sections">
          {sections.map((s) => (
            <Button key={s.id} variant="bare" aria-current={shown === s.id || undefined} onClick={() => setShown(s.id)}>
              {s.name}
            </Button>
          ))}
        </nav>
        <div className="cx-main" data-shown={shown}>
          {minutes && <MinutesBox minutes={minutes} back={back} />}
          <LevelBox />
          {onAutoRecord && <RecordBox on={autoRecord} onChange={onAutoRecord} error={autoRecordError} />}
          {shown === "cx-feed" && <FeedBox />}{/* loaded when opened: most visits to Settings never need it */}
          {onSky && <SkyBox sky={sky} onSky={onSky} error={skyError} />}
          <FilesBox />
        </div>
        <Account username={username} version={version} onSignOut={onSignOut} onDeleted={onDeleted}
          clerkLinked={clerkLinked} />
      </aside>
    </>
  );
}
