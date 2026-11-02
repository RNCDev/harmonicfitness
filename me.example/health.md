+++
schema = 6
# Each injury listed below needs a [[limits]] entry here (area, side, level, note). The brief's safety
# screen reads only these rows. level is off-limits (nothing that loads the area) or delicate (only light
# loads); knowledge/limits.toml says what each means for a session. Once a limit clears, keep its row and add
# cleared = <the day, such as 2026-11-02>: the screen then skips it, and the brief keeps what should carry on
# after it for a few weeks. An example, with an invented area:
#
# [[limits]]
# area = "wrist"
# side = "right"
# level = "delicate"
# flags = []
# rehab = []
# note = "Physio: no weight through the hand until cleared."
+++
# Health

Injuries and limitations, with the standing rules for each. Claude reads this before every workout and the check-in confirms how you are today; red flags (`./harmonicfitness get limits` lists them) stop the session. Where this file, the playbook and the movement catalog disagree, the strictest wins. This file is private: it lives only in `me/`.

HarmonicFitness is not medical advice. Anything a doctor or physical therapist has told you overrides everything here; write it down below and it will be followed literally.

## Active injuries and limitations
- None right now.

<!-- An entry looks like this, and each one also needs a [[limits]] row in the settings block above:
- Right wrist: strain, date of injury.
  - Programming: <what's banned and what's allowed>.
-->

## Clinician rules
<!-- One rule per line, word for word where possible; each is followed literally. -->
- Rule: [what a doctor or physical therapist told you]
