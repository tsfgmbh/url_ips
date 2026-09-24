# IP-Listen für OPNsense

Automatisch gepflegte Media-IP-Bereiche für Videokonferenz-Dienste, als
URL-Table-Quelle für OPNsense-Aliase (ein CIDR pro Zeile).

| Datei | Quelle |
|---|---|
| `lists/webex-media.txt` | https://help.webex.com/en-us/article/WBX000028782 |
| `lists/google-meet-media.txt` | https://support.google.com/a/answer/1279090 |

Ein GitHub-Actions-Workflow läuft täglich, liest die Hersteller-Seiten aus und
committet nur, wenn sich ein Netz geändert hat. Findet das Script zu wenige
Netze oder würde eine Liste um mehr als die Hälfte schrumpfen, bleibt die alte
Datei unverändert und der Lauf schlägt fehl.

## OPNsense

Firewall ‣ Aliases ‣ Typ **URL Table (IPs)**, Inhalt:

```
https://raw.githubusercontent.com/<user>/<repo>/main/lists/webex-media.txt
https://raw.githubusercontent.com/<user>/<repo>/main/lists/google-meet-media.txt
```

Hinweis: Der Alias wird erst in pf geladen, wenn eine aktive Regel ihn nutzt.
