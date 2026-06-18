# ⚽ FIFA World Cup Interactive Terminal

A feature-rich, zero-dependency Python terminal application for following the FIFA World Cup — live scores, group standings, match stats, timelines, and lineups, all from your command line.

Data is sourced in real time from [FotMob](https://www.fotmob.com) via their public Next.js page payloads. No API key required.

---

## Features

- **Group Standings** — Full table for every group (A–L), including played, wins, draws, losses, goal difference, and points.
- **Finished Matches** — Browse all completed results with scores; drill into any match for detailed stats.
- **Upcoming & Live Matches** — View the full fixture list with kickoff times in UTC.
- **Match Center** — Per-match sub-menu with three views:
  - 📈 Team Statistics (shots, possession, passes, etc.)
  - ⏱ Timeline of key events (goals, cards, substitutions, own goals)
  - 👥 Starting lineups with shirt numbers
- **Season switching** — Defaults to 2026, but works for any World Cup season available on FotMob (e.g. `2022`).

---

## Requirements

- Python **3.11+**
- No third-party packages — uses only the standard library (`urllib`, `json`, `re`, `datetime`, `sys`)

---

## Installation

```bash
# Clone or download the script
git clone https://github.com/Lunatic16/world-cup-terminal.git
cd world-cup-terminal

# No pip install needed — just run it
python interactive_world_cup.py
```

---

## Usage

### Default (2026 World Cup)

```bash
python interactive_world_cup.py
```

### Specify a season

```bash
python interactive_world_cup.py 2022
```

The season argument maps to FotMob's internal season identifier. The two confirmed working values are `2026` (USA/Canada/Mexico) and `2022` (Qatar).

---

## Navigation

The app uses a simple numbered menu system throughout. All menus accept keyboard input — no mouse required.

### Main Menu

```
==============================================
🏆 FIFA WORLD CUP 2026 INTERACTIVE TERMINAL
==============================================
  [1] View Group Standings (Groups A–L)
  [2] View Finished Matches (Results & Stats)
  [3] View Upcoming/Live Matches
  [Q] Exit Application
```

### Match List

```
  [Number]  Open Match Center for that game
  [B]       Return to main menu
```

### Match Center

```
  [1]  Team Statistics
  [2]  Timeline / Key Events
  [3]  Lineups
  [B]  Back to match list
```

---

## Sample Output

### Group Standings

```
🔹 Group A
  Pos Team                  | Pld | W | D | L | GD | Pts
  ------------------------------------------------
  1 USA                     |   3 | 2 | 1 | 0 |  4 |  7
  2 Mexico                  |   3 | 1 | 1 | 1 |  0 |  4
  3 Panama                  |   3 | 1 | 0 | 2 | -2 |  3
  4 Morocco                 |   3 | 0 | 2 | 1 | -2 |  2
```

### Match Timeline

```
⏱ Match Timeline (Most recent first):
   90' [GOAL] Mbappe
   67' [SUBSTITUTION]  (IN: Thuram | OUT: Giroud)
   45' [YELLOWCARD] Bellingham (YELLOW CARD)
   12' [GOAL] Kane (OWN GOAL)
```

### Team Statistics

```
📈 Match Statistics:

  🔹 Shots
    Shots on target         :     5 vs 3
    Total shots             :    14 vs 9

  🔹 Possession
    Ball possession         :   58% vs 42%
```

---

## How It Works

FotMob embeds the full page state as a JSON blob inside a `<script id="__NEXT_DATA__">` tag on every page. This script fetches that tag directly using `urllib` and parses the JSON — no browser automation, no headless Chrome, no paid API.

Three endpoints are used:

| Endpoint | Purpose |
|---|---|
| `/leagues/77/overview/world-cup?season=YEAR` | Standings (group tables) |
| `/leagues/77?season=YEAR` | Full fixture list |
| `/matches/<slug>` | Individual match details (stats, events, lineups) |

The league ID `77` is FotMob's internal identifier for the FIFA World Cup.

---

## Known Limitations

- **Live match detection** — Matches in progress appear in the "Upcoming/Live" list alongside unstarted games; there is no dedicated live-only filter in the current version.
- **No pagination** — With 104 matches in the 2026 tournament, the match list will require terminal scrolling. A paginated view is planned.
- **UTC times only** — Kickoff times are displayed in UTC. Local timezone conversion is not currently applied.
- **FotMob dependency** — This tool scrapes public web pages. If FotMob changes their page structure or blocks requests, the app may stop working without notice.
- **No offline mode** — All data is fetched live; there is no caching between runs. Revisiting the same match center re-fetches the page.

---

## Planned Enhancements

- [ ] Separate "Live" match filter for in-progress games
- [ ] In-memory match cache to avoid redundant HTTP fetches within a session
- [ ] Paginated match lists (20 per page with `[N]ext` / `[P]rev`)
- [ ] ANSI color output (green for goals, red for cards, yellow for substitutions)
- [ ] Concurrent page fetches with `asyncio` for faster initial load
- [ ] `argparse`-based CLI with `--season`, `--help`, and `--group` flags
- [ ] Team search / filter across the fixture list
- [ ] Textual TUI port with a Tokyo Night theme

---

## Project Structure

```
world-cup-terminal/
├── interactive_world_cup.py   # Main application — self-contained, single file
└── README.md
```

---

## Disclaimer

This tool is for personal, non-commercial use only. It scrapes publicly accessible web pages from FotMob. All football data, scores, and statistics are the property of their respective rights holders. This project is not affiliated with FIFA, FotMob, or any football governing body.
