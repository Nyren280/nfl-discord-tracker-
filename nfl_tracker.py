import os
import requests

TEAMS = {
    "NO": {
        "webhook": os.getenv("DISCORD_WEBHOOK_SAINTS"),
        "role_id": os.getenv("DISCORD_ROLE_SAINTS"),
        "color": 13408563,  # Gold
        "name": "New Orleans Saints",
        "alt_name": "New Orleans Saints"
    },
    "CAR": {
        "webhook": os.getenv("DISCORD_WEBHOOK_PANTHERS"),
        "role_id": os.getenv("DISCORD_ROLE_PANTHERS"),
        "color": 15403,     # Panther Blue
        "name": "Carolina Panthers",
        "alt_name": "Carolina Panthers"
    }
}

PRIMARY_ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
FALLBACK_SPORTSDB_URL = "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=today&s=American_Football"

def fetch_espn_data():
    """Primary fetcher: ESPN API"""
    print("Fetching scores from primary source (ESPN)...")
    res = requests.get(PRIMARY_ESPN_URL, timeout=8)
    if res.status_code != 200:
        raise Exception(f"ESPN returned HTTP {res.status_code}")
    
    data = res.json()
    events = data.get("events", [])
    updates = []
    
    for event in events:
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        competitors = competitions[0].get("competitors", [])
        
        for team in competitors:
            abbrev = team.get("team", {}).get("abbreviation")
            if abbrev in TEAMS:
                home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                away = next((c for c in competitors if c.get("homeAway") == "away"), {})
                status = event.get("status", {}).get("type", {}).get("detail", "Scheduled")
                
                updates.append({
                    "abbrev": abbrev,
                    "away_name": away.get('team', {}).get('displayName', 'Away'),
                    "away_score": away.get('score', '0'),
                    "home_name": home.get('team', {}).get('displayName', 'Home'),
                    "home_score": home.get('score', '0'),
                    "status": status,
                    "source": "ESPN API"
                })
    return updates

def fetch_sportsdb_fallback():
    """Secondary fetcher: TheSportsDB"""
    print("⚠️ Primary API down or empty. Swapping to fallback (TheSportsDB)...")
    res = requests.get(FALLBACK_SPORTSDB_URL, timeout=8)
    if res.status_code != 200:
        raise Exception(f"TheSportsDB returned HTTP {res.status_code}")
        
    data = res.json()
    events = data.get("events") or []
    updates = []
    
    for event in events:
        home_team = event.get("strHomeTeam", "")
        away_team = event.get("strAwayTeam", "")
        
        for abbrev, cfg in TEAMS.items():
            if cfg["alt_name"] in [home_team, away_team]:
                updates.append({
                    "abbrev": abbrev,
                    "away_name": away_team,
                    "away_score": event.get("intAwayScore", "0") or "0",
                    "home_name": home_team,
                    "home_score": event.get("intHomeScore", "0") or "0",
                    "status": event.get("strStatus", "Scheduled"),
                    "source": "TheSportsDB (Fallback)"
                })
    return updates

def send_discord_update(update):
    cfg = TEAMS[update["abbrev"]]
    if not cfg["webhook"]:
        print(f"Skipping {update['abbrev']} — missing Webhook URL.")
        return
        
    role_ping = f"<@&{cfg['role_id']}>" if cfg["role_id"] else ""
    payload = {
        "content": role_ping,
        "allowed_mentions": {"roles": [cfg["role_id"]] if cfg["role_id"] else []},
        "embeds": [{
            "title": f"🏈 {cfg['name']} Game Update",
            "color": cfg["color"],
            "fields": [
                {
                    "name": "Matchup",
                    "value": f"**{update['away_name']}** @ **{update['home_name']}**",
                    "inline": False
                },
                {
                    "name": "Score",
                    "value": f"{update['away_name']}: **{update['away_score']}** | {update['home_name']}: **{update['home_score']}**",
                    "inline": True
                },
                {
                    "name": "Status",
                    "value": update["status"],
                    "inline": True
                }
            ],
            "footer": {"text": f"Automated Live Tracker • Source: {update['source']}"}
        }]
    }
    
    res = requests.post(cfg["webhook"], json=payload)
    print(f"Sent update for {update['abbrev']} via {update['source']}. HTTP {res.status_code}")

def run():
    updates = []
    
    # Try ESPN first
    try:
        updates = fetch_espn_data()
    except Exception as e:
        print(f"ESPN API Failed: {e}")
        
    # If ESPN returned no game updates or hit an exception, fall back to TheSportsDB
    if not updates:
        try:
            updates = fetch_sportsdb_fallback()
        except Exception as e:
            print(f"Fallback API also failed: {e}")

    # Post to Discord if any updates were retrieved
    if updates:
        for update in updates:
            send_discord_update(update)
    else:
        print("No active games found for Saints or Panthers on either API.")

if __name__ == "__main__":
    run()
