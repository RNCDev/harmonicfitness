+++
schema = 5
# What the coach calls you: a first name or nickname, said in the welcome, at the hardest set and at the sign-off. Empty means no name.
name = "Priya"
# The speaking rate ./sweatcast lint assumes when no voice is given; builds use each voice's measured pace.
words_per_minute = 165
# How workouts become audio, in order of preference: local (this computer's own engine) or a cloud voice (fish, elevenlabs, cartesia, deepgram) with its key in me/.env. Each build uses the first that works on the computer it runs on.
render = ["local"]
# Your training level: novice, experienced or advanced. The brief's menu of movements matches it; until set, it assumes novice.
experience = "advanced"
# Movements you enjoy (ids or names from ./sweatcast movements); sessions favour them.
likes = []
# Movements to leave out (ids or names); the brief's menu never lists them.
dislikes = []
# Where finished MP3s go: a folder that syncs to your phone. ~ is your home folder and * matches anything (any Google account). Once the copy is there the local MP3 is removed; empty keeps MP3s in me/workouts/.
deliver_to = ""
# Channels (@handles) for the deep dives retold from a video's transcript.
youtube_favorites = ["Asianometry", "BranchEducation", "PracticalEngineeringChannel"]
# Channels (@handles) whose puzzles can be the session's quiz.
puzzles = ["MindYourDecisions"]

# Equipment kits a session can be planned with: a name and the equipment ids you have there (./sweatcast movements lists them).

[[kits]]
name = "full-gym"
equipment = ["dumbbells", "kettlebell", "bench", "band", "mat", "chair", "towel", "foam-roller", "strap", "bike", "rower", "cable", "machines", "barbell", "rack", "ski-erg", "air-bike", "sled", "treadmill", "elliptical", "stair-climber"]

# Fetched by ./sweatcast feeds at the start of each session. Kinds: weather (latitude, longitude), espn (sport/league/team, as in ESPN's team URLs), rss and weekly (feed URL), onthisday (selected).

[[feeds]]
label = "Weather"
kind = "weather"
value = "45.00, 10.00"

[[feeds]]
label = "Deep tech, IEEE Spectrum"
kind = "rss"
value = "https://spectrum.ieee.org/feeds/feed.rss"

[[feeds]]
label = "Science, Quanta Magazine"
kind = "rss"
value = "https://www.quantamagazine.org/feed/"

[[feeds]]
label = "Science, Phys.org"
kind = "rss"
value = "https://phys.org/rss-feed/"

[[feeds]]
label = "Puzzle, The Fiddler"
kind = "weekly"
value = "https://thefiddler.substack.com/feed"

[[feeds]]
label = "Puzzle, NPR Sunday Puzzle"
kind = "weekly"
value = "https://feeds.npr.org/4473090/rss.xml"

[[feeds]]
label = "On this day, Wikipedia"
kind = "onthisday"
value = "selected"
+++
# My Profile

An invented listener for the judged grid in docs/eval/; nothing here is about a real person.

The settings the tools read (voices, where MP3s are copied, words per minute, YouTube channels, puzzles and feeds) are in the `+++` block at the top of this file.

Claude reads this before every workout. It holds the stable facts: setup, equipment, interests, feeds and style. Injuries and the rules around them are in `health.md`, day-to-day status comes from the check-in at the start of each session, and the workout log and running feedback live in `log.md`. Edit this file when something lasting changes, such as new equipment or a new interest. The `setup` skill fills it in with you ("set me up").

I listen to narrated workouts through earbuds, with no screen and no timer. The audio is the workout: it tells me what to do, keeps me company, and moves me along on time. Priorities, in order: safe for my body today, clean to the ear, worth listening to.

## Basics
- Name or nickname: in the settings above (`name`), so the coach greets them by it.
- Neighborhood: Ridgecrest (an invented town)
- Training background and current fitness: trains five days a week, several years of barbell work (invented)
- Goals right now: keep building strength while the back recovers
## Listening setup
- Earbuds, one times speed. The MP3 that `./sweatcast build` renders is the workout.
- Delivery wanted: a coach or instructor, grounded and motivating. Not an announcer, not sleepy, not goofy or high-pitched.
## Default session
- Usual length: twenty-five minutes
- Time of day: varies. Go by the time of the request: in the morning, preview the day ahead; in the evening, recap it.
- Preferred format: mix it up. Rotate rolling minutes, work-and-transition intervals, circuits, and long steady segments.
- Intensity: moderate, about six out of ten, leaving a couple of reps in the tank, and progress gradually across sessions.
## Equipment kits
- Home: none
- Travel (no gym): bodyweight plus whatever the room has.
- Gym: a full commercial gym
## Content
- Sports: none
- Science and tech breakthroughs: every session carries two current ones. This is the session's science.
- Books: thrillers
- Local: events. Keep politics factual and even-handed.
- On this day in history.
- Never bring up:
- Headlines or deep dives: a mix. Each session gets a few quick headlines, plus one deep-dive thread told across several segments. The deep dive alternates by session: a video from YouTube favorites, then a news story, then a video.
## Narrator
How the coach talks now lives with each coach, in me/personas/<coach>/persona.md.
