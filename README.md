# sponsorenlauf-tracker

Das System besteht aus einem Server (Flask-Webanwendung) zur Erfassung und Auswertung von Scans bei einem Sponsorenlauf (z.B. für Schulen). 
Bei jedem Durchlauf des Sponsorenlaufs wird der individuelle Code eines Schülers oder einer Schülerin gescannt.
Der Code wird zusammen mit dem Namen des Scanners (z. B. der Station oder Aufsichtsperson) an den Server übertragen.
Dort wird er mit vorhandenen Schülerdaten verknüpft und als eine absolvierte Runde gespeichert.

Die erfassten Daten können anschließend über ein Web-Frontend ausgewertet werden (*siehe [Nutzung](#nutzung)*):
- Letzte Scans
- Alle Scans
- Top-Schüler*innen (nach Rundenanzahl)
- Top-Klassen



## Features

- **Scan-Erfassung:** Scans werden per Web-Formular oder über einen separaten Client an den Server gesendet.
- **Live-Statistiken:** Anzeige der letzten Scans, Top-Schüler*innen und Top-Klassen mit automatischer Aktualisierung (Server-Sent Events).
- **Schülerdaten-Import:** Import von Schülerdaten aus einer CSV-Datei in eine PostgreSQL-Datenbank.
- **Fehlererkennung:** Scans mit unbekannten Codes werden erkannt und als Fehler behandelt.
- **Mehrere Scanner:** Unterstützung für verschiedene Scanner-IDs (z.B. für verschiedene Geräte).

## Projektstruktur
├── client.py # Konsolen-Client zum Senden von Scans  
├── server.py # Flask-Webserver mit allen Routen und Logik  
├── data/  
│ ├── students.csv # Beispielhafte Schülerdaten  
│ └── import_students.py # Tool zum Importieren der Schülerdaten  
├── static/ # (Optional) Statische Dateien für das Web-Frontend  
├── templates/ # HTML-Templates für die Weboberfläche  
│ ├── last.html  
│ ├── scan.html  
│ ├── top-classes.html  
│ └── top-students.html  
├── requirements.txt # Python-Abhängigkeiten  
├── .gitignore  
├── LICENSE  
└── README.md

## Voraussetzungen

- Python 3.7+
- PostgreSQL-Datenbank
- Die in `requirements.txt` gelisteten Pakete:
  - Flask
  - psycopg2-binary
  - requests

## Installation

1. **Repository klonen**
   ```sh
   git clone <REPO-URL>
   cd sponsorenlauf-tracker
   ```

2. **Python-Abhängigkeiten installieren**  
    ```sh 
    pip install -r requirements.txt
    ```

3. **PostgreSQL-Datenbank einrichten**  
    Erstelle eine Datenbank und einen Benutzer, z.B.:
    ```sql
    CREATE DATABASE demo1;
    CREATE USER scanuser WITH PASSWORD 'scanuser';
    GRANT ALL PRIVILEGES ON DATABASE demo1 TO scanuser;
    ```

    Erstelle die benötigten Tabellen:
    ```sql
    -- Tabelle für Schüler
    CREATE TABLE students (
        code VARCHAR PRIMARY KEY,
        firstname VARCHAR,
        lastname VARCHAR,
        class VARCHAR
    );

    -- Tabelle für Scans
    CREATE TABLE scans (
        id SERIAL PRIMARY KEY,
        code VARCHAR,
        scanner_id VARCHAR,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```

4. **PostgreSQL-Datenbank einrichten**  
    ```sh
    cd data
    python import_students.py
    cd ..
    ```

## Nutzung
### Server starten
```sh
python server.py
```
Der Server läuft standardmäßig auf http://localhost:8080.

### Web-Frontend
- Scan-Formular: http://localhost:8080/scan
- Letzte Scans: http://localhost:8080/last
- Alle Scans: http://localhost:8080/all
- Top-Schüler*innen: http://localhost:8080/top-students
- Top-Klassen: http://localhost:8080/top-classes

**Optionale URL-Parameter**
- `limit` (optional, `int`): Anzahl der Ergebnisse  
    - `0` = keine Begrenzung (alle anzeigen)
- `failures` (optional, `bool`):  
    - `false` = nur gültige Einträge
    - `true` = auch ungültige/nicht zuordenbare Codes anzeigen

zum Beispiel: http://localhost:8080/top-students?limit=10&failures=true

### API-Endpunkt
- POST /scan-client
    - Parameter: code, scanner_id
    - Antwort: JSON mit Scan-Status und ggf. Schülerdaten

### Scan-Client (Kommandozeile)
Mit dem Konsolen-Client kannst du Scans simulieren:
```sh
python client.py
```
Gib einen Code ein (z.B. 1000), um einen Scan zu senden. Mit exit beendest du das Programm.

### Live-Updates
Die Weboberfläche aktualisiert sich automatisch bei neuen Scans (über /events mit Server-Sent Events).

## Anpassungen
**Datenbankzugang:** Passe die Zugangsdaten in DB_CONFIG in server.py und import_students.py an deine Umgebung an.
**CSV-Import:** Die Datei students.csv kann beliebig angepasst werden.

## Lizenz
Siehe  [LICENSE Apache 2.0](LICENSE) 

___

*Hinweis: Dieses Projekt befindet sich im Aufbau und sollte vor produktivem Einsatz auf Sicherheit und Fehlerbehandlung geprüft werden.*

