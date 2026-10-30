+++
schema = 6
# Channels (@handles) whose videos can be retold, from their transcripts, as a serial across the rests.
youtube_favorites = ["Asianometry", "BranchEducation", "PracticalEngineeringChannel"]
# Channels (@handles) whose puzzles can be a quiz or brain teaser.
puzzles = ["MindYourDecisions"]
# Ways of telling to leave out of the rests, by id from knowledge/content.toml (such as "memory_game").
skip_formats = []

# Fetched by ./harmonicfitness feeds at the start of each session; name each after the topic it serves. Kinds: weather (latitude, longitude), espn (sport/league/team, as in ESPN's team URLs), rss and weekly (feed URL), onthisday (selected), wikipedia (featured: the featured article, most read, in the news and did you know).

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

What fills the rests between exercises. Write your topics as plain lines, as many as you like, each with a note if you want one ("scores and previews; a big trade is worth hearing about"). Before each workout the coach picks the topics told longest ago, finds what's new or worth knowing, and tells each one the way that suits it: a quick hit, a bigger story, an explainer, a quiz, a recommendation. Say "update my interests" any time to add topics, with ideas from what's trending.

## Topics
I like to stay current on and learn about:
- [a team you follow: scores and previews; trades and big news welcome]
- [where you live: local news, transit, what's on]
- [a subject you love: science, history, a hobby, a language you're learning]

## Never bring up
- [topics to leave out, or "nothing"]

## Taste
Shows, books, music, comedians, restaurants and drinks you've loved or not, out of five, so recommendations are in their spirit (the setup skill asks).
