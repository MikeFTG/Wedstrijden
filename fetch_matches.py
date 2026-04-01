import requests
import json
import os
from datetime import datetime, timezone

API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_TEST = os.environ.get("SLACK_TEST", "false")

COMPETITIES = {
    "PL":  "Premier League",
    "BL1": "Bundesliga",
    "SA":  "Serie A",
    "PD":  "La Liga",
    "FL1": "Ligue 1",
}

STATUS_BESTAND = "known_matches.json"
LOGO_MAP_BESTAND = "logo_map.json"
LOGOS_DIR = "logos"

def laad_bekende():
    if os.path.exists(STATUS_BESTAND):
        with open(STATUS_BESTAND) as f:
            return json.load(f)
    return {}

def sla_bekende_op(data):
    with open(STATUS_BESTAND, "w") as f:
        json.dump(data, f, indent=2)

def laad_logo_map():
    if os.path.exists(LOGO_MAP_BESTAND):
        with open(LOGO_MAP_BESTAND) as f:
            return json.load(f)
    return {}

def sla_logo_map_op(data):
    with open(LOGO_MAP_BESTAND, "w") as f:
        json.dump(data, f, indent=2)

def download_logo(naam, url, logo_map):
    if not url or naam in logo_map:
        return
    try:
        os.makedirs(LOGOS_DIR, exist_ok=True)
        veilige_naam = "".join(c if c.isalnum() or c in "-_" else "_" for c in naam)
        ext = ".svg" if url.endswith(".svg") else ".png"
        bestandsnaam = LOGOS_DIR + "/" + veilige_naam + ext
        r = requests.get(url, timeout=10, headers={"X-Auth-Token": API_KEY})
        if r.status_code == 200:
            with open(bestandsnaam, "wb") as f:
                f.write(r.content)
            logo_map[naam] = bestandsnaam
            print("  [Logo] " + naam)
    except Exception as e:
        print("  [Logo fout] " + naam + ": " + str(e))

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

def stuur_slack(tekst, kleur, velden):
    if not SLACK_WEBHOOK:
        print("  [Slack] Geen webhook ingesteld")
        return False
    bericht = {
        "text": tekst,
        "attachments": [{
            "color": kleur,
            "fields": velden,
            "footer": "Match Monitor Bot",
        }]
    }
    try:
        r = requests.post(SLACK_WEBHOOK, json=bericht, timeout=10)
        if r.status_code == 200:
            return True
        else:
            print("  [Slack fout] Status: " + str(r.status_code))
            return False
    except Exception as e:
        print("  [Slack fout] " + str(e))
        return False

def stuur_wedstrijd_slack(wedstrijd, comp_naam):
    thuis = wedstrijd["homeTeam"]["name"]
    uit = wedstrijd["awayTeam"]["name"]
    datum_str = wedstrijd.get("utcDate", "")
    speelronde = wedstrijd.get("matchday", "?")
    try:
        dt = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
        datum_nl = dt.strftime("%A %d %B, %H:%M UTC")
    except Exception:
        datum_nl = datum_str
    ok = stuur_slack(
        ":soccer: *Wedstrijd bevestigd - " + comp_naam + "*",
        "#36a64f",
        [
            {"title": "Speelronde", "value": str(speelronde), "short": True},
            {"title": "Wedstrijd", "value": thuis + " vs " + uit, "short": False},
            {"title": "Datum en tijd", "value": datum_nl, "short": True},
        ]
    )
    if ok:
        print("  [Slack] Ronde " + str(speelronde) + ": " + thuis + " vs " + uit)

def main():
    bekende = laad_bekende()
    nieuwe_bekende = dict(bekende)
    logo_map = laad_logo_map()
    alle_wedstrijden = []
    nu = datetime.now(timezone.utc)

    print("API key aanwezig: " + ("ja" if API_KEY else "NEE"))
    print("Slack webhook aanwezig: " + ("ja" if SLACK_WEBHOOK else "NEE"))

    # Slack test bericht
    if SLACK_TEST == "true":
        print("Slack test bericht versturen...")
        ok = stuur_slack(
            ":white_check_mark: *Match Monitor - Slack verbinding werkt!*",
            "#36a64f",
            [{"title": "Status", "value": "Verbinding succesvol getest", "short": False}]
        )
        print("Slack test: " + ("geslaagd!" if ok else "MISLUKT"))
        return

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
            except Exception:
                pass

            thuis_naam = w["homeTeam"]["name"]
            uit_naam = w["awayTeam"]["name"]
            download_logo(thuis_naam, w["homeTeam"].get("crest", ""), logo_map)
            download_logo(uit_naam, w["awayTeam"].get("crest", ""), logo_map)

            wid = str(w["id"])
            if status == "TIMED" and bekende.get(wid) != "TIMED":
                stuur_wedstrijd_slack(w, naam)
            nieuwe_bekende[wid] = status

            alle_wedstrijden.append({
                "id": w["id"],
                "compCode": code,
                "compName": naam,
                "matchday": w.get("matchday"),
                "homeTeam": thuis_naam,
                "homeCrest": logo_map.get(thuis_naam, ""),
                "awayTeam": uit_naam,
                "awayCrest": logo_map.get(uit_naam, ""),
                "utcDate": datum_str,
                "status": status,
            })

    output = {"updated": nu.isoformat(), "matches": alle_wedstrijden}
    with open("matches.json", "w") as f:
        json.dump(output, f, indent=2)
    sla_bekende_op(nieuwe_bekende)
    sla_logo_map_op(logo_map)
    print("Klaar. " + str(len(alle_wedstrijden)) + " aankomende wedstrijden opgeslagen.")

if __name__ == "__main__":
    main()
