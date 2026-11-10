// What looks like an outlined button but isn't one: a link that downloads (Download your files) and a file
// picker (Bring in a folder). Both take Button's outlined look here, so no page draws a shared look by hand
// (layers.test.ts).
import type { AnchorHTMLAttributes, ReactNode } from "react";

/** A link drawn as an outlined button. */
export function LinkButton({ className, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { children: ReactNode }) {
  return <a className={`act outlined${className ? " " + className : ""}`} {...rest}>{children}</a>;
}

/** A file picker drawn as an outlined button: `onFile` gets the file chosen; while `busy`, `busyLabel` shows and it's
 * switched off. The input is cleared after each choice, so the same file can be picked again. */
export function FileButton({ accept, busy = false, busyLabel, onFile, children }: {
  accept?: string; busy?: boolean; busyLabel?: string; onFile: (file: File) => void; children: ReactNode;
}) {
  return (
    <label className="act outlined" aria-busy={busy || undefined}>
      {busy && busyLabel ? busyLabel : children}
      <input type="file" accept={accept} disabled={busy} className="sr"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </label>
  );
}
