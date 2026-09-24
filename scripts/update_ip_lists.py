#!/usr/bin/env python3
"""
Holt die Media-IP-Bereiche von Webex und Google Meet aus den offiziellen
Hersteller-Seiten und schreibt sie als OPNsense-taugliche URL-Table-Listen
(ein CIDR pro Zeile) nach lists/.

Sicherheitsnetz: Wenn eine Seite umgebaut wurde und der Parser nichts oder
deutlich weniger findet, bricht das Script mit Fehler ab und laesst die
bestehende Datei unangetastet. Eine leere Liste landet so nie in der Firewall.

Nur Python-Standardbibliothek, keine Abhaengigkeiten.
"""

import datetime
import html
import ipaddress
import re
import sys
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "lists"

# Wenn die neue Liste weniger als diesen Anteil der alten enthaelt, abbrechen.
MAX_SHRINK = 0.5

SOURCES = [
    {
        "name": "webex-media",
        "title": "Webex Media Subnets (IPv4 + IPv6)",
        "url": "https://help.webex.com/en-us/article/WBX000028782",
        "section": 'Abschnitt "IP subnets for Webex media services"',
        # Bereich zwischen Start- und Endmarker wird nach CIDRs durchsucht
        "start": "IPv4 Subnets for Media Services",
        "end": "perform tests to detect the reachability",
        "min_entries": 20,
    },
    {
        "name": "google-meet-media",
        "title": "Google Meet Media Server (IPv4 + IPv6)",
        "url": "https://support.google.com/a/answer/1279090?hl=en",
        "section": 'Abschnitt "Allow access to Google IP address ranges"',
        "start": "Allow access to Google IP address ranges",
        "end": "Review bandwidth requirements",
        "min_entries": 3,
    },
]

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# Kandidaten: alles, was wie Adresse/Praefix aussieht; Validierung danach
CIDR_CANDIDATE = re.compile(r"[0-9A-Fa-f:.]+/\d{1,3}")


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def to_text(raw: str) -> str:
    # JSON-escapte Tags (Next.js-Seiten) zuerst normalisieren
    raw = raw.replace("\\u003c", "<").replace("\\u003e", ">")
    raw = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(raw)


def extract_networks(text: str, start: str, end: str) -> list:
    """Sucht jede Stelle des Startmarkers, nimmt den Text bis zum naechsten
    Endmarker und sammelt alle gueltigen Netze daraus (dedupliziert)."""
    found = {}
    pos = 0
    while True:
        s = text.find(start, pos)
        if s == -1:
            break
        e = text.find(end, s)
        if e == -1:
            break
        for cand in CIDR_CANDIDATE.findall(text[s:e]):
            if "." not in cand and ":" not in cand:
                continue
            try:
                net = ipaddress.ip_network(cand, strict=False)
            except ValueError:
                continue
            found[str(net)] = net
        pos = e
    return sorted(found.values(), key=lambda n: (n.version, n.network_address, n.prefixlen))


def read_existing(path: Path) -> set:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def write_list(path: Path, src: dict, nets: list) -> None:
    today = datetime.date.today().isoformat()
    lines = [
        f"# {src['title']}",
        f"# Quelle: {src['url']}",
        f"# {src['section']}",
        f"# Automatisch erzeugt, letzte inhaltliche Aenderung: {today}",
    ]
    lines += [str(n) for n in nets]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors = 0

    for src in SOURCES:
        path = OUT_DIR / f"{src['name']}.txt"
        try:
            nets = extract_networks(to_text(fetch(src["url"])), src["start"], src["end"])
        except Exception as exc:  # Netzwerk, HTTP-Fehler, ...
            print(f"[FEHLER] {src['name']}: Abruf fehlgeschlagen: {exc}")
            errors += 1
            continue

        new = {str(n) for n in nets}
        old = read_existing(path)

        if len(new) < src["min_entries"]:
            print(
                f"[FEHLER] {src['name']}: nur {len(new)} Netze gefunden "
                f"(Minimum {src['min_entries']}). Seite umgebaut? Datei bleibt unveraendert."
            )
            errors += 1
            continue

        if old and len(new) < len(old) * MAX_SHRINK:
            print(
                f"[FEHLER] {src['name']}: Liste wuerde von {len(old)} auf {len(new)} "
                f"schrumpfen. Bitte manuell pruefen. Datei bleibt unveraendert."
            )
            errors += 1
            continue

        if new == old:
            print(f"[OK] {src['name']}: unveraendert ({len(new)} Netze)")
            continue

        added, removed = sorted(new - old), sorted(old - new)
        write_list(path, src, nets)
        print(f"[NEU] {src['name']}: {len(new)} Netze geschrieben")
        for n in added:
            print(f"      + {n}")
        for n in removed:
            print(f"      - {n}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
