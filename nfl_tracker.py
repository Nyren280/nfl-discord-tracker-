import os
import requests

TEAMS = {
    "NO": {
        "webhook": os.getenv("DISCORD_WEBHOOK_SAINTS"),
        "role_id": os.getenv("DISCORD_ROLE_SAINTS"),
        "color": 13408563,  # Gold
        "name": "New Orleans Saints"
    },
    "CAR": {
        "webhook": os.getenv("DISCORD_WEBHOOK_PANTHERS"),
        "role_id": os.getenv("DISCORD_ROLE_PANTHERS"),
        "color": 15403,     # Blue/Black
        "name": "Carolina Panthers"
    }
}

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def run_tracker():
    try:
        response = requests.get(ESPN_URL, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"Error fetching ESPN API: {e}")
        return

    events = data.get("events", [])

    for event in events:
        competition = event["competitions"][0]
        competitors = competition["competitors"]
        
        for team in competitors:
            abbrev = team["team"]["abbreviation"]
            
            if abbrev in TEAMS and TEAMS[abbrev]["webhook"]:
                cfg = TEAMS[abbrev]
                role_ping = f"<@&{cfg['role_id']}>" if cfg["role_id"] else ""
                
                home = next(c for c in competitors if c["homeAway"] == "home")
                away = next(c for c in competitors if c["homeAway"] == "away")
                
                status_detail = event["status"]["type"]["detail"]
                
                payload = {
                    "content": role_ping,
                    "allowed_mentions": {"roles": [cfg["role_id"]] if cfg["role_id"] else []},
                    "embeds": [{
                        "title": f"🏈 {cfg['name']} Game Update",
                        "color": cfg["color"],
                        "fields": [
                            {
                                "name": "Matchup",
                                "value": f"**{away['team']['displayName']}** @ **{home['team']['displayName']}**",
                                "inline": False
                            },
                            {
                                "name": "Score",
                                "value": f"{away['team']['abbreviation']}: **{away['score']}** | {home['team']['abbreviation']}: **{home['score']}**",
                                "inline": True
                            },
                            {
                                "name": "Status",
                                "value": status_detail,
                                "inline": True
                            }
                        ],
                        "footer": {"text": "Automated NFL Live Score Tracker"}
                    }]
                }
                
                res = requests.post(cfg["webhook"], json=payload)
                print(f"Sent update for {abbrev}. Status: {res.status_code}")

if __name__ == "__main__":
    run_tracker()
