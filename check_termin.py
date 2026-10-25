"""
Führerscheinstelle Kreis Mettmann – Termin-Wächter
Prüft, ob es für "Umschreibung ausländische Fahrerlaubnis" einen früheren
Termin gibt als den aktuellen, und schickt dann eine Push-Nachricht über ntfy.

Der Bot bucht NICHTS. Er liest nur das Datum "Nächster Termin ab ..." aus.
"""

import os
import re
import sys
import html
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime

BASE = "https://tevis.krzn.de/tevisweb700"
START_URL = f"{BASE}/select2?md=3"  # Führerscheinstelle
LOCATION_URL = f"{BASE}/location?mdt=127&select_cnc=1&cnc-1952=1"  # Umschreibung ausl. Fahrerlaubnis

# Aktueller Termin – alles davor ist interessant (Format TT.MM.JJJJ)
AKTUELLER_TERMIN = os.environ.get("AKTUELLER_TERMIN", "10.12.2026")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
# Persönlicher Änderungslink aus der Bestätigungs-Mail (als GitHub-Secret!)
AENDERUNGS_LINK = os.environ.get("AENDERUNGS_LINK", "").strip() or START_URL

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
}


def fetch(opener, url):
    req = urllib.request.Request(url, headers=HEADERS)
    with opener.open(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def naechster_termin(page_html):
    """Sucht 'Nächster Termin ... ab TT.MM.JJJJ, HH:MM Uhr' im Seitentext."""
    text = re.sub(r"<[^>]+>", " ", page_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"N.chster Termin\s*:?\s*ab\s*(\d{2}\.\d{2}\.\d{4}),?\s*(\d{2}:\d{2})?", text)
    if not m:
        return None, text
    return (m.group(1), m.group(2) or ""), text


def notify(title, message, priority="high"):
    if not NTFY_TOPIC:
        print("Kein NTFY_TOPIC gesetzt – keine Push-Nachricht gesendet.")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{urllib.parse.quote(NTFY_TOPIC)}",
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8").decode("latin-1", errors="ignore"),
            "Priority": priority,
            "Tags": "car",
            "Click": AENDERUNGS_LINK,
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # 1) Sitzung starten (Cookie holen), 2) Standortseite mit Anliegen aufrufen
    fetch(opener, START_URL)
    page = fetch(opener, LOCATION_URL)

    found, text = naechster_termin(page)
    if not found:
        print("FEHLER: 'Nächster Termin' nicht gefunden. Seitentext (Anfang):")
        print(text[:1500])
        sys.exit(1)  # Lauf schlägt fehl -> GitHub schickt dir eine E-Mail

    datum, uhrzeit = found
    frei = datetime.strptime(datum, "%d.%m.%Y")
    aktuell = datetime.strptime(AKTUELLER_TERMIN, "%d.%m.%Y")
    print(f"Nächster freier Termin: {datum} {uhrzeit} | Dein Termin: {AKTUELLER_TERMIN}")

    if frei < aktuell:
        notify(
            "Früherer Termin frei!",
            f"Führerscheinstelle Mettmann: {datum} {uhrzeit} Uhr frei "
            f"(dein Termin: {AKTUELLER_TERMIN}). Schnell über den Änderungslink umbuchen!",
        )
        print("Früherer Termin gefunden – Benachrichtigung gesendet.")
    else:
        print("Kein früherer Termin.")


if __name__ == "__main__":
    main()
