import requests
import json
import os
from datetime import datetime, timezone

API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")

COMPETITIES = {
    "PL":  "Premier League",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "PD":  "La Liga",
    "BL2": "2. Bundesliga",
    "FL1": "Ligue 1",
}

STATUS_BESTAND = "known_matches.json"

def laad_bekende():
    if os.path.exists(STATUS_BESTAND):
        with open(STATUS_BESTAND) as f:
            return json.load(f)
    return {}

def sla_bekende_op(data):
    with open(STATUS_BESTAND, "w") as f:
        json.dump(data, f, indent=2)

def haal_wedstrijden_op(code):
    url = "https://api.football-data.org/v4/competitions/" + code + "/matches"
    headers = {"X-Auth-Token": API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json().get("matches", [])
    except Exception as e:
        print("  [FOUT] " + code + ": " + str(e))
        return []

def stuur_slack(wedstrijd, comp_naam):
    thuis = wedstrijd["homeTeam"]["name"]
    uit   = wedstrijd["awayTeam"]["name"]
    datum_str = wedstrijd.get("utcDate", "")
    speelronde = wedstrijd.get("matchday", "?")
    try:
        dt = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
        datum_nl = dt.strftime("%A %d %B, %H:%M UTC")
    except:
        datum_nl = datum_str
    bericht = {
        "text": ":soccer: *Wedstrijd bevestigd - " + comp_naam + "*",
        "attachments": [{
            "color": "#36a64f",
            "fields": [
                {"title": "Speelronde", "value": str(speelronde), "short": True},
                {"title": "Wedstrijd", "value": thuis + " vs " + uit, "short": False},
                {"title": "Datum en tijd", "value": datum_nl, "short": True},
            ],
            "footer": "Match Monitor Bot",
        }]
    }
    try:
        requests.post(SLACK_WEBHOOK, json=bericht, timeout=10)
        print("  [Slack] Ronde " + str(speelronde) + ": " + thuis + " vs " + uit)
    except Exception as e:
        print("  [Slack fout] " + str(e))

def main():
    bekende = laad_bekende()
    nieuwe_bekende = dict(bekende)
    alle_wedstrijden = []
    nu = datetime.now(timezone.utc)

    print("API key aanwezig: " + ("ja" if API_KEY else "NEE - KEY ONTBREEKT"))

    for code, naam in COMPETITIES.items():
        print("Fetching " + naam + "...")
        wedstrijden = haal_wedstrijden_op(code)
        print("  " + str(len(wedstrijden)) + " wedstrijden totaal")

        for w in wedstrijden:
            status = w.get("status", "")
            if status in ("FINISHED", "IN_PLAY", "PAUSED", "SUSPENDED", "CANCELLED", "POSTPONED"):
                continue
            datum_str = w.get("utcDate", "")
            try:
                dt = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
                if dt < nu:
                    continue
            except:
                pass

            wid = str(w["id"])
            if status == "TIMED" and bekende.get(wid) != "TIMED":
                stuur_slack(w, naam)
            nieuwe_bekende[wid] = status

            alle_wedstrijden.append({
                "id": w["id"],
                "compCode": code,
                "compName": naam,
                "matchday": w.get("matchday"),
                "homeTeam": w["homeTeam"]["name"],
                "awayTeam": w["awayTeam"]["name"],
                "utcDate": datum_str,
                "status": status,
            })

    output = {"updated": nu.isoformat(), "matches": alle_wedstrijden}
    with open("matches.json", "w") as f:
        json.dump(output, f, indent=2)
    sla_bekende_op(nieuwe_bekende)
    print("Klaar. " + str(len(alle_wedstrijden)) + " aankomende wedstrijden opgeslagen.")

if __name__ == "__main__":
    main()
