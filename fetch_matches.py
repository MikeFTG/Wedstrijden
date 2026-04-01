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
        return r.status_code == 200
    except Exception as e:
        print("  [Slack fout] " + str(e))
        return False

def formatteer_datum(datum_str):
    try:
        dt = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
        return dt.strftime("%A %d %B, %H:%M UTC")
    except Exception:
        return datum_str

def main():
    bekende = laad_bekende()
    nieuwe_bekende = dict(bekende)
    logo_map = laad_logo_map()
    alle_wedstrijden = []
    nu = datetime.now(timezone.utc)

    print("API key aanwezig: " + ("ja" if API_KEY else "NEE"))
    print("Slack webhook aanwezig: " + ("ja" if SLACK_WEBHOOK else "NEE"))

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

            thuis = w["homeTeam"]["name"]
            uit = w["awayTeam"]["name"]
            speelronde = w.get("matchday", "?")
            wid = str(w["id"])

            oude_info = bekende.get(wid, {})
            # Ondersteuning voor oude string-opslag (alleen status)
            if isinstance(oude_info, str):
                oude_info = {"status": oude_info, "datum": ""}

            oude_status = oude_info.get("status", "")
            oude_datum = oude_info.get("datum", "")

            # Nieuw bevestigd
            if status == "TIMED" and oude_status != "TIMED":
                print("  [Nieuw bevestigd] " + thuis + " vs " + uit)
                stuur_slack(
                    ":soccer: *Wedstrijd bevestigd - " + naam + "*",
                    "#36a64f",
                    [
                        {"title": "Speelronde", "value": str(speelronde), "short": True},
                        {"title": "Wedstrijd", "value": thuis + " vs " + uit, "short": False},
                        {"title": "Datum en tijd", "value": formatteer_datum(datum_str), "short": True},
                    ]
                )

            # Verplaatst (al TIMED, maar datum gewijzigd)
            elif status == "TIMED" and oude_status == "TIMED" and oude_datum and oude_datum != datum_str:
                print("  [Verplaatst] " + thuis + " vs " + uit)
                stuur_slack(
                    ":warning: *Wedstrijd verplaatst - " + naam + "*",
                    "#ff9800",
                    [
                        {"title": "Speelronde", "value": str(speelronde), "short": True},
                        {"title": "Wedstrijd", "value": thuis + " vs " + uit, "short": False},
                        {"title": "Oude datum", "value": formatteer_datum(oude_datum), "short": True},
                        {"title": "Nieuwe datum", "value": formatteer_datum(datum_str), "short": True},
                    ]
                )

            nieuwe_bekende[wid] = {"status": status, "datum": datum_str}

            download_logo(thuis, w["homeTeam"].get("crest", ""), logo_map)
            download_logo(uit, w["awayTeam"].get("crest", ""), logo_map)

            alle_wedstrijden.append({
                "id": w["id"],
                "compCode": code,
                "compName": naam,
                "matchday": speelronde,
                "homeTeam": thuis,
                "homeCrest": logo_map.get(thuis, ""),
                "awayTeam": uit,
                "awayCrest": logo_map.get(uit, ""),
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
