import os
import json
import requests

# ── CACHE STATE FILE SETUP ────────────────────────────────────
CACHE_FILE = "sent_scores.json"

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as f:
            sent_games = json.load(f)
    except Exception as e:
        print(f"⚠️ Error reading cache file: {e}. Starting fresh.")
        sent_games = {}
else:
    sent_games = {}

# ── TEAM CONFIGURATION ────────────────────────────────────────
TEAMS = {
    "NO": {
        "webhook": os.getenv("DISCORD_WEBHOOK_NO"),
        "role_id": os.getenv("DISCORD_ROLE_NO"),
        "color": 13408563,  # Gold
        "name": "New Orleans Saints"
    },
    "CAR": {
        "webhook": os.getenv("DISCORD_WEBHOOK_CAR"),
        "role_id": os.getenv("DISCORD_ROLE_CAR"),
        "color": 15403,     # Blue/Black
        "name": "Carolina Panthers"
    }
}

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


def fetch_and_process_scores():
    try:
        response = requests.get(ESPN_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Failed to fetch ESPN data: {e}")
        return

    events = data.get("events", [])
    if not events:
        print("ℹ️ No NFL events found in feed.")
        return

    cache_updated = False

    for event in events:
        game_id = event.get("id")
        status_data = event.get("status", {}).get("type", {})
        status_name = status_data.get("name", "")  # e.g., "STATUS_FINAL"
        status_detail = status_data.get("detail", "Final")  # e.g., "Final" or "Final/OT"

        # We only want to trigger automatic updates for finished games
        if status_name != "STATUS_FINAL":
            continue

        competitors = event.get("competitions", [{}])[0].get("competitors", [])
        if not competitors:
            continue

        # Extract team abbreviation, score, and home/away status
        team_data = {}
        for comp in competitors:
            abbrev = comp.get("team", {}).get("abbreviation")
            score = comp.get("score", "0")
            home_away = comp.get("homeAway")
            team_data[abbrev] = {"score": score, "homeAway": home_away}

        # Check if any configured team played in this game
        for team_code, team_info in TEAMS.items():
            if team_code in team_data:
                webhook_url = team_info["webhook"]
                if not webhook_url:
                    print(f"⚠️ Webhook missing for {team_code}. Skipping.")
                    continue

                # Unique key per team, game ID, and status state
                cache_key = f"{team_code}_{game_id}_{status_name}"

                # 🛑 DUP GUARD: Skip if already posted to Discord
                if sent_games.get(cache_key):
                    print(f"⏩ Skipping {cache_key} — score update already sent.")
                    continue

                # Identify opponent
                opponent_code = [k for k in team_data.keys() if k != team_code]
                opponent_str = opponent_code[0] if opponent_code else "OPP"

                # Build Matchup Title (e.g. CAR @ BUF or JAX @ NO)
                if team_data[team_code]["homeAway"] == "home":
                    matchup_str = f"{opponent_str} @ {team_code}"
                else:
                    matchup_str = f"{team_code} @ {opponent_str}"

                # Build Score Line (e.g. CAR: 14 | BUF: 29)
                away_team = next((k for k, v in team_data.items() if v["homeAway"] == "away"), team_code)
                home_team = next((k for k, v in team_data.items() if v["homeAway"] == "home"), opponent_str)
                score_str = f"{away_team}: **{team_data.get(away_team, {}).get('score', '0')}** | {home_team}: **{team_data.get(home_team, {}).get('score', '0')}**"

                role_ping = f"<@&{team_info['role_id']}>" if team_info.get("role_id") else ""

                payload = {
                    "username": f"{team_info['name']} Bot",
                    "content": role_ping,
                    "allowed_mentions": {"roles": [team_info["role_id"]] if team_info.get("role_id") else []},
                    "embeds": [
                        {
                            "title": f"🏈 {team_info['name']} Game Update",
                            "color": team_info["color"],
                            "fields": [
                                {"name": "Matchup", "value": matchup_str, "inline": False},
                                {"name": "Score", "value": score_str, "inline": False},
                                {"name": "Status", "value": status_detail, "inline": False}
                            ],
                            "footer": {"text": "Automated NFL Live Score Tracker"}
                        }
                    ]
                }

                # Send Webhook
                try:
                    res = requests.post(webhook_url, json=payload, timeout=10)
                    if res.status_code in [200, 204]:
                        print(f"✅ Posted update for {cache_key}")
                        sent_games[cache_key] = True
                        cache_updated = True
                    else:
                        print(f"❌ Discord error {res.status_code}: {res.text}")
                except Exception as post_err:
                    print(f"🚨 Failed to send webhook: {post_err}")

    # Write updated cache to file if new scores were posted
    if cache_updated:
        with open(CACHE_FILE, "w") as f:
            json.dump(sent_games, f, indent=2)
        print("💾 Saved sent_scores.json cache.")


if __name__ == "__main__":
    fetch_and_process_scores()
