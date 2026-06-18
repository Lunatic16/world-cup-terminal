#!/usr/bin/env python3
"""
FIFA World Cup Interactive Terminal
====================================
Real-time scores, standings, match stats, timelines, and lineups
sourced directly from FotMob. No API key required.

Usage:
    python interactive_world_cup.py [--season YEAR] [--group GROUP] [--help]
"""

import argparse
import asyncio
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# ANSI color helpers — gracefully degrades if terminal doesn't support colors
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    """Return True if the terminal likely supports ANSI escape codes."""
    import os
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_COLOR = _supports_color()

class C:
    """ANSI color constants."""
    RESET   = "\033[0m"    if _COLOR else ""
    BOLD    = "\033[1m"    if _COLOR else ""
    DIM     = "\033[2m"    if _COLOR else ""
    # Foreground
    RED     = "\033[31m"   if _COLOR else ""
    GREEN   = "\033[32m"   if _COLOR else ""
    YELLOW  = "\033[33m"   if _COLOR else ""
    BLUE    = "\033[34m"   if _COLOR else ""
    MAGENTA = "\033[35m"   if _COLOR else ""
    CYAN    = "\033[36m"   if _COLOR else ""
    WHITE   = "\033[97m"   if _COLOR else ""
    # Bright foreground
    BGREEN  = "\033[92m"   if _COLOR else ""
    BYELLOW = "\033[93m"   if _COLOR else ""
    BRED    = "\033[91m"   if _COLOR else ""
    BCYAN   = "\033[96m"   if _COLOR else ""


def col(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes and reset afterwards."""
    return "".join(codes) + text + C.RESET


# ---------------------------------------------------------------------------
# HTTP / HTML helpers
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class _NextDataParser(HTMLParser):
    """stdlib HTML parser that extracts the __NEXT_DATA__ <script> payload."""

    def __init__(self):
        super().__init__()
        self._capture = False
        self.result: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            attr_dict = dict(attrs)
            if attr_dict.get("id") == "__NEXT_DATA__":
                self._capture = True

    def handle_data(self, data):
        if self._capture:
            self.result = data
            self._capture = False

    def handle_endtag(self, tag):
        self._capture = False


def fetch_nextjs_data(url: str) -> dict | None:
    """
    Fetch *url* and return the pageProps from the __NEXT_DATA__ JSON payload.
    Returns None on any failure and prints a descriptive error.
    """
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.status
            if status_code == 404:
                print(col(f"\n❌ Page not found (404): {url}", C.RED))
                return None
            if status_code == 429:
                print(col("\n❌ Rate-limited by FotMob (429). Please wait a moment and retry.", C.YELLOW))
                return None
            html = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(col(f"\n❌ HTTP {e.code} error fetching {url}: {e.reason}", C.RED))
        return None
    except urllib.error.URLError as e:
        print(col(f"\n❌ Network error: {e.reason}", C.RED))
        return None
    except TimeoutError:
        print(col("\n❌ Request timed out. Check your connection.", C.RED))
        return None

    parser = _NextDataParser()
    parser.feed(html)

    if parser.result is None:
        print(col("\n❌ Could not find __NEXT_DATA__ in the page. FotMob may have changed their structure.", C.RED))
        return None

    try:
        data = json.loads(parser.result)
        return data.get("props", {}).get("pageProps", {})
    except json.JSONDecodeError as e:
        print(col(f"\n❌ Failed to parse JSON payload: {e}", C.RED))
        return None


def safe_get(obj, *keys, default=None):
    """Safely traverse nested dicts, returning *default* if any key is absent."""
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
        if obj is None:
            return default
    return obj


def parse_utc_time(utc_str: str) -> datetime | None:
    """
    Parse FotMob's UTC time string, handling both with- and without-microseconds
    variants, e.g. '2026-06-11T18:00:00.000Z' or '2026-06-11T18:00:00Z'.
    Returns a timezone-aware datetime or None on failure.
    """
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(utc_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def format_kickoff(utc_str: str, local_tz=None) -> str:
    """Return a human-readable kickoff string. Falls back to raw slice."""
    dt = parse_utc_time(utc_str)
    if dt is None:
        return utc_str[:16] if len(utc_str) >= 16 else utc_str
    if local_tz:
        dt = dt.astimezone(local_tz)
    return dt.strftime("%b %d, %H:%M")


# ---------------------------------------------------------------------------
# Match classification helpers
# ---------------------------------------------------------------------------

def classify_match(m: dict) -> str:
    """Return 'finished', 'live', or 'upcoming'."""
    if m.get("finished"):
        return "finished"
    if m.get("started"):
        return "live"
    return "upcoming"


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

PAGE_SIZE = 20  # matches per page


def divider(width: int = 50, char: str = "─") -> str:
    return col(char * width, C.DIM)


def header_line(title: str, width: int = 50) -> str:
    pad = max(0, width - len(title) - 2)
    left = pad // 2
    right = pad - left
    line = col("─" * left + " ", C.DIM) + col(title, C.BOLD, C.WHITE) + col(" " + "─" * right, C.DIM)
    return line


def event_icon(event_type: str, own_goal: bool = False, card: str = "") -> str:
    if event_type == "GOAL":
        return col("⚽", C.BGREEN) if not own_goal else col("⚽", C.RED)
    if event_type in ("YELLOWCARD", "YELLOW"):
        return col("🟨", C.BYELLOW)
    if event_type in ("REDCARD", "RED"):
        return col("🟥", C.BRED)
    if event_type == "YELLOWREDCARD":
        return col("🟨🟥", C.BRED)
    if event_type == "SUBSTITUTION":
        return col("🔄", C.CYAN)
    if event_type == "PENALTY":
        return col("🎯", C.BGREEN)
    if event_type == "VAR":
        return col("📺", C.MAGENTA)
    return col("•", C.DIM)


def live_badge() -> str:
    return col(" LIVE ", C.BOLD, C.BGREEN)


def score_display(m: dict) -> str:
    score = m.get("score_str") or "vs"
    status = classify_match(m)
    if status == "live":
        return col(score, C.BOLD, C.BGREEN)
    if status == "finished":
        return col(score, C.WHITE)
    return col("vs", C.DIM)


def paginate(items: list, page: int) -> tuple[list, int, int]:
    """
    Return (page_items, total_pages, corrected_page).
    Page is 0-indexed internally.
    """
    total = len(items)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    return items[start : start + PAGE_SIZE], total_pages, page


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class WorldCupApp:
    def __init__(self, season: str = "2026", group_filter: str | None = None):
        self.season = season
        self.group_filter = group_filter.upper() if group_filter else None
        self.league_id = 77  # FotMob's ID for the FIFA World Cup
        self.overview_data: dict | None = None
        self.matches_data: dict | None = None
        self.matches_list: list[dict] = []
        # In-memory match-detail cache  {match_id -> props_dict}
        self._match_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _fetch_overview(self) -> dict | None:
        url = (
            f"https://www.fotmob.com/leagues/{self.league_id}"
            f"/overview/world-cup?season={self.season}"
        )
        return fetch_nextjs_data(url)

    def _fetch_fixtures(self) -> dict | None:
        url = f"https://www.fotmob.com/leagues/{self.league_id}?season={self.season}"
        return fetch_nextjs_data(url)

    def _parse_matches(self, matches_data: dict) -> list[dict]:
        """Transform raw FotMob fixture entries into a flat, typed list."""
        result = []
        fixtures = matches_data.get("fixtures", {})
        all_m = fixtures.get("allMatches", [])
        for m in all_m:
            status = m.get("status", {})
            score_raw = status.get("scoreStr")
            result.append({
                "id":        str(m.get("id", "")),
                "home":      m.get("home", {}).get("name", "TBD"),
                "away":      m.get("away", {}).get("name", "TBD"),
                "finished":  bool(status.get("finished", False)),
                "started":   bool(status.get("started", False)),
                "score_str": score_raw if score_raw else "vs",
                "utc_time":  status.get("utcTime", ""),
                "page_url":  m.get("pageUrl", ""),
                "round":     m.get("roundId", ""),
            })
        return result

    def load_data(self) -> bool:
        """
        Concurrently fetch overview + fixtures using a thread pool
        (asyncio event loop runs both urllib calls in parallel).
        """
        print(col("🔄  Loading World Cup data from FotMob …", C.CYAN))

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_overview  = pool.submit(self._fetch_overview)
            fut_fixtures  = pool.submit(self._fetch_fixtures)
            self.overview_data = fut_overview.result()
            self.matches_data  = fut_fixtures.result()

        if self.matches_data:
            self.matches_list = self._parse_matches(self.matches_data)
        else:
            self.matches_list = []

        if self.overview_data is None and self.matches_data is None:
            return False
        return True

    def refresh_data(self) -> None:
        """Re-fetch all data and clear the match cache."""
        self._match_cache.clear()
        self.load_data()
        print(col("✅  Data refreshed.", C.BGREEN))
        input("\nPress Enter to continue…")

    # ------------------------------------------------------------------
    # Match detail fetching (with cache)
    # ------------------------------------------------------------------

    def _fetch_match_props(self, match: dict) -> dict | None:
        mid = match["id"]
        if mid in self._match_cache:
            return self._match_cache[mid]

        slug = match["page_url"]
        if "#" in slug:
            slug = slug.split("#")[0]
        if not slug:
            return None

        url = f"https://www.fotmob.com{slug}"
        print(col(f"🔄  Loading match details for {match['home']} vs {match['away']} …", C.CYAN))
        props = fetch_nextjs_data(url)
        if props:
            self._match_cache[mid] = props
        return props

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    def show_standings(self) -> None:
        if not self.overview_data:
            print(col("❌  No standings data available.", C.RED))
            input("\nPress Enter to return…")
            return

        tables = (
            self.overview_data
            .get("table", [{}])[0]
            .get("data", {})
            .get("tables", [])
        )
        if not tables:
            print(col("❌  No group tables found. The tournament may not have started yet.", C.YELLOW))
            input("\nPress Enter to return…")
            return

        print(f"\n{header_line(f'🏆  FIFA World Cup {self.season} — Group Standings', 60)}\n")

        for t in tables:
            league_name = t.get("leagueName", "Group")
            group_letter = league_name.split()[-1] if league_name.split() else ""

            # Skip non-group pseudo-tables
            if len(group_letter) != 1 or not group_letter.isalpha():
                continue
            # Apply --group filter if set
            if self.group_filter and group_letter.upper() != self.group_filter:
                continue

            print(col(f"  🔹 {league_name}", C.BOLD, C.CYAN))
            hdr = f"  {'':>2}  {'Team':<22}  {'Pld':>3}  {'W':>2}  {'D':>2}  {'L':>2}  {'GD':>3}  {'Pts':>3}"
            print(col(hdr, C.DIM))
            print(col("  " + "─" * 52, C.DIM))

            rows = t.get("table", {}).get("all", [])
            for row in rows:
                idx  = row.get("idx", "-")
                name = row.get("name") or row.get("shortName") or "TBD"
                pld  = row.get("p", 0)
                w    = row.get("w", 0)
                d    = row.get("d", 0)
                l    = row.get("l", 0)
                gd   = row.get("goalConDiff", 0)
                pts  = row.get("pts", 0)
                gd_str = f"+{gd}" if gd > 0 else str(gd)

                # Highlight top 2 (qualification spots)
                rank_col = C.BGREEN if idx <= 2 else C.WHITE
                pts_col  = C.BOLD if idx <= 2 else ""
                print(
                    col(f"  {idx:>2}", rank_col)
                    + f"  {name:<22}  {pld:>3}  {w:>2}  {d:>2}  {l:>2}  "
                    + col(f"{gd_str:>3}", C.BGREEN if gd > 0 else (C.RED if gd < 0 else C.DIM))
                    + "  "
                    + col(f"{pts:>3}", pts_col + rank_col)
                )
            print()

        input(col("  Press Enter to return to main menu…", C.DIM))

    # ------------------------------------------------------------------
    # Match list (with live filter + pagination + team search)
    # ------------------------------------------------------------------

    def _filter_matches(
        self,
        mode: str,           # 'finished' | 'live' | 'upcoming'
        team_query: str = "",
    ) -> list[dict]:
        results = []
        q = team_query.strip().lower()
        for m in self.matches_list:
            cls = classify_match(m)
            # Map 'upcoming' to include both 'upcoming' and 'live' for the combined view
            if mode == "upcoming_live":
                if cls not in ("upcoming", "live"):
                    continue
            elif cls != mode:
                continue
            if q and q not in m["home"].lower() and q not in m["away"].lower():
                continue
            results.append(m)
        results.sort(key=lambda x: x["utc_time"])
        return results

    def show_matches(self, mode: str = "finished") -> None:
        """
        Paginated match browser. mode = 'finished' | 'live' | 'upcoming_live'
        """
        LABELS = {
            "finished":      "Finished Matches",
            "live":          "Live Now",
            "upcoming_live": "Upcoming & Live Matches",
        }
        label = LABELS.get(mode, "Matches")
        team_query = ""
        page = 0

        while True:
            filtered = self._filter_matches(mode, team_query)
            page_items, total_pages, page = paginate(filtered, page)
            offset = page * PAGE_SIZE

            title = f"📅  {label}"
            if team_query:
                title += f'  [filter: "{team_query}"]'
            print(f"\n{header_line(title, 60)}\n")

            if not page_items:
                if team_query:
                    print(col(f'  No matches found for "{team_query}".', C.YELLOW))
                else:
                    print(col("  No matches in this category yet.", C.DIM))
            else:
                for i, m in enumerate(page_items):
                    num   = col(f"  [{offset + i + 1:>3}]", C.DIM)
                    cls   = classify_match(m)
                    tstr  = format_kickoff(m["utc_time"]) if m["utc_time"] else ""
                    home  = col(f"{m['home']:<22}", C.WHITE)
                    away  = col(f"{m['away']:<22}", C.WHITE)
                    score = score_display(m)
                    badge = f"  {live_badge()}" if cls == "live" else ""
                    print(f"{num}  {col(tstr, C.DIM):<22}  {home}  {score}  {away}{badge}")

            # Pagination footer
            if total_pages > 1:
                pg_info = col(f"  Page {page + 1} / {total_pages}", C.DIM)
                nav = ""
                if page > 0:
                    nav += col("  [P] Prev", C.CYAN)
                if page < total_pages - 1:
                    nav += col("  [N] Next", C.CYAN)
                print(f"\n{pg_info}{nav}")

            print(col("\n  Options:", C.DIM))
            print(col("    [number]  Open Match Center", C.DIM))
            print(col("    [/]       Search by team name", C.DIM))
            if team_query:
                print(col("    [C]       Clear search", C.DIM))
            if total_pages > 1:
                print(col("    [P/N]     Prev / Next page", C.DIM))
            print(col("    [B]       Back to main menu", C.DIM))

            choice = input(col("\n  → ", C.CYAN)).strip().lower()

            if choice == "b":
                break
            elif choice == "n" and page < total_pages - 1:
                page += 1
            elif choice == "p" and page > 0:
                page -= 1
            elif choice == "/":
                team_query = input(col("  Search team name: ", C.CYAN)).strip()
                page = 0
            elif choice == "c":
                team_query = ""
                page = 0
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(filtered):
                        self.show_match_center(filtered[idx])
                    else:
                        print(col("  ❌  Number out of range.", C.RED))
                except ValueError:
                    print(col("  ❌  Invalid input.", C.RED))

    # ------------------------------------------------------------------
    # Match Center
    # ------------------------------------------------------------------

    def show_match_center(self, match: dict) -> None:
        props = self._fetch_match_props(match)
        if not props:
            print(col("  ❌  Failed to fetch match details.", C.RED))
            input("\nPress Enter to continue…")
            return

        while True:
            header  = props.get("header", {})
            status  = header.get("status", {})
            score   = status.get("scoreStr") or "vs"
            cls     = classify_match(match)

            title = f"🏟  {match['home']}  {score}  {match['away']}"
            print(f"\n{header_line(title, 60)}\n")

            # Status line
            if cls == "live":
                print(f"  {live_badge()}  In Progress")
            elif cls == "finished":
                print(col("  ✅  Full Time", C.BGREEN))
            else:
                kt = format_kickoff(match["utc_time"]) if match["utc_time"] else "TBD"
                print(col(f"  🕐  Kick-off: {kt} UTC", C.DIM))

            # Venue / referee
            info_box = safe_get(props, "content", "matchFacts", "infoBox", default={})
            venue = safe_get(info_box, "Stadium", "name", default=None)
            referee = safe_get(info_box, "Referee", "text", default=None)
            if venue:
                print(col(f"  🏟  Venue: {venue}", C.DIM))
            if referee:
                print(col(f"  👤  Referee: {referee}", C.DIM))

            print(f"\n  {col('[1]', C.CYAN)}  Team Statistics")
            print(f"  {col('[2]', C.CYAN)}  Timeline / Key Events")
            print(f"  {col('[3]', C.CYAN)}  Lineups")
            if cls == "live":
                print(f"  {col('[R]', C.BYELLOW)}  Refresh this match")
            print(f"  {col('[B]', C.DIM)}  Back to match list")

            choice = input(col("\n  → ", C.CYAN)).strip().lower()

            if choice == "b":
                break
            elif choice == "r" and cls == "live":
                # Evict cache entry and re-fetch
                self._match_cache.pop(match["id"], None)
                props = self._fetch_match_props(match)
                if not props:
                    print(col("  ❌  Refresh failed.", C.RED))
                    input("\nPress Enter to continue…")
                    break
            elif choice == "1":
                self._show_stats(props, status, match)
            elif choice == "2":
                self._show_timeline(props, status)
            elif choice == "3":
                self._show_lineups(props, match)

    def _show_stats(self, props: dict, status: dict, match: dict) -> None:
        stats_list = safe_get(props, "content", "stats", "Periods", "All", "stats", default=[])

        print(f"\n{header_line('📈  Match Statistics', 54)}\n")

        if not stats_list:
            if not status.get("started"):
                print(col("  Statistics will be available at kick-off.", C.DIM))
            else:
                print(col("  No statistics recorded for this match.", C.DIM))
            input("\n  Press Enter to continue…")
            return

        home_label = col(f"  {match['home'][:18]:<18}", C.BCYAN)
        away_label = col(f"  {match['away'][:18]}", C.BYELLOW)
        print(f"  {'Stat':<26}  {home_label}  {away_label}")
        print(col("  " + "─" * 60, C.DIM))

        for cat in stats_list:
            print(col(f"\n  {cat.get('title', '').upper()}", C.BOLD, C.DIM))
            for item in cat.get("stats", []):
                title    = item.get("title", "")
                vals     = item.get("stats", [None, None])
                home_val = vals[0] if len(vals) > 0 else None
                away_val = vals[1] if len(vals) > 1 else None
                home_str = "" if home_val is None else str(home_val)
                away_str = "" if away_val is None else str(away_val)
                if not home_str and not away_str:
                    continue

                # Color advantage: higher is better for most stats
                try:
                    hv = float(str(home_val).replace("%", ""))
                    av = float(str(away_val).replace("%", ""))
                    hc = C.BGREEN if hv > av else (C.RED if hv < av else C.WHITE)
                    ac = C.BGREEN if av > hv else (C.RED if av < hv else C.WHITE)
                except (TypeError, ValueError):
                    hc = ac = C.WHITE

                print(
                    f"  {title:<26}  "
                    + col(f"{home_str:>8}", hc)
                    + "    "
                    + col(f"{away_str:<8}", ac)
                )

        input(col("\n  Press Enter to continue…", C.DIM))

    def _show_timeline(self, props: dict, status: dict) -> None:
        events = safe_get(props, "content", "matchFacts", "events", "events", default=[])

        print(f"\n{header_line('⏱  Match Timeline', 54)}\n")

        if not events:
            if not status.get("started"):
                print(col("  Timeline events will appear here once the match kicks off.", C.DIM))
            else:
                print(col("  No events recorded for this match.", C.DIM))
            input("\n  Press Enter to continue…")
            return

        SKIP_TYPES = {"HALF", "ADDEDTIME", "PERIOD", "MATCHEND"}

        sorted_events = sorted(
            (e for e in events if e.get("type", "").upper() not in SKIP_TYPES),
            key=lambda e: (e.get("time", 0), e.get("overloadTime", 0)),
            reverse=True,
        )

        for event in sorted_events:
            etype    = event.get("type", "event").upper()
            minute   = event.get("time", 0)
            added    = event.get("overloadTime", 0)
            own_goal = bool(event.get("ownGoal"))
            card     = event.get("card", "")

            # Build minute string
            min_str = f"{minute}'" + (f"+{added}" if added else "")

            # Build player / description
            if etype == "SUBSTITUTION":
                swap = event.get("swap") or []
                if len(swap) >= 2:
                    p_in  = swap[0].get("name", "TBD")
                    p_out = swap[1].get("name", "TBD")
                else:
                    p_in  = event.get("player", {}).get("name") or "TBD"
                    p_out = "TBD"
                desc = (
                    col(f"▲ {p_in}", C.BGREEN)
                    + col("  ▼ ", C.DIM)
                    + col(p_out, C.RED)
                )
            else:
                player = (
                    event.get("player", {}).get("name")
                    or event.get("nameStr")
                    or "Unknown"
                )
                desc = col(player, C.WHITE)
                if own_goal:
                    desc += col("  (Own Goal)", C.RED)
                elif card:
                    desc += col(f"  ({card})", C.YELLOW)

            icon = event_icon(etype, own_goal, card)
            print(
                f"  {col(min_str, C.DIM):<18}  "
                + f"{icon}  "
                + f"{desc}"
            )

        input(col("\n  Press Enter to continue…", C.DIM))

    def _show_lineups(self, props: dict, match: dict) -> None:
        home_lu = safe_get(props, "content", "lineup", "homeTeam", "starters", default=[])
        away_lu = safe_get(props, "content", "lineup", "awayTeam", "starters", default=[])
        home_subs = safe_get(props, "content", "lineup", "homeTeam", "subs", default=[])
        away_subs = safe_get(props, "content", "lineup", "awayTeam", "subs", default=[])

        print(f"\n{header_line('👥  Lineups', 54)}\n")

        if not home_lu and not away_lu:
            print(col("  Lineups have not been released yet.", C.DIM))
            input("\n  Press Enter to continue…")
            return

        home_hdr = col(f"  {match['home'][:28]:<28}", C.BCYAN, C.BOLD)
        away_hdr = col(f"  {match['away'][:28]}", C.BYELLOW, C.BOLD)
        print(f"  {'#':>3}  {'Home Team':<26}    {'#':>3}  Away Team")
        print(col("  " + "─" * 60, C.DIM))

        max_len = max(len(home_lu), len(away_lu))
        for i in range(max_len):
            if i < len(home_lu):
                p = home_lu[i]
                h = col(f"  {p.get('jersey', ''):>2}  {p.get('name', ''):<26}", C.BCYAN)
            else:
                h = " " * 32

            if i < len(away_lu):
                p = away_lu[i]
                a = col(f"  {p.get('jersey', ''):>2}  {p.get('name', '')}", C.BYELLOW)
            else:
                a = ""

            print(f"{h}    {a}")

        if home_subs or away_subs:
            print(col(f"\n  {'Substitutes':^60}", C.DIM, C.BOLD))
            print(col("  " + "─" * 60, C.DIM))
            max_subs = max(len(home_subs), len(away_subs))
            for i in range(max_subs):
                if i < len(home_subs):
                    p = home_subs[i]
                    h = col(f"  {p.get('jersey', ''):>2}  {p.get('name', ''):<26}", C.DIM)
                else:
                    h = " " * 32
                if i < len(away_subs):
                    p = away_subs[i]
                    a = col(f"  {p.get('jersey', ''):>2}  {p.get('name', '')}", C.DIM)
                else:
                    a = ""
                print(f"{h}    {a}")

        input(col("\n  Press Enter to continue…", C.DIM))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        ok = self.load_data()
        if not ok:
            print(col("\n❌  Failed to load World Cup data. Check your connection and try again.", C.RED))
            sys.exit(1)

        live_count = sum(1 for m in self.matches_list if classify_match(m) == "live")

        while True:
            print(f"\n{header_line(f'🏆  FIFA World Cup {self.season}  —  Interactive Terminal', 62)}\n")

            if live_count:
                print(col(f"  {live_badge()}  {live_count} match{'es' if live_count != 1 else ''} in progress\n", C.BGREEN))

            print(f"  {col('[1]', C.CYAN)}  Group Standings")
            print(f"  {col('[2]', C.CYAN)}  Finished Matches")
            print(f"  {col('[3]', C.CYAN)}  Upcoming & Live Matches")
            if live_count:
                print(f"  {col('[4]', C.BGREEN)}  Live Matches Only")
            print(f"  {col('[R]', C.BYELLOW)}  Refresh Data")
            print(f"  {col('[Q]', C.DIM)}  Quit")

            choice = input(col("\n  → ", C.CYAN)).strip().lower()

            if choice == "q":
                print(col("\n  Goodbye! ⚽\n", C.DIM))
                break
            elif choice == "1":
                self.show_standings()
            elif choice == "2":
                self.show_matches(mode="finished")
            elif choice == "3":
                self.show_matches(mode="upcoming_live")
            elif choice == "4" and live_count:
                self.show_matches(mode="live")
            elif choice == "r":
                self.refresh_data()
                live_count = sum(1 for m in self.matches_list if classify_match(m) == "live")
            else:
                print(col("  ❌  Invalid choice.", C.RED))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="interactive_world_cup.py",
        description="FIFA World Cup Interactive Terminal — powered by FotMob",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python interactive_world_cup.py\n"
            "  python interactive_world_cup.py --season 2022\n"
            "  python interactive_world_cup.py --season 2026 --group A\n"
        ),
    )
    parser.add_argument(
        "--season",
        default="2026",
        metavar="YEAR",
        help="World Cup season year (default: 2026). Use 2022 for Qatar.",
    )
    parser.add_argument(
        "--group",
        default=None,
        metavar="LETTER",
        help="Filter standings to a single group, e.g. --group A",
    )
    # Positional for backwards compat: `python script.py 2022`
    parser.add_argument(
        "season_positional",
        nargs="?",
        default=None,
        metavar="YEAR",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    season = args.season_positional or args.season

    app = WorldCupApp(season=season, group_filter=args.group)
    app.run()


if __name__ == "__main__":
    main()
