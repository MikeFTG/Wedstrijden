import requests
import json
import os
from datetime import datetime

API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
STATUS_BESTAND = "known_matches.json"

COMPETITIES = {
    "PL":  "Premier League",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "PD":  "La Liga",
    "BL2": "2. Bundesliga",
    "FL1": "Ligue 1",
}

def laad_bekende():
    if os.path.exists(STATUS_BESTAND):
        with open(STATUS_BESTAND) as f:
            return json.load(f)
    return {}

def sla_bekende_op(data):
    with open(STATUS_BESTAND, "w") as f:
        json.dump(data, f, indent=2)

def haal_wedstrijden_op(code):
    url = f"https://api.football-data.org/v4/competitions/{code}/matches"
    headers = {"X-Auth-Token": API_KEY}
    params = {"status": "SCHEDULED,TIMED"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception as e:
        print(f"  [FOUT] {code}: {e}")
        return []

def stuur_slack(wedstrijd, comp_naam):
    thuis = wedstrijd["homeTeam"]["name"]
    uit   = wedstrijd["awayTeam"]["name"]
    datum_str = wedstrijd.get("utcDate", "")
    try:
        dt = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
        datum_nl = dt.strftime("%A %d %B · %H:%M UTC")
    except:
        datum_nl = datum_str

    bericht = {
        "text": f":soccer: *Wedstrijd bevestigd \u2014 {comp_naam}*",
        "attachments": [{
            "color": "#36a64f",
            "fields": [
                {"title": "Wedstrijd", "value": f"{thuis} vs {uit}", "short": False},
                {"title": "Datum & tijd", "value": datum_nl, "short": True},
                {"title": "Status", "value": wedstrijd.get("status", ""), "short": True},
            ],
            "footer": "Match Monitor Bot",
        }]
    }
    try:
        requests.post(SLACK_WEBHOOK, json=bericht, timeout=10)
        print(f"  [Slack] {thuis} vs {uit}")
    except Exception as e:
        print(f"  [Slack fout] {e}")

def main():
    bekende = laad_bekende()
    nieuwe_bekende = dict(bekende)
    alle_wedstrijden = []

    for code, naam in COMPETITIES.items():
        print(f"Fetching {naam}...")
        wedstrijden = haal_wedstrijden_op(code)
        print(f"  {len(wedstrijden)} wedstrijden")

        for w in wedstrijden:
            wid = str(w["id"])
            status = w.get("status", "")

            # Slack sturen als status veranderd is naar TIMED
            if status == "TIMED" and bekende.get(wid) != "TIMED":
                stuur_slack(w, naam)

            nieuwe_bekende[wid] = status
            alle_wedstrijden.append({
                "id": w["id"],
                "compCode": code,
                "compName": naam,
                "homeTeam": w["homeTeam"]["name"],
                "awayTeam": w["awayTeam"]["name"],
                "utcDate": w.get("utcDate", ""),
                "status": status,
            })

    # Sla wedstrijddata op voor de website
    output = {
        "updated": datetime.utcnow().isoformat() + "Z",
        "matches": alle_wedstrijden,
    }
    with open("matches.json", "w") as f:
        json.dump(output, f, indent=2)

    sla_bekende_op(nieuwe_bekende)
    print(f"\nKlaar. {len(alle_wedstrijden)} wedstrijden opgeslagen.")

if __name__ == "__main__":
    main()
