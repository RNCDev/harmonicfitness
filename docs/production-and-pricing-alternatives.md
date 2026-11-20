# Production and pricing: alternatives

**Status:** a roadmap proposal, 2026-11-20. Nothing here is built. The numbers come from the token bench of
2026-11-10 ([benchmark-script-writing/README.md](benchmark-script-writing/README.md)) and need measuring again
before any price is set.

**The question:** can the website sell a flat monthly plan, about $10 for up to 30 workouts, and stay above cost?
And can research be shared across listeners so that its cost is spread over everyone?

## The proposal as first put

- **Class A, a flat fee:** about $10 a month for up to 30 scripts.
  - No personal research. One run at 05:00 UTC researches national and global news and the day's big topics, for
    everyone.
  - When a script is written, the only thing looked up for that listener is their local weather.
- **Class B, bring your own key:** listeners who want research on their own topics pay for it with their own key.

## What a workout costs, and where

A 15-minute workout on Gemini, from the bench:

| Line | Cost | Can it be shared across listeners? |
|---|---|---|
| Voice (Gemini TTS) | 12¢ to 13¢ | Partly: see "Share the voice" below |
| Agent loop and writers | about 13¢ to 17¢ | No: each script is its own |
| Research and top-up, tokens | 3¢ to 4¢ | Yes |
| Search fees | free for the first 5,000 a month, then $14 per 1,000 | Yes |
| **Total today** | **29¢ to 34¢** | |
| **Total at 2027 rates, with bench cuts #1 to #4** | **36¢ to 46¢** | |

Search fees are what make research matter at scale. A workout runs 4 to 10 searches, so once past the free 5,000 a
month, research costs about 6¢ to 15¢ a workout. Sharing it is worth doing. But research is about a fifth of the
cost, not most of it.

### What $10 for 30 workouts leaves

A $10 card payment keeps $9.41 after fees (2.9% plus 30¢): **31¢ a workout** for a listener who uses all thirty.

| A listener who uses all 30, at 15 minutes each | Cost per workout | Result per workout |
|---|---|---|
| Today | 29¢ to 34¢ | about break-even, before hosting |
| 2027 rates, with cuts #1 to #4 | 36¢ to 46¢ | a loss of 5¢ to 15¢ |
| 2027 rates, with cuts and shared research | about 30¢ to 40¢ | about break-even, or a loss |
| A 30-minute workout, 2027 rates | about 60¢ to 80¢ | a loss of about 30¢ or more |

Counting scripts only pays if most listeners use few of them. The listeners who use all thirty are the ones who
like the product most, and the plan would lose money on each of them.

### What dropping personal research costs the product

- **It removes what makes the workout worth listening to:** a coach who talks about the listener's own world. That
  is the third of the project's priorities, and the thing that sets it apart from a playlist.
- **News is a poor default for a workout.** Much of it is grim or political, and it runs into a listener's "Never
  bring up". Nothing checks a script against that list yet: in the bench, Opus run 2 named the weekday in its
  opening.
- **05:00 UTC is midnight on the US east coast and evening in Asia,** so for many listeners "this morning's news"
  is a day old.

## Recommended shape

### Class A: hosted, about $10 a month

1. **Sell minutes, not scripts.** For example "300 minutes a month", or "20 workouts of up to 20 minutes".
   - Cost grows with minutes. Voice and writing both scale with length, not with the number of scripts.
   - At 2027 rates, with the cuts and shared research, 300 minutes leaves a margin of about 20% to 30% even for a
     listener who uses all of them. Confirm with the bench before publishing a number.
2. **Share research by topic, not in one global run.** This is cut #3 in the bench README, which still needs its
   own design.
   - Keep a catalog of the topics listeners follow: start with the most-followed 200 or so.
   - Research each topic once a day, at 05:00 UTC or staggered by region, into a shared reserve. The engine already
     has the parts: `research/reserve/`, the topics in `knowledge/content.toml`, and `interests`.
   - Each listener's own step only picks from the topics they follow and frames what it picks. It runs no web
     search. `told.jsonl` (what this listener has already heard) and "Never bring up" stay per listener.
   - This keeps almost all of the savings of one shared run and keeps the personal feel.
3. **Make news one topic in the catalog, opt-in,** with a filter for grim stories. Not the default.
4. **Weather from a free weather API** (Open-Meteo, for example), never from a model's search.
   - It costs nothing and is more reliable than a search.
   - It needs only a city, never an exact location.
5. **Share the voice where it can be shared.** Voice is the largest single line.
   - For each stock web coach, record the counts, "go", "rest" and the common transitions once, and reuse them
     for every listener. Local coaches already work this way with `cues/`.
   - Measure what share of a script's characters these clips cover before counting on the saving.

### Class B: "your own topics", about $15 to $20 a month

- Any free-text topic, researched for this listener alone.
- More minutes, and longer sessions.
- Hosted, like Class A. No key to paste.

BYOK isn't the upgrade, for two reasons:
- The web client moved away from asking listeners for keys (2026-11-10): mainstream listeners won't paste one.
- A key doesn't split. A listener's Gemini key would pay for the writing and the voice too, not only the research.

### BYOK: kept, not advertised

For people who tinker, and for the local engine. It costs the site only hosting.

## Other variants

- **A free tier made from the shared pool:** a few 10-minute workouts a month, on catalog topics and stock coaches
  only. Shared research and recorded cue clips keep it cheap.
- **Long sessions cost more:** a 45- or 60-minute session counts double minutes, or needs Class B.
- **Price for 2027 from launch.** Gemini's input and output rates double on 2027-01-01. Raising a subscription
  later is much harder than raising the price of a credit pack, so set the minute allowance for 2027's rates
  from the start.
- **Credit packs alongside the plan,** for listeners who train now and then and won't subscribe. The bench sketched
  these at 6¢ a minute in $10 packs.

## Order of work

1. **Measure how many listeners share topics.** This decides how much shared research saves. With few listeners
   per topic it saves little, and per-listener research stays. Without real listeners yet, estimate it from the
   catalog that onboarding offers.
2. **Weather from an API.** Small, cheap and independent of everything else.
3. **The bench cuts already ranked** (#1, #2 and #4 in the bench README): ending the turn after the price, code
   running the fixed steps, and caching.
4. **Design and build the shared topic reserve** (cut #3), with the per-listener pick.
5. **Recorded cue clips for the stock web coaches,** after measuring their share of a script's characters.
6. **Billing:** the minute allowance, the two classes and card payments. Set the numbers last, from the bench run
   at 2027 rates.

## Not yet measured

- Workouts of 30 minutes and longer, at 2027 rates.
- Hosting per workout, from the Fly bill.
- Re-records and failed runs, as a share of all runs.
- How much of a script's characters recorded cue clips would cover.
- How many minutes a month real listeners use: the figure a flat plan depends on.
