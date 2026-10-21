# My Profile

Claude reads this before every workout. It holds the stable facts: setup, equipment, interests, feeds and style. Injuries and the rules around them are in `health.md`, day-to-day status comes from the check-in at the start of each session, and the workout log and running feedback live in `log.md`. Edit this file when something lasting changes, such as new equipment or a new interest. The `setup` skill fills it in with you ("set me up").

Keep the line formats as they are where a tool reads them: the Voices list, "Copy finished MP3s to:", "Measured words per minute", "YouTube favorites", "Puzzles" and the Feeds lines.

I listen to narrated workouts through earbuds, with no screen and no timer. The audio is the workout: it tells me what to do, keeps me company, and moves me along on time. Priorities, in order: safe for my body today, clean to the ear, worth listening to.

## Basics
- Name or nickname (optional):
- Neighborhood: [neighborhood, city] (used only for local news, events and weather)
- Training background and current fitness:
- Goals right now:
## Listening setup
- Earbuds, one times speed. The MP3 that `tools/build.sh` renders is the workout.
- Copy finished MP3s to: [a folder that syncs to your phone, such as ~/Library/Mobile Documents/com~apple~CloudDocs/Workouts or ~/Library/CloudStorage/GoogleDrive-*/My Drive/Workouts; delete this line to keep MP3s only in me/workouts/]
  (`tools/build.sh` copies each finished MP3 to the path above. A leading `~` is your home folder and `*` matches anything, such as any Google account.)
- Measured words per minute (drafting guide): 165. A starting estimate; it only sizes the first draft, and the lint then predicts each segment's spoken seconds from the chosen voice's measured rate.
- Voices (names from `python3 tools/voices.py`; the first is the default; how to add one: `knowledge/voices.md`):
  - Chatterbox Coach: man in his forties, warm baritone, a seasoned trainer talking to one client. The most natural delivery.
  - Qwen3 Coach: man in his thirties, a focused class instructor. The clearest diction.
- Delivery wanted: a coach or instructor, grounded and motivating. Not an announcer, not sleepy, not goofy or high-pitched.
## Default session
- Usual length: twenty-five minutes
- Time of day: varies. Go by the time of the request: in the morning, preview the day ahead; in the evening, recap it.
- Preferred format: mix it up. Rotate rolling minutes, work-and-transition intervals, circuits, and long steady segments.
- Intensity: moderate, about six out of ten, leaving a couple of reps in the tank, and progress gradually across sessions.
## Equipment kits
- Home: [for example, pairs of ten and twenty pound dumbbells, a bench, a mat]
- Travel (no gym): bodyweight plus whatever the room has.
- Gym:
## Content
- Sports: [teams and leagues to follow]
- Science and tech breakthroughs: every session carries two current ones. This is the session's science. Exercise science is only an occasional one-line aside explaining a cue.
- YouTube favorites (deep dives retold from the video's transcript, via `tools/youtube.py`): Asianometry @Asianometry, Branch Education @BranchEducation, Practical Engineering @PracticalEngineeringChannel.
- Puzzles (the session's quiz, when one works by ear alone): MindYourDecisions @MindYourDecisions (via `tools/youtube.py puzzles`), plus The Fiddler and NPR's Sunday Puzzle from the Feeds.
- Books: [genres]
- Local: [local politics, transit, events]. Keep politics factual and even-handed.
- On this day in history.
- Never bring up:
- Headlines or deep dives: a mix. Each session gets a few quick headlines, plus one deep-dive thread told across several segments. The deep dive alternates by session: a video from YouTube favorites, then a news story, then a video.
## Feeds
Read by `tools/feeds.py` at the start of each session: results and schedules, weather, and recent headlines, so research searches only for what these miss. One source per line, `- <label> (<kind>): <value>`; the kinds are weather (latitude, longitude, rounded), espn (sport/league/team, as in ESPN's team URLs), rss (feed URL), weekly (feed URL; the newest two items from the last eight days, for weekly podcasts and puzzles) and onthisday (selected). A source that fails is listed at the end of the sheet.
- Weather (weather): [latitude, longitude, two decimals is plenty]
- [Team] (espn): [sport/league/team, for example hockey/nhl/nj]
- Local, [outlet] (rss): [feed URL]
- Deep tech, IEEE Spectrum (rss): https://spectrum.ieee.org/feeds/feed.rss
- Science, Quanta Magazine (rss): https://www.quantamagazine.org/feed/
- Science, Phys.org (rss): https://phys.org/rss-feed/
- Puzzle, The Fiddler (weekly): https://thefiddler.substack.com/feed
- Puzzle, NPR Sunday Puzzle (weekly): https://feeds.npr.org/4473090/rss.xml
- On this day, Wikipedia (onthisday): selected
## Narrator
- Tone: calm and focused. Keep humor light and occasional, with no hype.
- Pet peeves in workout audio:
