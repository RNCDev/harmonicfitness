# Research

The evidence behind HarmonicFitness's training knowledge, kept current. The working files read it, the tools never do:
`knowledge/programming.md` (effort, rest, tempo, progression), `knowledge/sessions.toml` (session shapes and
doses), `knowledge/movements.toml` (the catalog's loads, levels and coaching), `knowledge/injury-playbook.md`
and `knowledge/kits.md`. When a number or rule there says `source:`, the source is in one of those files or in
a note here.

## Topics

- **Training:** how sessions are shaped and dosed (order, methods, sets, rest, intervals, progression, readiness).
- **Biomechanics:** how movements load joints and tissues (the catalog's `loads` and `support`, regressions).
- **Exercises:** what each movement trains, how to coach it without a mirror, its common faults.
- **Equipment:** what home and hotel kits hold and what each piece allows.
- **Voices:** the local text-to-speech models and how their takes are rendered, checked and finished (`knowledge/voices.md`, `tools/verify.py`).

## Notes

| Note | Topic | Feeds |
|---|---|---|
| [2026-10-21-session-structure.md](2026-10-21-session-structure.md) | Training: block order, methods, pattern balance, joint-load ladders, exercise count | `sessions.toml` (block order, push and pull balance) |
| [2026-10-30-movement-library.md](2026-10-30-movement-library.md) | Exercises, biomechanics, equipment: the 49 drafts finished and 103 new movements of 0.41.0 to 0.42.0, the new equipment, the refused names | `movements.toml` (loads, levels, coaching, `[unlisted]`), `kits.md` |

## Writing a note

- One note per question, named `<date>-<subject>.md`, with a line saying what it covers and what it doesn't.
- Cite only sources actually opened, with the URL; say when only an abstract was read. Paraphrase, quote briefly.
- End with what wasn't found ("Not confirmed"), so a house default stays marked as one.
- Then carry what changes practice into the working file it belongs to, citing the source there, and add the
  note to the table above. A note that overturns an older one says so, and the older one gets a line pointing to it.
