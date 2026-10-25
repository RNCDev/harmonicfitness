+++
schema = 6
# Channels (@handles) for the deep dives retold from a video's transcript.
youtube_favorites = ["Asianometry", "BranchEducation", "PracticalEngineeringChannel"]
# Channels (@handles) whose puzzles can be the session's quiz.
puzzles = ["MindYourDecisions"]

# What the filler between exercises rotates through: [[interests]] rows, each a name, its slot (today, science, deep_dive, quiz, delight or learn; knowledge/content.toml) and a detail for research. Within a slot, the one told longest ago comes next. Without any rows, knowledge/content.toml's defaults.

# Fetched by ./sweatcast feeds at the start of each session. Kinds: weather (latitude, longitude), espn (sport/league/team, as in ESPN's team URLs), rss and weekly (feed URL), onthisday (selected), wikipedia (featured: the featured article, most read, in the news and did you know).

[[feeds]]
label = "Weather"
kind = "weather"
value = "[latitude, longitude, two decimals is plenty]"

[[feeds]]
label = "[Team]"
kind = "espn"
value = "[sport/league/team, for example hockey/nhl/nj]"

[[feeds]]
label = "Local, [outlet]"
kind = "rss"
value = "[feed URL]"

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

[[feeds]]
label = "Wikipedia today"
kind = "wikipedia"
value = "featured"
+++
# Content

What fills the rests between exercises: interests, feeds, YouTube channels and puzzles (the settings above), and the topics and taste below. Research reads this before each workout.

## Content
- Sports: [teams and leagues to follow]
- Science and tech breakthroughs: one or two current ones a session, by its length. This is the session's science.
- Books: [genres]
- Local: [local politics, transit, events]. Keep politics factual and even-handed.
- On this day in history.
- Never bring up: [topics to leave out, or "nothing"]
## Taste
Shows, books, music, comedians, restaurants and drinks you've loved or not, out of five, so the filler recommends in their spirit (the setup skill asks).
- Headlines or deep dives: a mix. Each session gets a few quick headlines, plus one deep-dive thread told across several segments. The deep dive alternates by session: a video from YouTube favorites, then a news story, then a video.
