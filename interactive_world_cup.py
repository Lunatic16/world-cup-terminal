#!/usr/bin/env python3
import json
import re
import sys
import urllib.request
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def fetch_nextjs_data(url):
    """Fetches a URL and extracts the __NEXT_DATA__ script tag payload."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"\n❌ HTTP request failed: {e}")
        return None

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        print("\n❌ Could not find __NEXT_DATA__ in HTML response.")
        return None

    try:
        data = json.loads(match.group(1))
        return data.get("props", {}).get("pageProps", {})
    except Exception as e:
        print(f"\n❌ Failed to parse JSON payload: {e}")
        return None

def safe_get(obj, *keys, default=None):
    """Safely retrieves a nested value from a dictionary, returning default if any key is missing or None."""
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
        if obj is None:
            return default
    return obj

class WorldCupApp:
    def __init__(self, season="2026"):
        self.season = season
        self.league_id = 77  # World Cup
        self.overview_data = None
        self.matches_data = None
        self.matches_list = []

    def load_data(self):
        """Loads both the overview (for standings) and league fixtures (for matches)."""
        print("🔄 Loading World Cup data from FotMob (please wait)...")
        
        # Load standings & overview
        overview_url = f"https://www.fotmob.com/leagues/{self.league_id}/overview/world-cup?season={self.season}"
        self.overview_data = fetch_nextjs_data(overview_url)

        # Load all matches
        matches_url = f"https://www.fotmob.com/leagues/{self.league_id}?season={self.season}"
        self.matches_data = fetch_nextjs_data(matches_url)

        # Flatten matches
        self.matches_list = []
        if self.matches_data:
            fixtures = self.matches_data.get("fixtures", {})
            all_m = fixtures.get("allMatches", [])
            for m in all_m:
                self.matches_list.append({
                    "id": m.get("id"),
                    "home": m.get("home", {}).get("name", "TBD"),
                    "away": m.get("away", {}).get("name", "TBD"),
                    "finished": m.get("status", {}).get("finished", False),
                    "started": m.get("status", {}).get("started", False),
                    "score_str": m.get("status", {}).get("scoreStr", "vs"),
                    "utc_time": m.get("status", {}).get("utcTime", ""),
                    "page_url": m.get("pageUrl", "")
                })

        return self.overview_data is not None

    def show_standings(self):
        """Displays all group standings."""
        if not self.overview_data:
            print("❌ No standings data available.")
            return

        tables = self.overview_data.get("table", [{}])[0].get("data", {}).get("tables", [])
        if not tables:
            print("❌ No standings groups found.")
            return

        print(f"\n==============================================")
        print(f"🏆 FIFA World Cup {self.season} Group Standings")
        print(f"==============================================")

        for t in tables:
            league_name = t.get("leagueName", "Group")
            # Verify it's a valid group letter and not a pseudo-table
            group_letter = league_name.split()[-1] if len(league_name.split()) > 0 else ""
            if len(group_letter) != 1 or not group_letter.isalpha():
                continue

            print(f"\n🔹 {league_name}")
            print(f"  {'Pos Team':<22} | Pld | W | D | L | GD | Pts")
            print("  " + "-" * 48)
            for row in t.get("table", {}).get("all", []):
                idx = row.get("idx", "-")
                name = row.get("name") or row.get("shortName") or "TBD"
                pld = row.get("p", 0)
                w = row.get("w", 0)
                d = row.get("d", 0)
                l = row.get("l", 0)
                gd = row.get("goalConDiff", 0)
                pts = row.get("pts", 0)
                
                team_display = f"{idx} {name}"
                print(f"  {team_display:<22} | {pld:3d} | {w:1d} | {d:1d} | {l:1d} | {gd:2d} | {pts:3d}")
        
        input("\nPress Enter to return to main menu...")

    def show_matches(self, finished_only=True):
        """Lists matches and allows entering the Match Center for a selected game."""
        filtered = [m for m in self.matches_list if m["finished"] == finished_only]
        
        # Sort by kickoff time
        filtered.sort(key=lambda x: x["utc_time"])

        status_label = "Finished" if finished_only else "Upcoming/Live"
        
        while True:
            print(f"\n==============================================")
            print(f"📅 {status_label} Matches ({len(filtered)} found)")
            print(f"==============================================")
            
            for idx, m in enumerate(filtered):
                time_str = ""
                if m["utc_time"]:
                    try:
                        dt = datetime.strptime(m["utc_time"], "%Y-%m-%dT%H:%M:%S.%fZ")
                        time_str = dt.strftime("%b %d, %H:%M")
                    except:
                        time_str = m["utc_time"][:16]

                print(f"  [{idx + 1}] {time_str:<12} | {m['home']:<20} {m['score_str']} {m['away']:<20}")

            print("\nOptions:")
            print("  [Number] Open match center for details/stats")
            print("  [B] Return to main menu")
            
            choice = input("\nSelect an option: ").strip().lower()
            if choice == 'b':
                break
            
            try:
                match_idx = int(choice) - 1
                if 0 <= match_idx < len(filtered):
                    self.show_match_center(filtered[match_idx])
                else:
                    print("❌ Invalid number.")
            except ValueError:
                print("❌ Invalid input.")

    def show_match_center(self, match):
        """Displays real-time stats and events for a selected match in a sub-menu."""
        # Clean fragment URL if any
        slug = match["page_url"]
        if "#" in slug:
            slug = slug.split("#")[0]

        if not slug:
            print("❌ Match URL slug is not available.")
            input("Press Enter to continue...")
            return

        url = f"https://www.fotmob.com{slug}"
        print(f"\n🔄 Loading Match Details for {match['home']} vs {match['away']}...")
        
        props = fetch_nextjs_data(url)
        if not props:
            print("❌ Failed to fetch match details.")
            input("Press Enter to continue...")
            return

        while True:
            general = props.get("general", {})
            header = props.get("header", {})
            status = header.get("status", {})
            score = status.get("scoreStr", "vs")
            
            print(f"\n==============================================")
            print(f"🏟 MATCH CENTER: {match['home']} {score} {match['away']}")
            print(f"==============================================")
            print(f"Status: Finished={status.get('finished')}, Started={status.get('started')}")
            print(f"Venue: {props.get('content', {}).get('matchFacts', {}).get('infoBox', {}).get('Stadium', {}).get('name', 'N/A')}")
            if props.get('content', {}).get('matchFacts', {}).get('infoBox', {}).get('Referee'):
                ref = props.get('content', {}).get('matchFacts', {}).get('infoBox', {}).get('Referee', {}).get('text')
                print(f"Referee: {ref}")

            print("\n1. View Team Statistics")
            print("2. View Timeline / Key Events")
            print("3. View Lineups")
            print("B. Back to match list")

            choice = input("\nChoose a menu option: ").strip().lower()
            if choice == 'b':
                break
            elif choice == '1':
                stats_list = safe_get(props, "content", "stats", "Periods", "All", "stats", default=[])
                if not stats_list:
                    if not status.get("started"):
                        print("\n📈 Match has not started yet. Statistics will be available at kickoff.")
                    else:
                        print("\n📈 No statistics available for this match.")
                else:
                    print("\n📈 Match Statistics:")
                    for cat in stats_list:
                        print(f"\n  🔹 {cat.get('title')}")
                        for item in cat.get("stats", []):
                            title = item.get("title", "")
                            home_val = item.get("stats", [None, None])[0]
                            away_val = item.get("stats", [None, None])[1]
                            home_str = "" if home_val is None else str(home_val)
                            away_str = "" if away_val is None else str(away_val)
                            if home_str == "" and away_str == "":
                                continue
                            print(f"    {title:<24}: {home_str:>5} vs {away_str:<5}")
                input("\nPress Enter to continue...")
            elif choice == '2':
                events = safe_get(props, "content", "matchFacts", "events", "events", default=[])
                if not events:
                    if not status.get("started"):
                        print("\n⏱ Match has not started yet. Timeline events will appear here once the match kicks off.")
                    else:
                        print("\n⏱ No events recorded for this match.")
                else:
                    print("\n⏱ Match Timeline (Most recent first):")
                    for event in sorted(events, key=lambda e: e.get("time", 0), reverse=True):
                        event_type = event.get("type", "Event").upper()
                        
                        # Skip utility/formatting markers
                        if event_type in ("HALF", "ADDEDTIME"):
                            continue
                            
                        minute = event.get("time", 0)
                        player = event.get("player", {}).get("name") or event.get("nameStr") or "Someone"
                        
                        # Add descriptive details if present (like Own Goal, card type, sub info)
                        extra = ""
                        if event.get("ownGoal"):
                            extra = " (OWN GOAL)"
                        elif event.get("card"):
                            extra = f" ({event.get('card')})"
                        elif event_type == "SUBSTITUTION":
                            swap = event.get("swap", [])
                            if len(swap) >= 2:
                                player_in = swap[0].get("name", "TBD")
                                player_out = swap[1].get("name", "TBD")
                            else:
                                player_in = "TBD"
                                player_out = "TBD"
                            extra = f" (IN: {player_in} | OUT: {player_out})"
                            player = ""
                            
                        print(f"  {minute:3d}' [{event_type}] {player}{extra}")
                input("\nPress Enter to continue...")
            elif choice == '3':
                home_lu = safe_get(props, "content", "lineup", "homeTeam", "starters", default=[])
                away_lu = safe_get(props, "content", "lineup", "awayTeam", "starters", default=[])
                
                if not home_lu and not away_lu:
                    print("\n👥 Lineups not released yet.")
                else:
                    print(f"\n👥 Lineups:")
                    print(f"  {'Home: ' + match['home']:<30} | {'Away: ' + match['away']:<30}")
                    print("  " + "-" * 63)
                    max_len = max(len(home_lu), len(away_lu))
                    for i in range(max_len):
                        p_home = f"{home_lu[i].get('name', '')} ({home_lu[i].get('jersey', '')})" if i < len(home_lu) else ""
                        p_away = f"{away_lu[i].get('name', '')} ({away_lu[i].get('jersey', '')})" if i < len(away_lu) else ""
                        print(f"  {p_home:<30} | {p_away:<30}")
                input("\nPress Enter to continue...")

    def run(self):
        if not self.load_data():
            print("❌ Failed to load World Cup data.")
            return

        while True:
            print(f"\n==============================================")
            print(f"🏆 FIFA WORLD CUP {self.season} INTERACTIVE TERMINAL")
            print(f"==============================================")
            print("  [1] View Group Standings (Groups A–L)")
            print("  [2] View Finished Matches (Results & Stats)")
            print("  [3] View Upcoming/Live Matches")
            print("  [Q] Exit Application")
            
            choice = input("\nSelect menu option: ").strip().lower()
            if choice == 'q':
                print("Goodbye!")
                break
            elif choice == '1':
                self.show_standings()
            elif choice == '2':
                self.show_matches(finished_only=True)
            elif choice == '3':
                self.show_matches(finished_only=False)
            else:
                print("❌ Invalid choice.")

if __name__ == "__main__":
    # Standard season is 2022 (Qatar) or 2026 (Upcoming)
    season = "2026"
    if len(sys.argv) > 1:
        season = sys.argv[1]
    
    app = WorldCupApp(season)
    app.run()
