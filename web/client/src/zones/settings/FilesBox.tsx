// Your files, in Settings: the profile, log and workouts as a ZIP to download, or a me folder from HarmonicFitness
// on a computer to bring in. Keys are never in either.
import { useState } from "react";
import { api } from "../../lib/api";
import { SAID } from "../../lib/messages";
import { useAction } from "../../lib/useAction";
import { FileButton, LinkButton } from "../../ui/ActionLink";
import { Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

export function FilesBox() {
  const [note, setNote] = useState<string | null>(null);
  const take = useAction(async (file: File) => {
    setNote(null);
    const r = await api.importFolder(file);
    setNote(`Brought in ${r.imported} files${r.left_out ? ` (left out ${r.left_out}: keys, audio, caches, backups)` : ""}.`);
  }, { fallback: SAID.upload });

  return (
    <Section id="cx-files" title="Your files">
      <p className="cx-s">Your profile, log and workouts as a ZIP, or a <code>me</code> folder from
        HarmonicFitness on your computer. Keys are never included.</p>
      <div className="act-row">
        <LinkButton href="/api/export" download>Download your files</LinkButton>
        <div className="cx-box">
          <FileButton accept=".zip,application/zip" busy={take.busy} busyLabel="Bringing it in…"
            onFile={(f) => void take.run(f)}>Bring in a folder</FileButton>
          <Notice tone="done" className="cx-s">{note}</Notice>
          <Notice tone="error">{take.error}</Notice>
        </div>
      </div>
    </Section>
  );
}
