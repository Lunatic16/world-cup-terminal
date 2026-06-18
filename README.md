# ⚽ FIFA World Cup Interactive Terminal

A feature-rich, zero-dependency Python terminal application for following the FIFA World Cup — live scores, group standings, match stats, timelines, and lineups, all from your command line.

Data is sourced in real time from [FotMob](https://www.fotmob.com) via their public Next.js page payloads. No API key required.

---

## Features

- **Group Standings** — Full table for every group (A–L), with qualification spots highlighted in green. Supports `--group` flag to filter to a single group.
- **Finished Matches** — Paginated list of all completed results with scores.
- **Upcoming & Live Matches** — Full fixture list with kickoff times; live matches are separated into their own filter and highlighted.
- **Live Match Filter** — Dedicated "Live Now" view that appears in the menu only when matches are in progress.
- **Match Center** — Per-match sub-menu with three views:
  - 📈 **Team Statistics** — color-coded advantage highlighting (green = winning stat, red = losing)
  - ⏱ **Timeline** — goals, cards, substitutions with in/out names, own goals, and proper minute + added-time display
  - 👥 **Lineups** — starters and substitutes side-by-side with shirt numbers
- **Live Refresh** — `[R]` inside a live match center re-fetches that match; `[R]` from the main menu refreshes all data.
- **In-memory Cache** — Match details are fetched once per session. Revisiting the same Match Center is instant.
- **Paginated Match Lists** — 20 matches per page with `[N]ext` / `[P]rev` navigation.
- **Team Search** — Filter any match list by typing `/` and a team name.
- **ANSI Color Output** — Goals in green, red cards in red, yellow cards in yellow, live badges highlighted. Degrades gracefully on terminals without color support (including Windows CMD).
- **Concurrent Data Loading** — Overview and fixture endpoints are fetched in parallel via a thread pool, cutting startup time roughly in half.
- **argparse CLI** — `--season`, `--group`, and `--help` flags; backwards-compatible with the old positional argument.

---

## Requirements

- Python **3.10+** (uses `str | None` union type hints)
- No third-party packages — uses only the standard library (`urllib`, `json`, `html.parser`, `datetime`, `concurrent.futures`, `argparse`, `sys`)

> **Python 3.9 compatibility:** replace the `str | None` annotations with `Optional[str]` from `typing` if needed.

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
python interactive_world_cup.py --season 2022
# or positional (backwards-compatible)
python interactive_world_cup.py 2022
```

### Filter standings to one group

```bash
python interactive_world_cup.py --season 2026 --group B
```

### Help

```bash
python interactive_world_cup.py --help
```

---

## Navigation

All menus accept single-key keyboard input. No mouse required.

### Main Menu

```
──────── 🏆  FIFA World Cup 2026  —  Interactive Terminal ────────

   LIVE   2 matches in progress

  [1]  Group Standings
  [2]  Finished Matches
  [3]  Upcoming & Live Matches
  [4]  Live Matches Only          ← appears only when matches are live
  [R]  Refresh Data
  [Q]  Quit
```

### Match List

```
  [number]  Open Match Center for that game
  [/]       Search by team name
  [C]       Clear search filter
  [P/N]     Previous / Next page (when > 20 matches)
  [B]       Back to main menu
```

### Match Center

```
  [1]  Team Statistics
  [2]  Timeline / Key Events
  [3]  Lineups
  [R]  Refresh this match          ← appears only for live matches
  [B]  Back to match list
```

---

## Sample Output

### Group Standings (top-2 highlighted)

```
  #   Team                    Pld   W   D   L   GD  Pts
  ────────────────────────────────────────────────────
  1   USA                       3   2   1   0   +4    7   ← green
  2   Mexico                    3   1   1   1    0    4   ← green
  3   Panama                    3   1   0   2   -2    3
  4   Morocco                   3   0   2   1   -2    2
```

### Match List (live badge)

```
  [  1]  Jun 15, 18:00    Brazil                2-1   Argentina              LIVE
  [  2]  Jun 16, 15:00    France                vs    Germany
```

### Timeline

```
  90'+2'            ⚽  Mbappe
  78'               🔄  ▲ Thuram  ▼ Giroud
  55'               🟨  Bellingham  (YELLOW CARD)
  12'               ⚽  Kane  (Own Goal)
```

### Team Statistics

```
  Stat                        France             Germany
  ──────────────────────────────────────────────────────
  SHOTS
  Shots on target                  5                  3
  Total shots                     14                  9

  POSSESSION
  Ball possession               58%                42%
```

---

## How It Works

FotMob embeds the full page state as a JSON blob inside a `<script id="__NEXT_DATA__">` tag on every page. This script parses that tag using Python's stdlib `html.parser` (more robust than a regex) and extracts the `pageProps` payload — no browser automation, no headless Chrome, no paid API.

Three endpoints are used:

| Endpoint | Purpose |
|---|---|
| `/leagues/77/overview/world-cup?season=YEAR` | Standings (group tables) |
| `/leagues/77?season=YEAR` | Full fixture list |
| `/matches/<slug>` | Individual match details (stats, events, lineups) |

The league ID `77` is FotMob's internal identifier for the FIFA World Cup. Both the overview and fixture endpoints are fetched concurrently at startup using `concurrent.futures.ThreadPoolExecutor`.

---

## Error Handling

HTTP errors are classified and reported distinctly:

| Condition | Message |
|---|---|
| 404 Not Found | Page not found — season/league ID may be wrong |
| 429 Too Many Requests | Rate-limited — wait and retry |
| Network/timeout | Descriptive connection error |
| Missing `__NEXT_DATA__` | FotMob structure may have changed |

---

## Known Limitations

- **UTC times only** — Kickoff times are displayed in UTC. Local timezone conversion is not currently applied.
- **FotMob dependency** — This tool scrapes public web pages. If FotMob changes their page structure or blocks requests, the app may stop working without notice.
- **No disk persistence** — The match cache lives in memory for the duration of the session only. Restarting the app clears it.
- **Python 3.10+ required** — For `str | None` union syntax. Easily backported to 3.9 by replacing with `Optional[str]`.

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
