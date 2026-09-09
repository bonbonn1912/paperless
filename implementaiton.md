# Paperless – finaler Implementierungsplan

Stand: 09.09.2026. Zielhardware: Linux-Server mit 4 CPU-Kernen, 6 GB RAM und ohne GPU.
Dieser Plan ersetzt den bisherigen Entwurf. Er beschreibt die noch zu implementierende Anwendung; Funktionen und Leistungswerte sind nicht bereits umgesetzt oder gemessen.

## 1. Ziel und verbindlicher Umfang

Eine private, vollständig lokal verarbeitende Dokumentenverwaltung als mobile PWA:

- PDFs und Bilder hochladen; mindestens 100 Dateien gemeinsam auswählen und als Stapel nacheinander verarbeiten.
- Direkt in der UI mehrere Kameraseiten aufnehmen, ordnen und als ein mehrseitiges PDF-Dokument speichern; alternativ einzelne Bilddokumente erstellen.
- Eine hochwertige, durchgehend responsive UI für Desktop, iPhone und iPad mit gleichwertiger Touch-, Maus- und Tastaturbedienung bereitstellen.
- Einen integrierten hochwertigen Bild- und PDF-Viewer direkt im Frontend anbieten, einschließlich mehrseitiger Navigation, Zoom und Dokumentensuche.
- Originaldateien unverändert in einem gemeinsamen Serverordner speichern.
- Virtuelle Ordner in der UI erstellen und Dokumente darin organisieren.
- Dokumente mit mehreren Tags versehen; Synonyme wie „Rechnung“ und „Invoice“ unter einem gemeinsamen Tab „Rechnungen“ bündeln.
- Nach jedem erfolgreichen Upload automatisch Textextraktion, erforderliche OCR und Klassifizierung einreihen und beginnen, sobald ein Worker frei ist.
- Den persistenten Verarbeitungszustand samt Fortschritt und Fehlergrund im Frontend anzeigen.
- Nicht sicher klassifizierbare Dokumente im Tab „Zu prüfen“ manuell bestehenden oder neuen Tags zuordnen.
- Wörter in PDF-Text und in per OCR erkannten Bild-/Scan-Inhalten lokal suchen.
- Höher aufgelöste OCR und große Neuindizierungen manuell oder nach einem in der UI eingestellten Zeitplan ausführen.
- Keine Advanced-KI-Funktionen in dieser Version: keine LLMs, Embeddings, generativen Zusammenfassungen oder semantische Suche; hierfür auch keine vorbereiteten UI-Schalter oder Implementierungsphase.
- Keine Registrierung; Zugänge werden über ENV konfiguriert. Jeder Benutzer sieht ausschließlich seine eigenen Daten.

„Lokal“ bedeutet: Keine Dokumente, OCR-Texte, Suchanfragen oder Metadaten verlassen für Verarbeitung und Suche den Server. OCR-Sprachdateien werden einmalig bei der Installation bereitgestellt. Danach funktionieren alle Kernfunktionen ohne Internet. Die PWA benötigt für Serverzugriff eine LAN-/VPN-/HTTPS-Verbindung; das ist keine vollständige Offline-Dokumentbibliothek auf dem Smartphone.

## 2. Korrekturen gegenüber dem bisherigen Entwurf

| Bisherige Lücke / Entscheidung | Finale Festlegung |
| --- | --- |
| Physische Ordner nach Benutzer/Jahr/Dokument | Ein flacher Originalordner; Benutzer, Ordner und Tags werden in SQLite verwaltet. |
| Kategorien plus unstrukturierte Tag-Strings | Ein gemeinsames Tag-Modell mit stabilen IDs, Aliasen und optionalem Dokumenttyp. |
| `invoice` und „Rechnung“ könnten getrennt entstehen | Beide Namen werden auf denselben kanonischen Tag aufgelöst. |
| Nur `uploaded`, `processing`, `ready`, `failed` | Persistente Job-State-Machine mit Verarbeitungsschritten, Wiederaufnahme und separatem Prüfstatus. |
| FastAPI `BackgroundTasks` für OCR | Eigener Worker-Prozess mit dauerhafter SQLite-Jobqueue. |
| `LIKE`-Suche als Übergang | FTS5 ab der ersten nutzbaren Version. |
| OCR-Entscheidung anhand gesamter PDF-Textlänge | Pro Seite und bei Mischseiten auch anhand relevanter Bildbereiche entscheiden. |
| Optionale Advanced-KI-/Cloud-Provider | Entfallen vollständig; lokale Textextraktion, Tesseract und regelbasierte Klassifizierung genügen. |
| Kamera-Serie erst als spätere Erweiterung | Mehrseitige Kamera-Dokumente sind Pflichtumfang dieser Version. |
| Unverbindliche Mehrfachauswahl und Status je Dokument | Mindestens 100 Dateien pro Stapel, sequentieller Worker und genau ein gemeinsamer Listen-Poll pro Intervall. |
| Allgemeine Mobile-First-UI | Verbindliches Designsystem und responsive Desktop-/iPhone-/iPad-Abnahme einschließlich Touch. |
| Sämtliche Einstellungen nur über ENV | ENV für Infrastruktur und harte Grenzen; DB und UI für tägliche Einstellungen und Zeitpläne. |
| Basic-Auth-Passwort in `sessionStorage` | Login mit Argon2-Verifikation und widerrufbarer Cookie-Session. |
| Datenbank angeblich vollständig aus Originalen rekonstruierbar | Benutzerordner, Tags, Korrekturen und Zeitpläne sind Primärdaten und müssen gesichert werden. |
| Laufendes `/data` einfach kopieren | Konsistenter DB-/Datei-Backupablauf mit Wiederherstellungstest. |

## 3. Architektur und Stack

### Backend und Prozesse

- Python 3.12 oder neuer, eine konkret getestete Version im Container festlegen.
- FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy, Alembic.
- SQLite mit FTS5, `foreign_keys=ON`, WAL, `busy_timeout` und kurzen Schreibtransaktionen.
- PyMuPDF für PDF-Analyse und Rendering, Tesseract für OCR, Pillow für Bildverarbeitung; HEIC über zusätzlich integrierten und getesteten HEIF-Decoder.
- Ein API-Prozess; ein separater Worker mit SQLite-Queue und integriertem Scheduler.
- Regelbasierter lokaler Klassifikator und schlanke OCR-Pipeline, ohne zusätzliche KI-Laufzeit.
- Keine CPU-intensive Verarbeitung im HTTP-Handler oder Event-Loop.
- Kein Redis, Celery, Elasticsearch oder separater Vektorserver für diese Zielinstallation.

FastAPI weist bei schwerer Hintergrundberechnung auf separate Verarbeitung hin. Für dieses Ein-Server-System wird die dauerhafte Queue bewusst in SQLite implementiert. [FastAPI: Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

SQLite erlaubt auch mit WAL nur einen gleichzeitigen Writer. DB und Worker bleiben auf demselben Host und einem lokalen Dateisystem; keine SQLite-Datei auf einem Netzlaufwerk. [SQLite: WAL](https://www.sqlite.org/wal.html)

### Frontend und Deployment

- Angular, Router, HttpClient, Tailwind CSS, PWA-Manifest und Service Worker.
- Lokal gebündeltes PDF.js mit passendem Web Worker als PDF-Renderingbasis; eigene, zum Designsystem passende Viewer-Oberfläche und gemeinsamer Bildbetrachter.
- Eigenständige responsive Layouts für Desktop, iPad und iPhone; Ordnernavigation, Mehrfachauswahl, Kamera und Stapelupload sind auf allen geeigneten Geräten erreichbar.
- Docker Compose: `api`, `worker`, `web` (statisch gebautes Frontend und Reverse Proxy).
- Caddy oder nginx mit HTTPS und gemeinsamer Origin für Frontend und `/api/v1`.
- Gepinnte, getestete Abhängigkeiten und Container-Versionen; kein `latest` als Produktionsvorgabe.
- Persistentes `/data`; Container nicht als root. OCR-Sprachpakete im getesteten Image bereitstellen.

```text
Angular PWA ── HTTPS / REST ── API ── SQLite: Metadaten, FTS, Jobs, Zeitpläne
                               │                    ▲
                               ▼                    │
                         Originaldateien        Worker + Scheduler
                                                    │
                                      Extraktion → OCR → Regeln
                                                    │
                                      geplante OCR / Neuindizierung
```

## 4. Dateisystem und virtuelle Ordner

### Physischer Speicher

```text
/data/
├── documents/                  # Alle Originale flach in diesem Ordner
│   ├── <uuid>.pdf
│   ├── <uuid>.jpg
│   └── <uuid>.heic
├── derived/<uuid>/             # Neu erzeugbare Vorschauen und OCR-Artefakte
├── staging/                    # Unvollständige Uploads / atomare Übergabe
├── database/app.sqlite3
└── exports/                    # Optionaler lokaler Export
```

Die Dateiendung stammt vom verifizierten Dateityp. Namen vom Client werden nur als Metadaten gespeichert und niemals als Pfad verwendet. UUIDs sind global eindeutig. Originale werden nach erfolgreicher Speicherung nicht überschrieben; Bilddrehung, Kompression, OCR-PDF und Vorschau erzeugen abgeleitete Dateien. Bei Kamera-Dokumenten bleiben die angenommenen Bilddateien als unveränderte Quell-Assets ebenfalls flach in `documents` erhalten; das daraus erzeugte mehrseitige PDF ist das Standard-Anzeigeartefakt. `document_assets` verknüpft diese Dateien mit genau einem logischen Dokument, ohne zusätzliche Bibliothekseinträge pro Seite.

Ordner- und Tag-Änderungen bewegen oder duplizieren keine Originaldateien. Benutzertrennung erfolgt durch geprüfte DB-Zuordnung bei jedem Zugriff, nicht durch den Ordnernamen. Kein direkter statischer Zugriff auf `/data`.

### Virtuelle Ordner in der UI

- Ordner erstellen, umbenennen, verschieben und löschen; Unterordner unterstützen.
- Dokumente können in mehreren virtuellen Ordnern liegen, über eine Many-to-many-Zuordnung.
- „Zu Ordner hinzufügen“ ergänzt eine Zuordnung; „Aus Ordner entfernen“ entfernt nur diese. „Verschieben“ ersetzt die gewählte Quellzuordnung durch die Zielzuordnung.
- Ein Ordner ist unabhängig von Tags. Beispielsweise kann ein Dokument in „Haus / Renovierung“ liegen und die Tags „Rechnungen“ und „Handwerker“ haben.
- Leere Ordner bleiben sichtbar. „Ohne Ordner“ ist ein gespeicherter Filter, kein physischer Ordner.
- Ordnerlöschung entfernt nach einer UI-Vorschau den gewählten virtuellen Teilbaum samt Zuordnungen, niemals Dokumente oder Tags. Andere Zuordnungen bleiben erhalten.
- Zyklen und fremde Eigentümer bei Eltern-/Kindzuordnungen werden serverseitig verhindert.

## 5. Kanonische Tags, Aliase und Tabs

### Ein gemeinsames Tag-System

Ein Tag hat eine stabile UUID, einen Anzeigenamen und optional `kind=document_type`; andere Tags haben `kind=topic`. Die UUID bleibt beim Umbenennen unverändert. Das bisherige freie Feld `category` entfällt.

Initiale Dokumenttypen werden pro Benutzer angelegt: Rechnungen, Belege, Verträge, Versicherungen, Steuer, Bank, Behörden, Gesundheit, Korrespondenz, Anleitungen und Garantien. Benutzer können eigene Dokumenttypen und Themen erstellen. Es gibt keine automatische Restekategorie „Sonstiges“, die ungeklärte Dokumente versteckt.

| Kanonischer Tag | Akzeptierte Namen / Aliase | Gemeinsamer UI-Tab |
| --- | --- | --- |
| Rechnungen | Rechnung, Rechnungen, Invoice, Invoices | Rechnungen |
| Verträge | Vertrag, Verträge, Contract, Contracts | Verträge |
| Belege | Beleg, Belege, Receipt, Receipts | Belege |

Ein Benutzer kann jeden Tag als Tab anheften. Dokumenttyp-Tags sind initial angeheftet; Themen sind über Tagfilter erreichbar und optional anheftbar. Tabs sind Abfragen auf eine Tag-ID. Es entsteht kein zweiter Tab für einen Alias. Ein Dokument kann in mehreren Tag-Tabs erscheinen.

### Auflösung neuer Namen

1. Eingabe normalisieren: Unicode-Normalisierung (NFKC), `casefold`, äußere Leerzeichen entfernen und innere Leerzeichen zusammenfassen. Keine pauschale Übersetzung oder Wortstammkürzung.
2. In einem gemeinsamen Namensregister aus kanonischen Namen und Aliasen suchen; Unique Constraint `(owner, normalized_name)` verhindert auch Namens-/Alias-Kollisionen.
3. Bei bekanntem Namen die vorhandene Tag-ID zurückgeben. `POST /tags` mit „Invoice“ liefert somit den bestehenden Tag „Rechnungen“ und `resolved_existing=true`.
4. Bei unbekanntem Namen ähnliche bestehende Tags anbieten. Exakte bekannte Aliase werden automatisch aufgelöst; unbekannte Ähnlichkeiten benötigen eine bewusste Auswahl. Vorschläge beruhen ausschließlich auf bekannten Aliasen und einfacher Zeichenkettenähnlichkeit.
5. Der Benutzer wählt „Vorhandenen Tag verwenden“, „Als Alias hinzufügen“ oder „Neuen Tag erstellen“. Die neue Zuordnung gilt sofort.

„Beleg“, „Rechnung“, „Gutschrift“ oder „Kontoauszug“ werden nicht allein wegen ähnlicher Inhalte zusammengeführt. Neue Synonyme werden manuell als Aliase gepflegt; unbekannte Tags werden nicht automatisch verschmolzen.

### Zusammenführen und Korrekturen

Die Tagverwaltung zeigt beim Merge Quelle, Ziel und Anzahl betroffener Dokumente. Eine Transaktion überträgt Zuordnungen ohne Duplikate, Aliase, Regeln und Tab-Verweise; die alte ID erhält einen Redirect auf die Ziel-ID. Bei unterschiedlichem `kind` muss der Zieltyp ausdrücklich festgelegt werden. Referenzen in Jobresultaten werden vor dem Schreiben erneut aufgelöst. Ein Änderungsprotokoll hält die betroffenen Zuordnungen fest.

Manuell gesetzte oder entfernte Tags und Metadaten werden als Benutzerentscheidung gespeichert. Reprocessing und geplante OCR-Läufe dürfen diese nicht überschreiben. Auch eine manuelle Entfernung wird dokumentiert, damit dasselbe automatische Tag nicht beim nächsten Lauf wiederkehrt.

Tag-Löschung zeigt zuvor alle betroffenen Zuordnungen und Regeln. Sie entfernt keine Dokumente, deaktiviert betroffene Regeln und entfernt den Tab. Verliert ein Dokument dadurch seine letzte akzeptierte Klassifizierung, geht es mit Grund `tag_removed` zurück nach „Zu prüfen“. Ein reines Umbenennen ändert keine Klassifizierung. Ordnernamen sind je Benutzer und Elternordner normalisiert eindeutig, auch auf Wurzelebene.

## 6. Persistentes Datenmodell

Alle privaten Tabellen tragen `owner` oder werden über zwingende Eigentümerbeziehungen aufgelöst. Fremdschlüssel und zusammengesetzte Constraints sichern die Trennung auch bei Zuordnungen ab. UUIDs allein sind keine Autorisierung.

| Tabelle | Zentrale Felder / Aufgabe |
| --- | --- |
| `documents` | UUID, owner, Originalname, storage_key, MIME, Größe, SHA-256, Titel, Absender, Datumsfelder, Betrag, Währung, source (`upload`, `capture`), metadata_revision, active_run_id, processing_state, classification_state, index_state, timestamps, deleted_at |
| `document_assets` | Dokument, Asset-UUID, storage_key, Rolle (`source_image`, `assembled_pdf`), SHA-256, MIME, Bytegröße; Kameraquellen bleiben unverändert |
| `upload_batches` / `upload_items` | Benutzerbezogener Stapel, manifest_version, Status / client_item_id, Auswahlposition, Annahmereihenfolge, Uploadstatus, Dokument-/Job-ID, Fehler, Idempotency-Key |
| `capture_sessions` / `capture_pages` | Eigentümer, Entwurfsstatus, Revision, Ablauf / Seiten-UUID, Quell-Asset, Reihenfolge, Rotation/Zuschnitt, Uploadstatus |
| `document_pages` | document_id, page_number, Text, extraction_method, OCR-Qualitätshinweise, page_state, error_code, Text-/Pipeline-Version; Seitenmaße und Wort-/Zeilenkoordinaten mit Textoffsets für Viewer-Suchmarkierungen |
| `document_field_overrides` | document_id, Feld, manueller Wert oder bewusst leerer Wert, Benutzer, Zeitpunkt |
| `folders` / `document_folders` | Ordnerbaum, normalisierter Name, Eltern-ID / Dokumentzuordnungen |
| `tags` / `tag_names` | Kanonischer Tag, kind, Farbe, Merge-Ziel / Anzeigenamen und Aliase mit eindeutigem normalisiertem Namensraum |
| `document_tags` | Dokument, Tag, source (`manual`, `rule`), score, Version und Zeitpunkt |
| `document_tag_overrides` | Manuell bestätigte oder ausgeschlossene Tags; Vorrang vor automatischen Vorschlägen |
| `classification_results` | Versionierte Vorschläge, Evidenz, Regelversion, Prüfgründe, Basisrevision |
| `classification_rules` | Benutzerbezogene Bedingungen, Ziel-Tag-IDs, Priorität, aktiviert, Version |
| `jobs` | ID, owner, Dokument, run_id, Typ, Zustand, Schritt, Priorität, Fortschritt, not_before, schedule_id, Versuche, Lease, Heartbeat, claim_token, Fehler, Config-/Input-Version |
| `job_events` | Append-only Zustandswechsel mit Zeit, Grund und Fortschritt; begrenzte Aufbewahrung |
| `schedules` | Benutzer, Jobtyp, Filter, Modus, Wochentage, lokale Uhrzeit, Zeitzone, Zeitfenster, Limits, nächste Ausführung |
| `user_settings` | OCR-/Klassifizierungspräferenzen, angeheftete Tabs, Ressourcenwünsche innerhalb der ENV-Grenzen |
| `sessions` | Gehashte Session-ID, ENV-Benutzerkennung, credential_version, Ablauf, Widerruf |
| `audit_events` | Manuelle Änderungen, Merge, Löschen, Einstellungen; ohne vollständige Dokumentinhalte |
| `search_documents` / FTS5 | Versionierte Suchprojektion aus Text und Metadaten, ein Eintrag pro Dokument |

Beträge als Integer in kleinsten Währungseinheiten mit Währungsexponent speichern; API übermittelt Dezimalstrings. Keine binären Float-Beträge. Zeitpunkte intern in UTC, Dokumentdaten als Datum ohne Zeitzone. Bei nicht eindeutig erkannten Werten bleibt das Feld leer und ein Vorschlag wird separat angezeigt.

Quell-Assets eines Kameraentwurfs gehören zunächst einer `capture_session`; ihre Dokument-ID darf bis zum Finalisieren leer sein. Eigentümer und mindestens eine gültige Entwurfs-/Dokumentzuordnung sind Pflicht. Finalisieren überträgt sie atomar an das neue Dokument und erhält das eingefrorene Seitenmanifest. Entwurfsbereinigung darf Assets mit Dokumentzuordnung niemals löschen.

Notwendige Indizes: `(owner, sha256)` unique, Listenfilter nach owner/status/Datum, Ordner- und Tagzuordnungen, Jobauswahl nach Zustand/not_before/Priorität, eindeutige Seitennummer je Dokument und Verarbeitungsrevision. Pro Dokument ist höchstens ein aktiver Basispipeline-Lauf zulässig. Automatische Jobs erhalten einen deduplizierenden Schlüssel aus Dokument, Jobtyp und Input-/Konfigurationsversion; manuell ausgelöste Neuläufe erhalten einen neuen Run, HTTP-Wiederholungen bleiben idempotent.

## 7. Upload und dauerhafte Jobannahme

Unterstützt werden PDF, JPEG, PNG, WebP und HEIC, sobald der Decoder im Produktionsimage vorhanden und getestet ist. Die UI zeigt nur tatsächlich unterstützte Formate. Bei normalem Stapelupload erzeugt jede Datei ein Dokument; vorhandene mehrseitige PDFs bleiben ein Dokument. Im separaten Kamera-/Seitensammler können mehrere Fotos dagegen ausdrücklich zu einem mehrseitigen Dokument zusammengefasst werden.

1. Authentifizierung, Eigentümerzuordnung und Upload-Idempotency-Key prüfen.
2. Datei gestreamt in `staging` schreiben, Größenlimit durchsetzen, SHA-256 berechnen und tatsächliches Format prüfen.
3. Endung, MIME, Decoderergebnis, Seiten-/Pixelgrenzen und freien Speicher validieren. Beschädigte oder passwortgeschützte PDFs mit verständlichem Grund ablehnen; die lokale Quelldatei bleibt beim Benutzer.
4. Eine exakte Dublette des gleichen Benutzers liefert `409 document_already_exists` mit dessen vorhandener Dokument-ID. Über andere Benutzer wird keine Auskunft gegeben.
5. Original unter UUID atomar auf demselben Dateisystem nach `documents` umbenennen und dauerhaft schreiben; erst danach Dokument und `queued`-Basisjob zusammen in einer DB-Transaktion anlegen.
6. `202 Accepted` mit Dokument-ID, Job-ID, optionaler Batch-/Item-ID und Verweis auf den gemeinsamen Listen-Status-Endpunkt zurückgeben. Die Annahme bedeutet „dauerhaft gespeichert und eingeplant“, nicht „schon klassifiziert“.
7. Der Worker greift unmittelbar auf die Queue zu, ohne weiteren UI-Klick.

Dateisystem und SQLite bilden keine gemeinsame Transaktion. Bei DB-Fehler wird die neue Datei entfernt oder als verwaist markiert. Ein Recovery-Lauf bereinigt alte Staging-/verwaiste Dateien nach einer Schutzfrist; fehlende Originale zu DB-Einträgen werden gemeldet. Nach Verbindungsabbruch löst eine Wiederholung mit demselben Idempotency-Key auf das bereits angenommene Dokument auf.

Der Browser zeigt während der Dateiübertragung lokalen Uploadfortschritt. Erst nach erfolgreicher Annahme übernimmt die Server-State-Machine.

### Stapelupload mit mindestens 100 Dateien

1. Mehrfachauswahl oder Drag-and-drop öffnet eine Liste mit Dateiname, Größe, Typ und entfernbaren Einträgen. Auf Touch-Geräten steht dieselbe Mehrfachauswahl über den Dateidialog bereit. Ein bestehendes PDF wird nicht in einzelne Dokumente zerlegt.
2. `POST /api/v1/upload-batches` legt ein Manifest mit mindestens 100 möglichen Einträgen und stabilen `client_item_id`s an. Die Response enthält `batch_id`, Item-IDs und Limits. Metadatenprüfung vorab ersetzt keine serverseitige Dateiprüfung.
3. Der Browser überträgt Dateien gestreamt über `PUT /upload-batches/{batch_id}/items/{item_id}/file`, standardmäßig höchstens zwei gleichzeitig. Jeder Request enthält genau eine Datei und einen Idempotency-Key. 100 Dateien werden weder vollständig in RAM geladen noch in einem riesigen Multipart-Request gebündelt. Die getrennten Dateiübertragungen erzeugen keine getrennten Polling-Schleifen.
4. Jede erfolgreich angenommene Datei wird sofort dauerhaft gespeichert und eingereiht; die Verarbeitung wartet nicht auf den letzten Upload. Ein globaler schwerer Worker verarbeitet Dokumente nacheinander, FIFO nach dauerhafter Annahme innerhalb derselben Prioritätsklasse. Uploadparallelität ist unabhängig von Verarbeitungsparallelität. Die UI zeigt die tatsächliche Queue-Reihenfolge; sie kann bei zwei Uploads von der Auswahlreihenfolge abweichen.
5. Eine Dublette oder fehlerhafte Datei betrifft nur ihren Eintrag. Bereits angenommene Dateien bleiben gespeichert und die übrigen laufen weiter. Die UI zeigt pro Eintrag „Noch nicht übertragen“, „Wird übertragen“, „Wartet“, „In Verarbeitung“, „Fertig“, „Zu prüfen“, „Doppelt“, „Fehlgeschlagen“ oder „Abgebrochen“.
6. Upload pausieren stoppt weitere Dateiübertragungen; bereits angenommene Dokumente werden weiterverarbeitet. Verarbeitung abbrechen ist eine getrennte Aktion. „Nur fehlgeschlagene wiederholen“ verwendet dieselben Item-IDs; bereits erfolgreiche Einträge werden nicht erneut angelegt. Fehlende lokale Dateien müssen nach einem Browser-Neustart gegebenenfalls erneut ausgewählt werden.
7. Der serverseitige Stapel samt angenommenen Dateien überlebt Reload, Logout und Neustart. Ein noch nicht vollständig übertragener Dateikörper wird im MVP ab Dateianfang erneut übertragen; Byte-Range-Resume wird nicht behauptet. Dateiname/Größe sind nur Zuordnungshilfen, die endgültige Dublettenprüfung verwendet SHA-256.

Das Dashboard zeigt getrennte Zähler für Upload und Verarbeitung, beispielsweise „100 ausgewählt · 80 angenommen · 19 noch lokal · 1 Uploadfehler“ und „80 angenommen · 32 fertig · 5 zu prüfen · 1 läuft · 42 warten“. Serverzähler schließen den Browserfortschritt nicht ein. Ein Stapel gilt erst als abgeschlossen, wenn alle Einträge terminal sind; `needs_review` ist ein abgeschlossenes Verarbeitungsergebnis mit offener fachlicher Prüfung. Nicht übertragene Einträge lassen sich nach Rückfrage explizit überspringen. Keine automatische Dokumentlöschung beim Schließen der Stapelansicht.

### Mehrseitige Kamera- und Bilddokumente

Der Pflichtablauf lautet „Neues Dokument → Scannen → Seite aufnehmen → weitere Seite → Seiten prüfen → Speichern“. Ein Foto kann auch als einzelnes Bilddokument gespeichert werden. Im Seitensammler lassen sich vorhandene Bilder ergänzen und zusammen mit Kameraaufnahmen zu einem PDF verbinden.

- Rückkamera bevorzugen, Live-Vorschau und großer Auslöser, sichtbare Seitenzahl, direktes Wiederholen unscharfer Aufnahmen. Kamera erst durch Benutzeraktion aktivieren und beim Verlassen stoppen. Kamerazugriff benötigt HTTPS und Browserfreigabe. [MDN: getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- Falls die Live-Kamera nicht verfügbar oder die Freigabe abgelehnt ist, alternative Aufnahme über Dateieingabe mit Kamera-Hinweis und Bildauswahl anbieten. Die Seitenübersicht funktioniert mit beiden Eingabewegen. Kein verlässliches Weiterfilmen oder Hochladen im iOS-Hintergrund voraussetzen.
- Seitenübersicht mit Miniaturen, Hinzufügen, Entfernen, Neuaufnahme, 90°-Drehung und manuellem Zuschnitt. Reihenfolge per Touch-/Maus-Drag ändern; zusätzlich immer bedienbare „Nach vorne/Nach hinten“-Aktionen und Tastatursteuerung. Vorschau und Seitennummern sofort aktualisieren. Automatische Perspektiverkennung ist nicht erforderlich.
- `POST /capture-sessions` erzeugt einen serverseitigen Entwurf. Bilder einzeln über `PUT /capture-sessions/{id}/pages/{page_id}/file` übertragen, Reihenfolge und Bearbeitungsanweisungen mit Revision über `PATCH /capture-sessions/{id}` speichern. Quelle bleibt unverändert; Bearbeitungen sind nicht destruktiv. Jeweils nur die aktive Vollbildaufnahme und kleine Miniaturen im Browser dekodiert halten.
- Erfolgreich übertragene Seiten bleiben als privater Serverentwurf nach Reload erhalten; „Entwurf gespeichert“ erst nach Serverbestätigung anzeigen. Unübertragene Aufnahmen bei Verbindungsabbruch als ungesichert markieren und vor dem Verlassen warnen, soweit die Plattform es zulässt. Keine dauerhafte lokale Speicherung sensibler Fotos ohne eigene explizite Funktion versprechen.
- „Als PDF speichern“ ruft `POST /capture-sessions/{id}/finalize` mit gewünschter Seitenreihenfolge, Entwurfsrevision und Idempotency-Key auf. Alle ausgewählten Seiten müssen vollständig gespeichert sein. Eine DB-Transaktion friert den Entwurf ein, erzeugt genau ein logisches Dokument und einen Basisjob. Wiederholtes Finalisieren derselben Revision liefert dasselbe Dokument zurück.
- Der Worker führt vor der Textpipeline den Schritt `assembling_document` aus, wendet die gespeicherten Bearbeitungen seitenweise an und schreibt das PDF atomar. Bis dahin ist `storage_key` für das PDF leer, die Quellbilder sind verfügbar. Erst ein vollständiges PDF wird als Standarddatei veröffentlicht; bei Fehler bleiben Quellen und Wiederholungsmöglichkeit erhalten. Die Klassifikation läuft anschließend einmal für das gesamte Dokument.
- Dokumentansicht zeigt mehrseitige Vorschau, Seitennavigation und Download des PDFs sowie der Quellbilder. Ein aus Bildern erzeugtes PDF durchläuft dieselbe OCR wie ein Scan-PDF. Das Zusammensetzen selbst braucht keine zusätzliche KI.
- Startlimits: mindestens 100 Seiten je Kameraentwurf, 100 MB je Quellbild und 1 GB Gesamtgröße je Entwurf; reale Limits sichtbar anzeigen und Speicherbedarf vor Aufnahme/Finalisierung prüfen. Quellen plus generiertes PDF zählen gegen das Speicherbudget. Allgemeine PDF-Uploadlimits gelten separat; intern zusammengesetzte PDFs bekommen ein eigenes Gesamtlimit.
- Abgebrochene Entwürfe explizit verwerfen können; unfinalisierte Serverentwürfe nach sichtbarer Frist (zunächst sieben Tage Inaktivität) bereinigen. Finalisierte Quell-Assets gehören zum Dokument und werden nicht durch Entwurfsbereinigung gelöscht. Gleichzeitige Finalisierung/Bereinigung durch Statusprüfung verhindern.

## 8. State-Machine und Status-API

### Jobzustände

```text
queued ───────────────────────────────► running ─────────► succeeded
scheduled ── Termin + Ressourcen frei ► running ── Fehler ► retry_wait
retry_wait ── not_before erreicht ────► running
running ── dauerhaft / Limit erreicht ──────────────────► failed
queued / scheduled / retry_wait ── Abbrechen ────────────► cancelled
running ── Abbruch anfordern ─────────► cancelling ──────► cancelled
running ── sichere Pause / Zeitfenster endet ────────────► scheduled
running ── Seitenpaket beendet / Queue freigeben ────────► queued
```

Terminale Jobs werden nicht zurückgesetzt. „Erneut versuchen“ erzeugt einen neuen Job/Run mit Bezug auf den alten. `running → scheduled/queued` ist nur nach gespeichertem Checkpoint und Freigabe des Claims erlaubt und zählt nicht als fehlgeschlagener Versuch. Jobzustände ändern ausschließlich API-Kommandos und Worker-Transitionen mit erwarteter Ausgangsversion.

### Schritte der Basispipeline

```text
assembling_document (nur Kameraserien) → extracting_text → ocr (falls erforderlich)
               → indexing → classifying
               → extracting_metadata → finalizing → succeeded
```

Übersprungene Schritte sind explizit `skipped`. Jede OCR-Seite hat einen Checkpoint. Bereits während Extraktion/OCR wird der Suchindex pro abgeschlossenem Seitenpaket aktualisiert und als `partial` markiert; der Schritt `indexing` vervollständigt und prüft diese Projektion. Beim Finalisieren werden zusätzliche Metadaten und Tags übernommen. Thumbnails entstehen früh als begrenzter Teilschritt; ein Vorschaudefekt ist eine Warnung und blockiert keine erfolgreiche Klassifizierung.

### Dokumentzustände sind getrennte Dimensionen

- `processing_state`: `queued | processing | ready | failed`. `ready` bedeutet, dass der Basislauf beendet ist, nicht dass eine Klassifizierung sicher ist. Bei abgebrochenem Erstlauf wird `failed` mit Grund `cancelled` projiziert. Ein gescheiterter Neulauf verwirft kein zuvor nutzbares Ergebnis; dessen Zustand bleibt sichtbar neben dem fehlgeschlagenen Job.
- `classification_state`: `pending | classified | needs_review`. `classified` bedeutet mindestens ein akzeptiertes Dokumenttyp-Tag oder eine explizit manuell bestätigte Tag-Zuordnung. Auch ein neues Themen-Tag darf die manuelle Prüfung abschließen, wenn der Benutzer dies bestätigt.
- `index_state`: `pending | partial | ready | failed`. Bei `partial` zeigt die Suche an, dass einzelne Seiten noch fehlen.
- Geplante OCR-Wiederholungen und Wartungsjobs besitzen eigene Zustände. Ihr Fehler setzt ein nutzbares Dokument nicht auf `failed` zurück.

`needs_review` ist ein fachliches Ergebnis, kein technischer Fehler. Gründe sind beispielsweise `no_matching_rule`, `ambiguous_type`, `low_text_quality`, `no_text` oder `partial_ocr`. Ein vollständiger Extraktionsfehler ergibt zusätzlich `processing_state=failed`. Nutzbarer Teiltext bleibt erhalten und durchsuchbar.

### Gemeinsame Listen-Status-API

`POST /api/v1/processing/status` ist der einzige periodisch verwendete Status-Endpunkt. Der Client übergibt Batch-IDs und/oder Dokument-IDs; auch eine Detailansicht registriert ihre ID bei demselben Polling-Service. Der Server lädt Zustände als Mengenabfrage ohne N+1-Abfragen und liefert Upload- sowie Verarbeitungsstatus gemeinsam.

Beispielrequest für einen kompletten Stapel:

```json
{
  "batch_ids": ["batch-uuid"],
  "document_ids": [],
  "known_revision": null
}
```

Beispielantwort, zur Lesbarkeit mit einem Listeneintrag:

```json
{
  "revision": "opaque-snapshot-token",
  "unchanged": false,
  "batches": [
    {
      "batch_id": "batch-uuid",
      "total": 100,
      "uploaded": 80,
      "upload_failed": 1,
      "waiting_for_upload": 19,
      "ready": 32,
      "needs_review": 5,
      "processing": 1,
      "queued": 42,
      "failed": 0,
      "cancelled": 0,
      "terminal": false
    }
  ],
  "items": [
    {
      "batch_id": "batch-uuid",
      "item_id": "item-uuid",
      "document_id": "doc-uuid",
      "upload_state": "accepted",
      "processing_state": "processing",
      "classification_state": "pending",
      "index_state": "partial",
      "job": {
        "id": "job-uuid",
        "state": "running",
        "step": "ocr",
        "processed_pages": 3,
        "total_pages": 8,
        "attempt": 1,
        "updated_at": "2026-09-09T15:30:00Z",
        "next_run_at": null,
        "error_code": null
      }
    }
  ],
  "poll_after_ms": 2000
}
```

Für einen Stapel mit 100 Dateien enthält eine Antwort alle 100 kompakten Einträge, auch noch nicht angenommene oder bereits abgeschlossene. Dokument-ID und Job sind vor Annahme `null`. Kein Abruf von 100 einzelnen Detailressourcen und kein notwendiges Nachladen je Eintrag. Zusammenfassende Verarbeitungszähler sind disjunkt; `ready` zählt hier nur fertig klassifizierte Dokumente, `needs_review` die separat ausstehende fachliche Prüfung.

Die API liefert je nach Zustand außerdem `review_reasons`, retryable und mögliche Aktionen. Ausführliche Schritthistorie nur beim Öffnen des Verlaufs einmalig laden, nicht für alle 100 Einträge im Poll mitliefern. Keine erfundenen Gesamtprozente: bekannte Seitenzahlen als „OCR: Seite 3 von 8“, sonst indeterminierter Fortschritt. Geplante Jobs zeigen Termin oder Wartegrund.

### Zentraler Polling-Service im Frontend

- Genau ein gemeinsam genutzter Polling-Zyklus pro geöffneter App-Instanz, standardmäßig alle 2 Sekunden während aktiver Verarbeitung. Dokumentliste, Stapelanzeige und Detailansicht abonnieren denselben Store; Komponenten starten keine eigenen Timer oder Requests.
- Ein Request vereinigt aktive Batch-IDs und zusätzlich beobachtete Dokument-IDs, der Server dedupliziert Überschneidungen. Standardgrenze: 500 resultierende Einträge und 10 Batch-IDs je Anfrage, damit ein 100er-Stapel vollständig in einer Antwort bleibt. Größere Abfragen werden mit verständlichem Limitfehler abgelehnt, niemals still gekürzt. Historische Stapel werden separat paginiert geladen, ohne sie vollständig weiterzupollen.
- Die Revision gilt für die gesamte angefragte Auswahl einschließlich Uploadzuständen, Zählern und Entfernungen. Wenn unverändert, genügt `unchanged=true` mit Revision und nächstem Intervall; der Client behält den letzten vollständigen Snapshot. Ändert sich die Auswahl, wird ein neuer vollständiger Snapshot angefordert. Ein tokenloser Request liefert immer alle Zustände der Auswahl.
- Höchstens ein Poll-Request gleichzeitig. Nächsten Timer nach Abschluss starten; bei Navigation veraltete Antworten anhand einer Query-Version ignorieren. Statusänderungen nur in betroffenen Zeilen darstellen, Fokus, Auswahl und Scrollposition erhalten.
- Bei Hintergrundtab oder Netzwerkfehlern bis 30 Sekunden zurücknehmen; bei Rückkehr sofort aktualisieren. Nach terminalem Zustand und ohne weitere aktive Beobachtung stoppen. Nach neuem Upload sofort neu starten; reine geplante Jobs seltener abfragen.
- Der Serverzustand bleibt nach Reload/Login rekonstruierbar. Statuspolling ist unabhängig von den begrenzt parallelen Dateiübertragungen. WebSockets sind nicht erforderlich.

## 9. Worker, Wiederaufnahme und Ressourcensteuerung

- Job mit kurzer `BEGIN IMMEDIATE`-Transaktion und bedingtem Update exklusiv claimen, dann Transaktion vor der Verarbeitung schließen.
- Lease und Heartbeat speichern, beispielsweise 60 Sekunden Lease und 10 Sekunden Heartbeat. CPU-Arbeit läuft in Kindprozessen, damit der Heartbeat weiterläuft.
- Jedes Claim erhält einen neuen `claim_token`. Ergebniswrites prüfen Claim, Run, Dokumentrevision und Löschstatus. Ein abgelöster Worker darf nach Lease-Verlust keine Resultate mehr committen.
- Abgelaufene Leases werden nach Neustart in `retry_wait` überführt. Artefakte pro Run in temporäre Dateien schreiben und erst nach erfolgreicher Prüfung atomar veröffentlichen.
- Maximal drei automatische Versuche insgesamt, mit Backoff; permanente Parserfehler sofort als dauerhaft kennzeichnen. Bei RAM-Fehlern oder Speichermangel kein enger Retry-Loop, sondern sichtbarer Ressourcenfehler.
- OCR und Extraktion seitenweise checkpointen; abgeschlossene Seiten bei Wiederaufnahme wiederverwenden, sofern Original-, OCR- und Pipeline-Version übereinstimmen.
- Dokumente innerhalb derselben Prioritätsklasse nacheinander in Annahmereihenfolge abarbeiten. Seitencheckpointing sichert die Wiederaufnahme, springt aber nicht willkürlich zwischen den 100 Dokumenten eines Stapels. Ein dauerhafter Fehler blockiert die folgenden Dateien nicht; ein Job im Retry-Backoff gibt den Worker bis zu seinem nächsten Versuch frei.
- Vorrang: Upload-/Kamera-Basispipeline, manuelle Wiederholung, geplante hochwertige OCR, Wartung. FIFO innerhalb jeder Klasse; Alterung verhindert dauerhaftes Zurückstellen niedriger Prioritäten.
- Verbindlich ein schwerer Job zur gleichen Zeit: PDF-Zusammenbau, Extraktion/OCR und andere schwere Wartungsarbeiten teilen denselben Worker. Kleine DB-/API-Operationen und gestreamte Uploads laufen parallel.
- Vor schwerer Verarbeitung freien Speicher und RAM-Reserve prüfen. Bei Ressourcenknappheit Job mit Grund verschieben, API und Suche weiter bedienen.
- Beim Eingang eines Uploads laufende geplante OCR/Wartung am nächsten sicheren Seiten-/Transaktionscheckpoint pausieren und später fortsetzen. Ein angenommener Upload bleibt nach Schließen des Browsers in der Serverqueue.
- Soft Deletes, manuelle Änderungen und Tag-Merges werden vor jedem Ergebnis-Commit geprüft. Veraltete Analysen dürfen keine neueren Benutzerentscheidungen überschreiben.

## 10. Textextraktion, OCR und Metadaten

PDFs zuerst seitenweise auf brauchbaren Text prüfen. Textqualität, Ersatzzeichen und relevante Bildflächen berücksichtigen. Eine einzige Textseite darf nicht verhindern, dass die übrigen Scan-Seiten OCR erhalten. Ein Header über einem gescannten Rechnungsbild reicht ebenfalls nicht als Grund, OCR zu überspringen.

Bei Mischseiten Bildbereiche mit mutmaßlichem Text zusätzlich analysieren; aus überlappenden Bereichen nicht denselben Text doppelt indexieren. Extraktionsmethode und Seitenbezug speichern. Die eingesetzte PyMuPDF-Version muss mit entsprechenden Mischseiten-Testdateien geprüft werden. OCR-Ergebnisse werden wiederverwendet, weil OCR erheblich teurer als direkte Textextraktion ist. [PyMuPDF: OCR](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)

OCR-Startprofil: `deu+eng`, etwa 250 DPI, höchstens eine gerenderte Seite gleichzeitig. EXIF-Ausrichtung berücksichtigen, Transparenz auf neutralen Hintergrund reduzieren, Pixelzahl vor Decodierung begrenzen. „OCR erneut mit höherer Qualität“ ist eine optionale UI-Aktion für geplante Verarbeitung. Unscharfe Fotos und Handschrift können unvollständige Ergebnisse liefern; „Text manuell korrigieren“ bleibt verfügbar.

Initial `OMP_THREAD_LIMIT=2` für OpenMP-fähige Tesseract-Builds setzen und auf der Zielhardware gegen 1 vergleichen. Das ist eine Startkonfiguration, kein behauptetes Optimum. [Tesseract: FAQ](https://tesseract-ocr.github.io/tessdoc/FAQ.html)

Automatische Basis-Metadaten: Titelvorschlag, erkannter Absender, eindeutig belegtes Dokumentdatum sowie Betrag/Währung und Fälligkeit bei eindeutigen Regeln. Evidenz und Quelle je Feld speichern. Mehrdeutige Datums- oder Betragskandidaten bleiben Vorschläge. Automatische Zusammenfassungen sind nicht Bestandteil dieser Version.

Ein OCR-Textlayer-PDF ist optional und unabhängig von der Suchfähigkeit; die Volltextsuche benötigt kein neu geschriebenes PDF. Digitale Originale und Signaturen bleiben unverändert erhalten.

## 11. Automatische Klassifizierung und manuelle Prüfung

### Schnelle lokale Basisklassifizierung

1. Text und Metadaten normalisieren, Sprache grob ermitteln.
2. Bekannte Aliase auf kanonische Tag-IDs auflösen.
3. Deterministische Regeln mit positiver und negativer Evidenz anwenden: beispielsweise „Rechnungsnummer“ oder „Invoice number“ zusammen mit Rechnungsbetrag, nicht nur das einzelne Wort „Rechnung“.
4. Dokumenttyp und zusätzliche Themen-Tags vorschlagen, Belegstellen und Regelversion speichern.
5. Nur bei hinreichender und widerspruchsfreier Evidenz automatisch akzeptieren, sonst `needs_review`.

Regel-Scores sind keine statistisch kalibrierten Wahrscheinlichkeiten. Die automatische Annahme wird zunächst über konkrete Evidenzregeln und Konfliktprüfungen gesteuert. Schwellen später anhand eines getrennten, manuell bewerteten Testsatzes festlegen.

Der Provider liefert ein validiertes Schema aus Tag-ID-Vorschlägen, Feldvorschlägen, Evidenz, Provider-Version und Prüfgründen. Regeln referenzieren kanonische Tag-IDs. Dokumenttext bleibt Eingabedatum und löst keine ausführbaren Anweisungen aus.

### Tab „Zu prüfen“

Filter: `classification_state=needs_review`, auch bei technischen Basisfehlern; zusätzlich eigener Fehlerfilter in „Verarbeitung“. Die Ansicht zeigt Vorschau, erkannten Text, Ursache, mögliche Tags und Mehrfachauswahl.

Aktionen:

- Bestehende Tags über Suche auswählen oder neue Tags samt Aliasprüfung anlegen.
- Mehrere Dokumente gemeinsam zuordnen.
- Metadaten oder OCR-Text korrigieren.
- „Zuordnung bestätigen“ speichert manuelle Entscheidungen und entfernt das Dokument aus „Zu prüfen“.
- „Später prüfen“ belässt es in der Liste; „OCR erneut versuchen“ erstellt einen neuen Basislauf.
- Optional „Regel daraus erstellen“ mit Bedingungen und Vorschau auf betroffene Dokumente. Eine Einzelkorrektur erzeugt keine unsichtbare globale Regel.

Bei Textkorrektur wird die Suchprojektion unmittelbar aktualisiert; eine noch laufende alte Analyse darf die Korrektur nicht zurückschreiben. Bereits manuell bestätigte Klassifikation bleibt bei Reprocessing erhalten. Manuelle Zuordnung behebt keinen technischen OCR-Fehler: Dieser bleibt in der Verarbeitung sichtbar, die Klassifikation kann trotzdem abgeschlossen sein.

## 12. Lokale Volltextsuche

FTS5 ist von Anfang an Pflicht. Der Container-Starttest prüft die Erweiterung. Indexiert werden Seiten-/OCR-Text, Titel, ursprünglicher Dateiname, Absender, Tags samt Aliasen.

Tokenizer zunächst `unicode61` mit normalisierter Akzentsuche; Wörter, Phrasen und explizite Präfixsuche unterstützen. Ergebnisse nach `bm25()` gewichten und Ausschnitte anzeigen. Tokenbasierte Suche garantiert weder beliebige Wortbestandteile noch Übersetzungen oder Fehlertoleranz. [SQLite: FTS5](https://www.sqlite.org/fts5.html)

- Ein zentrales Suchfeld; etwa 250 ms Debounce, Pagination und begrenzte Trefferzahl.
- Kombinierbar mit Ordner, Unterordnern, mehreren Tags (explizit `all` oder `any`), Datum, Absender und Prüf-/Jobzustand.
- Eigentümerfilter zwingend auch auf FTS-Abfrage, Trefferzahlen und Facetten anwenden.
- Texteingaben sicher in FTS-Syntax übersetzen; keine ungeprüften Suchoperatoren oder SQL-Fragmente übernehmen. Snippets HTML-escapen.
- Suchprojektion und FTS-Update zusammen mit akzeptierten Text-/Metadatenänderungen transaktional aktualisieren. Rename/Merge von Tags aktualisiert auch betroffene Projektionen.
- Suchindex aus DB-Inhalten neu aufbauen können; fehlende OCR ist gesondert nachzuholen.
- Treffer nennen nach Möglichkeit die Seite; diese kann für ausgewählte Treffer aus gespeicherten Seitentexten ermittelt werden.
- Bilder sind über tatsächlich erkannten Text auffindbar. Objekt-/Motiverkennung ist keine zugesagte Funktion der Wortsuche.

Der Suchumfang dieser Version ist lokale Wort-, Phrasen- und Präfixsuche über extrahierten/OCR-erkannten Text.

## 13. Leistung auf 4 Kernen / 6 GB RAM

Die folgenden Angaben sind Planungsgrößen, keine Messwerte. CPU-Modell, RAM-Bandbreite, Datenträger, Seitenzahl und Scanqualität sind noch unbekannt. Diese Version beschränkt sich auf die folgenden drei Funktionsgruppen:

| Funktion | Erwartete Belastung / Größenordnung | Standard |
| --- | --- | --- |
| Direkte PDF-Textextraktion, Regeln, FTS-Abfrage | Gering; für typische kleine Dokumente interaktiv bis wenige Sekunden | Sofort nach Upload |
| Tesseract-OCR | CPU-intensiv; Sekunden bis deutlich länger pro Seite, lange Stapel entsprechend mehrere Minuten | Sofort einreihen, ein Worker, Fortschritt pro Seite |
| OCR in höherer Auflösung, große Neuindizierungen | Längere Stapelverarbeitung | Manuell oder Zeitfenster |

Startbudget als zu überprüfendes Deploymentprofil: maximal 2 CPU-Kerne für schwere Verarbeitung, bis etwa 3 GiB für den gesamten schweren Prozessbaum; ungefähr 1 GiB für API/Web/Scheduler und verbleibender Speicher für Linux, SQLite-Cache und Reserve. Container-/cgroup-Limits setzen die harten Grenzen durch. Der Worker beendet einen Kindprozess kontrolliert bei Timeout, bevor weitere Jobs zugelassen werden.

100 angenommene Dateien sind Queue-Einträge, nicht 100 laufende Parser. Der Worker hält nur das aktuelle Dokument und höchstens eine voll gerenderte Seite gleichzeitig im Arbeitsspeicher. Auch beim Kamera-PDF-Zusammenbau Bilder nacheinander lesen, einfügen und freigeben; den tatsächlichen Speicherbedarf des PDF-Writers messen und die Gesamtgrenze durchsetzen. Vorschaubilder bedarfsgesteuert laden.

Die UI zeigt gemessene Laufzeitbereiche, Queue-Fortschritt und Warnungen bei Speicherknappheit. Ohne Messung steht „Noch nicht gemessen“. Die Standardsuche benötigt weder erneute OCR noch Dokumentneuverarbeitung. Ein Zeitplan verlagert CPU-Arbeit, hebt aber keine RAM-/Speicherlimits auf.

## 14. Zeitpläne vollständig über die UI

Seite „Einstellungen → Verarbeitung“:

- OCR-Sprachen aus lokal installierten Paketen, Qualitätsprofil, Klassifizierungsregeln, Tag-Aliase und konservative automatische Annahme einstellen.
- Pro optionalem Jobtyp `deaktiviert`, `nur manuell`, `sofort` oder `nach Zeitplan` wählen.
- Jobtypen: hochwertige OCR-Wiederholung, Suchindex-Neuaufbau und lokaler Export.
- Einmaligen Termin oder wiederkehrende Wochentage mit Uhrzeit und Zeitfenster wählen, etwa täglich 02:00–05:00, Zeitzone `Europe/Berlin`.
- Umfang über Ordner/Tags/Prüfstatus, „nur fehlende/veraltete Ergebnisse“ und Dokumentlimit pro Lauf bestimmen.
- CPU-Wunschlimit, Tageslaufzeitbudget, Timeout und Priorität innerhalb serverseitiger Grenzen einstellen.
- Nächste Ausführung, aktuellen Wartegrund, Queue, Fortschritt, letzte Laufzeit, Fehler und Verlauf sehen.
- „Jetzt ausführen“, „Pausieren“, „Abbrechen“ und „Erneut versuchen“ anbieten. „Jetzt“ umgeht nie die RAM-/CPU-Grenzen und verdrängt keine Upload-Basispipeline.

Einstellungen und Zeitpläne liegen versioniert in SQLite und wirken ohne Deployment. Benutzer konfigurieren nur ihre Jobs. Gemeinsame Ressourcenobergrenzen kommen aus ENV; das UI zeigt sie an und erlaubt keine Überschreitung. Eine globale Benutzer-/Rollenverwaltung wird dafür nicht benötigt.

Der Scheduler läuft serverseitig, auch bei geschlossener PWA. Fällige Läufe atomar claimen; `(schedule_id, occurrence_at)` verhindert doppelte Läufe. Filter werden beim Start ausgewertet, Input- und Einstellungsrevision je Job gespeichert. Vor Ausführung aktuelle Zugriffsrechte und Löschstatus prüfen.

Sommerzeit explizit behandeln: nicht existierende Uhrzeit am Umstellungstag zur nächsten gültigen lokalen Uhrzeit ausführen, doppelte Uhrzeit nur einmal. Nach Ausfall verpasste Termine zu höchstens einem Nachhollauf zusammenfassen, der das nächste zulässige Zeitfenster respektiert. Pausierte Pläne starten nichts neu; aktive Jobs lassen sich separat abbrechen. Überlappende Pläne deduplizieren dieselbe Dokument-/Job-/Versionskombination.

Am Fensterende keine neuen schweren Schritte beginnen. Laufende OCR-Seite beziehungsweise kleine Indextransaktion bis zum begrenzten Timeout abschließen, Checkpoint speichern und Rest auf das nächste Fenster verschieben. Die mögliche kurze Überschreitung und der Wiederanlauf sind in der UI erklärt.

Die Basisklassifizierung nach Dateiannahme beziehungsweise Finalisieren eines Kamera-Dokuments bleibt immer automatisch aktiv. Zeitpläne verschieben hochwertige Wiederholungen und Wartung. Stapeluploads werden ohne zusätzliche Freigabe nacheinander abgearbeitet.

## 15. API-Vertrag

Alle fachlichen Endpunkte liegen ausschließlich unter `/api/v1`. OpenAPI und gemeinsame Schema-Tests verhindern abweichende Frontend-/Backend-Feldnamen.

| Bereich | Endpunkte |
| --- | --- |
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /me` |
| Dokumente | `POST /documents`, `GET /documents`, `GET/PATCH/DELETE /documents/{id}` |
| Inhalte | `GET /documents/{id}/file`, `GET /documents/{id}/thumbnail`, `GET /documents/{id}/pages`, `PATCH /documents/{id}/pages/{page}`, `GET /documents/{id}/assets`, `GET /documents/{id}/assets/{asset_id}/file` |
| Viewer | `GET /documents/{id}/viewer` (Manifest), `GET /documents/{id}/search?q=...` (Trefferliste mit Seite/Koordinaten), `GET /documents/{id}/pages/{page}/preview?size=...` (begrenzte Vorschaugrößen) |
| Stapelupload | `POST/GET /upload-batches`, `GET/PATCH /upload-batches/{id}`, `PUT /upload-batches/{id}/items/{item_id}/file`, `PATCH /upload-batches/{id}/items/{item_id}` (z. B. überspringen) |
| Kameraentwürfe | `POST/GET /capture-sessions`, `GET/PATCH/DELETE /capture-sessions/{id}`, `PUT /capture-sessions/{id}/pages/{page_id}/file`, `POST /capture-sessions/{id}/finalize` |
| Verarbeitung | `POST /processing/status` (gemeinsame Liste nach Batch-/Dokument-IDs), `POST /documents/{id}/reprocess` |
| Prüfung | `GET /documents?classification_state=needs_review`, `POST /documents/{id}/review`, `POST /documents/bulk-review` |
| Ordner | `GET/POST /folders`, `PATCH/DELETE /folders/{id}`, `PUT/DELETE /documents/{id}/folders/{folder_id}` |
| Tags | `GET/POST /tags`, `PATCH/DELETE /tags/{id}`, `POST /tags/{id}/aliases`, `DELETE /tags/{id}/aliases/{alias_id}`, `POST /tags/{id}/merge`, `PUT/DELETE /documents/{id}/tags/{tag_id}` |
| Regeln | `GET/POST /rules`, `PATCH/DELETE /rules/{id}`, `POST /rules/{id}/preview` |
| Jobs | `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`, `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry` |
| Einstellungen | `GET/PATCH /settings`, `GET /system/capabilities` |
| Zeitpläne | `GET/POST /schedules`, `PATCH/DELETE /schedules/{id}`, `POST /schedules/{id}/preview`, `POST /schedules/{id}/run-now` |
| Export | `POST /exports`, `GET /exports/{id}` (lokaler Jobstatus) |

Beispielsuche: `GET /api/v1/documents?q=Stromrechnung&tag_ids=<uuid>&folder_id=<uuid>&include_descendants=true&tag_mode=all`.

Bibliotheks- und Historienlisten paginieren; Sortierung stabil mit ID als Tie-Breaker. Die Statusliste für einen 100er-Stapel wird vollständig in einem Request geliefert und nicht in 100 Detailrequests aufgeteilt. Änderungen verwenden Revision/`If-Match`; bei Konflikt `409` mit Möglichkeit zum Neuladen. Bulk-Aktionen begrenzen und Ergebnisse pro Dokument zurückgeben. Jobs werden idempotent angenommen. Fehlermeldungen bestehen aus maschinenlesbarem Code und übersetzbarem UI-Text ohne interne Pfade oder Stacktraces.

## 16. Verbindliches UI-/UX-Design und Authentifizierung

### Designqualität und Responsivität

Die UI ist ein zentraler Liefergegenstand. Vor der Feature-Umsetzung ein durchgängiges visuelles Konzept für Bibliothek, Dokumentdetail, Kamera, 100er-Upload und manuelle Prüfung ausarbeiten; dieselben Komponenten und Interaktionsmuster konsequent verwenden. Visuelle Abnahme gehört zu jeder Phase, nicht erst zum Abschluss.

- Ruhige, hochwertige Gestaltung mit klarer Typografiehierarchie, konsistentem Abstandsraster, lesbaren Zeilenlängen, abgestimmten neutralen Flächen und einer gezielten Akzentfarbe. Eigene Design-Tokens für Schrift, Abstand, Radien, Farben, Fokus und Bewegung; keine zufälligen Komponentenstile pro Bildschirm.
- Helles und dunkles Theme mit Systemvorgabe und UI-Umschalter. Icons einheitlich und bei unklarer Bedeutung beschriftet. Keine Funktion nur hinter Hover, Long-Press, Swipe oder Drag-and-drop verstecken.
- Inhaltsabhängige Layoutwechsel statt fest verdrahteter Gerätemodelle: kontinuierlich ab 320 CSS-Pixel Breite bis mindestens 3840 testen, darüber flexibel weiter skalieren. Browserzoom bis 200 %, vergrößerte Schrift, Hoch-/Querformat und wechselnde Fenstergrößen unterstützen. Keine abgeschnittenen Primäraktionen oder horizontales Scrollen der gesamten App; Vorschauflächen dürfen separat zoombar sein.
- Desktop breit: Ordner-/Tabnavigation links, flexible Dokumentliste mittig und optional Detailvorschau rechts. Auf sehr breiten Displays Platz für Inhaltsvorschau und zusätzliche Spalten nutzen, Texte aber nicht endlos strecken. Bei schmalem Fenster Seitenleiste einklappen und Tabelle in kompakte Liste überführen.
- iPad: je verfügbarer Breite ein- oder zweispaltige Navigation, gleichwertig für Touch, Trackpad und Tastatur. Split View, schmale Multitasking-Fenster sowie Hoch-/Querformat einbeziehen; ein iPad darf nicht allein wegen seiner Bildschirmdiagonale dauerhaft das Desktoplayout erhalten.
- iPhone: klare einspaltige Ansichten, große Dokumentzeilen, zugängliche Hauptnavigation und gut erreichbare Aufnahme-/Uploadaktion. Filter und Mehrfachaktionen in passenden Sheets; Detailvorschau mit eigenständiger Seitennavigation. Safe Areas, dynamische Browserleisten und Bildschirmtastatur berücksichtigen; Eingabefelder und „Speichern“ dürfen nicht verdeckt werden.

### Touch, Tastatur und Rückmeldungen

Für diese Web-UI beträgt die Mindest-Trefferfläche interaktiver Touch-Elemente 44 × 44 CSS-Pixel, zentrale Kameraaktionen größer. Dies ist die konkrete Web-Designvorgabe; Apples Plattformempfehlung verwendet 44 × 44 pt. Ausreichende Abstände verhindern Fehlberührungen. [Apple: UI Design Tips](https://developer.apple.com/design/tips/)

- Touch-Reordering mit erkennbarem Griff und Scrollschutz; dieselbe Aktion zusätzlich über Buttons. Mehrfachauswahl über expliziten Auswahlmodus/Checkboxen auf allen Geräten. Desktop bietet zusätzlich Shift-Auswahl, Drag-and-drop und dokumentierte Tastaturkürzel.
- Sinnvolle Tab-Reihenfolge, sichtbarer Fokus, Escape-/Zurück-Verhalten, Fokusführung in Dialogen und beschriftete Controls. VoiceOver auf iPhone/iPad und Tastaturbedienung real testen. Status nie nur per Farbe anzeigen.
- PDF-/Bildvorschau unterstützt Touch-Zoom, Panning und Seitenwechsel ohne Konflikt mit der Appnavigation. Zoom und Seitenauswahl zusätzlich als Buttons; keine erzwungene Deaktivierung des Browserzooms.
- Ladezustände mit passenden Skeletons, hilfreiche leere Zustände und konkrete Fehler mit Wiederholungsaktion. Optimistische Ordner-/Tagänderungen nur mit Rollback; Upload erst nach Serverbestätigung als gespeichert markieren.
- Dezente kurze Übergänge mit `prefers-reduced-motion`-Berücksichtigung. Keine springenden Listen beim Polling; Scrollposition, ausgewählte Dateien und Eingabefokus bleiben stabil. Screenreader erhalten zusammengefasste Fortschrittsmeldungen statt 100 Live-Meldungen alle zwei Sekunden.
- Ein Stapel-Panel bleibt beim Navigieren erreichbar und zeigt Gesamtfortschritt plus betroffene Dateien. Große Listen nur bei nachgewiesenem Bedarf virtualisieren und dabei Fokus/Zugänglichkeit erhalten; Thumbnails lazy laden. Die UI bleibt während Upload, Kameraaufnahme und OCR flüssig bedienbar.

### Kernansichten

Navigation: „Alle Dokumente“, angeheftete Tag-Tabs wie „Rechnungen“, „Zu prüfen“ mit Zähler, „Verarbeitung“, Ordnerbaum und „Einstellungen“. Alle Listen teilen Suche, Filter und Mehrfachauswahl.

Dokumentdetail: Originalvorschau, Seiten-/OCR-Text, Statusverlauf, Ordner, Tags, Metadaten, Vorschläge und manuelle Korrekturen. „Neu analysieren“ erklärt, welche automatisch erzeugten Daten aktualisiert werden. Manuelle Daten bleiben geschützt. Tags und Status dürfen nicht ausschließlich über Farben unterscheidbar sein; Tastaturbedienung und mobile Layouts sind Pflicht.

### Integrierter Bild- und PDF-Viewer

„Online“ bedeutet direkt innerhalb der Web-App: Dateien werden ausschließlich vom eigenen Server geladen und im Frontend angezeigt. Der Viewer ist ein eigener Pflichtbestandteil der Dokumentansicht und kein externer Viewer-Dienst. Dieselbe Oberfläche funktioniert eingebettet als Desktop-Vorschau und als großzügige Vollansicht auf iPhone/iPad.

**PDFs:** PDF.js lokal in einer getesteten, festgelegten Version einbinden; Worker und Bibliothek müssen dieselbe Version haben. Rendering, Textauswahl und vorhandene PDF-Navigation auf der PDF.js-Basis aufbauen, Toolbar und responsive Bedienung in das eigene Designsystem integrieren. [PDF.js: Getting Started](https://mozilla.github.io/pdf.js/getting_started/)

- Seitenminiaturen in ausklappbarer Leiste beziehungsweise mobilem Sheet, „Seite X von Y“, direktes Anspringen einer Seite und nächste/vorherige Seite.
- Scrollansicht und Einzelseitenmodus; breite Desktopansicht darf zusätzlich Doppelseiten anzeigen. Vorhandene PDF-Lesezeichen/Inhaltsverzeichnisse sowie interne Seitenlinks unterstützen.
- Zoom mit Plus/Minus, Prozentwert, „Seitenbreite“, „Ganze Seite“, Pinch-to-zoom und Double-Tap; Panning bei Vergrößerung. Maus-/Trackpad-, Touch- und Tastaturbedienung funktionieren ohne Springen des betrachteten Ausschnitts.
- „Großansicht“ füllt die Appfläche. Echten Browser-Vollbildmodus nur bei Verfügbarkeit zusätzlich nutzen; die Großansicht funktioniert auch ohne Fullscreen-API. Zurückschließen stellt Listenposition, Auswahl und Fokus wieder her.
- Seitenrotation ausschließlich als Anzeigeeinstellung, kein Überschreiben des Originals. Text bei vorhandener Textebene auswählen/kopieren; vorhandene Annotationen darstellen. Bearbeitung, Signieren, Schwärzen und ein PDF-Editor gehören nicht zum Viewerumfang.
- Original herunterladen und Drucken über den Browser anbieten; Druckumfang und hohe Speicherlast bei großen Dokumenten verständlich behandeln. Zum Drucken keine 300 Seiten auf einmal in maximaler Bildschirmauflösung rendern.

**Bilder:** JPEG, PNG und WebP direkt mit demselben Zoom-/Pan-/Rotationsverhalten anzeigen. HEIC serverseitig in eine browserkompatible Vorschau ableiten und das unveränderte Original zum Download erhalten. Kleine Vorschau zuerst anzeigen, passende höhere Auflösung bei Bedarf nachladen; wenige begrenzte Varianten statt beliebiger serverseitiger Resize-Parameter. Auflösung transparent halten, damit Text nicht nur als unscharfes Thumbnail lesbar ist. Bei Kameradokumenten zwischen Gesamt-PDF und geordneten Quellbildern wechseln können.

**Suche im geöffneten Dokument:** Ein Suchfeld mit Trefferzahl, vorherigem/nächstem Treffer und automatischem Sprung zur passenden Seite. Es nutzt dieselben gespeicherten PDF-/OCR-Texte wie die globale Suche. Treffer auch in Scans und Bildern hervorheben, sobald Wortpositionen vorliegen. Tesseract-Wortboxen und PDF-Textpositionen zusammen mit Seitenmaßen, Textoffsets und Transformationsversion speichern; Rotation, Zuschnitt, Zoom und Bildskalierung bei der Anzeige berücksichtigen. Keine erneute OCR beim Suchen.

Fehlen Positionen oder wurde OCR-Text manuell verändert, die ungültige Positionszuordnung verwerfen und stattdessen Seite plus markierten Textausschnitt im Textpanel anzeigen. Keine falschen Bildmarkierungen vortäuschen. Bei laufender OCR „Erkannter Text noch unvollständig“ zeigen und auf die über den gemeinsamen Status-Store erkannte neue Textversion reagieren. Dokumenttreffer werden als Liste geladen, nicht einzeln pro Seite gepollt. Globale Suchtreffer öffnen den Viewer direkt an der betreffenden Seite; ohne sichere Koordinate wird die Seite geöffnet.

**Ladeverhalten und Speicher:** `GET /documents/{id}/viewer` liefert Format, verfügbare Varianten, Seitenzahl soweit bekannt, Seitengrößen soweit vorhanden, Textversion und autorisierte relative URLs. Ein validiertes hochgeladenes Original ist vor Abschluss seiner OCR sichtbar. Während Kamera-PDFs noch zusammengesetzt werden, zeigt der Viewer bereits angenommene Quellseiten mit Hinweis auf den Zusammenbau. Ist eine Variante noch nicht verfügbar, wird ein fachlicher Zustand mit Wiederholungsmöglichkeit geliefert, keine kaputte Vorschau.

PDF-Dateiendpunkte unterstützen autorisierte HTTP-Range-Anfragen mit `206`, `Content-Range`, `Accept-Ranges` und konsistenter Dateilänge; ungültige Bereiche liefern `416`. PDF.js bekommt die autorisierte URL direkt, nicht erst einen vollständig vorab geladenen Blob. Range/Streaming anhand der eingesetzten PDF.js-Version testen; benötigte Inhalte hängen auch von der internen PDF-Struktur ab. [PDF.js: FAQ](https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions)

Nur sichtbare Seiten und einen kleinen Nachbarpuffer rendern, Miniaturen separat begrenzen, entfernte Canvases/Bitmaps freigeben und veraltete Renderjobs abbrechen. Retina-Auflösung unter einem Pixelbudget halten; auf iPhone bei Bedarf begrenzen und nach abgeschlossenem Zoom schärfer rendern. Große Dokumente dürfen nicht sämtliche Seiten gleichzeitig im RAM halten. Viewerassets einschließlich Fonts/CMaps lokal ausliefern; Browser-PDF-Skripting deaktivieren, externe Links nur auf bewusste Benutzeraktion öffnen. Range-, Bild- und OCR-Endpunkte behalten Sessionprüfung, Eigentümerfilter und privaten Cache-Schutz.

Viewerzustand (Seite, Zoommodus, Anzeigeoptionen) innerhalb der Sitzung pro Dokument erhalten. Ein Renderingfehler zerstört kein Dokument: verständlichen Fehler, erneutes Laden, gegebenenfalls vorhandene Bildvorschau und Originaldownload anbieten. Automatische Statusaktualisierung benutzt den zentralen Listen-Polling-Service; der Viewer eröffnet keine zusätzliche Polling-Schleife.

### Authentifizierung und PWA-Datenschutz

Kein Benutzerkonto wird über die UI angelegt. `APP_USERS_JSON` enthält Benutzerkennungen und Argon2-Hashes. Login prüft den Hash einmal und setzt eine zufällige Session-ID als `Secure`, `HttpOnly`, `SameSite=Lax` Cookie; in SQLite liegt nur der Hash der ID. Session hat Ablauf und Idle-Timeout. Passwortänderung oder Entfernung aus ENV widerruft Sessions über credential_version bzw. Benutzerprüfung. Kein Passwort und kein Basic-Auth-Header in Browser-Storage.

Schreibende API-Aufrufe prüfen Origin und CSRF-Token; Login drosseln, Session-ID nach Login erneuern. Same-Origin-Cookies funktionieren auch für autorisierte Bild-/PDF-Vorschauen. PDF-Dateiendpunkte unterstützen die für den Viewer festgelegten Range-Requests. Alle APIs einschließlich Suche, Status, Jobs, Exporte und Dateien prüfen den Eigentümer; Health-Endpunkt verrät keine privaten Daten.

Die PWA cached nur App-Shell und statische Assets. APIs, PDFs, Bilder, OCR und Sitzungsdaten werden nicht vom Service Worker dauerhaft gecached; Server antwortet für private Inhalte mit `Cache-Control: no-store`. Logout entfernt clientseitigen Zustand. Fonts, JavaScript und Icons lokal ausliefern; keine CDN-/Analytics-Abhängigkeit.

## 17. Konfiguration, Sicherheit und Betrieb

ENV ist nur für Startkonfiguration, Pfade, Identitäten und harte Sicherheits-/Ressourcengrenzen zuständig, zum Beispiel:

```dotenv
APP_ENV=production
DATA_DIR=/data
DATABASE_URL=sqlite:////data/database/app.sqlite3
MAX_UPLOAD_MB=100
MAX_BATCH_FILES=100
UPLOAD_CONCURRENCY=2
STATUS_MAX_ITEMS=500
MAX_CAPTURE_PAGES=100
MAX_CAPTURE_TOTAL_MB=1024
MAX_ASSEMBLED_PDF_MB=1024
CAPTURE_DRAFT_TTL_DAYS=7
MAX_PDF_PAGES=300
MAX_IMAGE_PIXELS=40000000
HEAVY_JOB_CONCURRENCY=1
HEAVY_CPU_LIMIT=2
HEAVY_MEMORY_MB=3072
OCR_PAGE_TIMEOUT_SECONDS=90
APP_USERS_JSON={"max":"<vollständiger-argon2id-hash>"}
```

Grenzwerte sind konservative Startwerte und werden nach Messung angepasst. `MAX_BATCH_FILES` und `MAX_CAPTURE_PAGES` sind positive Kapazitätsgrenzen; die zugesagte Version muss mindestens 100 Dateien pro Stapel beziehungsweise 100 Kameraseiten erlauben. `HEAVY_JOB_CONCURRENCY=1` bleibt verbindlich. Der Server liefert Upload-/Statuslimits über Capabilities; die UI hält die Uploadparallelität ein. Batch-Manifeste und Entwürfe erhalten zusätzlich benutzerbezogene Speicher-/Anzahlquoten. Freien Plattenplatz laufend prüfen, da 100 Dateien nicht automatisch insgesamt nur 100 MB bedeuten. Die Compose-Limits müssen die ENV-Angaben tatsächlich durchsetzen, nicht nur anzeigen. `.env` und `/data` nicht committen, `.env.example` ohne echte Zugangsdaten. Dollarzeichen in Argon2-Hashes beim tatsächlichen Compose-/ENV-Parsing testen.

Decoder-/Parser-Kindprozesse erhalten Zeit-, CPU-, RAM-, Pixel- und Seitenlimits. Uploads werden gestreamt; Vorschaudateien werden nicht als ausführbares HTML behandelt. Dokumenttexte dürfen keine Shell-Kommandos oder Netzwerkzugriffe auslösen. Keine beliebigen URLs oder Dateipfade aus der UI ausführen.

Lokale Verarbeitung funktioniert nach Bereitstellung aller Assets ohne Internetzugriff; dies wird mit blockiertem Egress getestet. Ein selbstverwaltetes LAN-Zertifikat oder VPN ist möglich; öffentliches ACME benötigt separat Netz für Zertifikatsverwaltung, aber keine Dokumentübermittlung.

Logging: Zeit, Level, Request-/Job-/Dokument-ID, Operation, Laufzeit und Fehlercode. Keine Passwörter, Session-Cookies, OCR-Volltexte oder Dokumentinhalte. Statusseite zeigt Worker-Heartbeat, Queue-Länge und Speicherwarnungen. Log-/Event-Aufbewahrung begrenzen.

## 18. Löschen, Export und Backup

### Dokumente löschen

In einer Transaktion `deleted_at` setzen, aus Suche und Listen entfernen und neue Jobs verhindern. Laufende Jobs abbrechen beziehungsweise beim Commit zurückweisen. Ein persistenter Cleanup-Job entfernt Original, sämtliche Kamera-Quell-Assets, zusammengesetztes PDF und Derived Files anhand geprüfter storage_keys; erst nach erfolgreicher Bereinigung endgültig aus der DB löschen. Fehler sichtbar machen und wiederholen. Damit entstehen bei einem Prozessabsturz weder wieder auftauchende Dokumente noch unkontrollierte Pfadlöschungen. Die UI unterscheidet klar zwischen Dokumentlöschung und bloßer Ordner-/Tag-Entfernung.

### Lokaler Export

Optional über UI oder Zeitplan: Originalkopien einschließlich Kamera-Quellbildern und zusammengestelltem PDF plus JSON-Manifest mit Tags, Aliasen, Ordnerzuordnungen und manuellen Metadaten. Standardexport enthält jedes Dokument einmal unter UUID; ein zusätzlicher lesbarer Export darf Namen mit UUID-Suffix verwenden. Bei mehrfachen Ordnerzuordnungen enthält das Manifest sämtliche Beziehungen. Keine Hardlinks in bearbeitbare Exporte, da Änderungen sonst das Original treffen könnten.

Cloud-/iCloud-/rclone-Sync ist nicht Bestandteil der lokalen Anwendung. Ein externer Exporttransport wäre eine spätere, ausdrücklich aktivierte Erweiterung; Upload und Klassifizierung hängen davon nie ab.

### Vollständige Sicherung

Originaldateien einschließlich Kamera-Quellbildern und finalisierter Seitenreihenfolge/Bearbeitungsanweisungen sind Primärdaten. Ebenso sind SQLite-Metadaten, manuelle Korrekturen, Ordner, Tags, Regeln und Zeitpläne Primärdaten. Nur OCR-Artefakte, Vorschauen und Suchindex sind erneut erzeugbar. Ein Neuaufbau allein aus Originalen stellt die persönliche Organisation nicht wieder her.

MVP-Backupablauf: Anwendung in Wartungsmodus versetzen, neue Mutationen und Jobs anhalten, laufende Schreibvorgänge/Dateiübergaben abschließen, konsistenten SQLite-Snapshot erzeugen und diesen zusammen mit Originalen und Manifest sichern. Mutationen erst nach dem Dateisnapshot beziehungsweise der Kopie wieder freigeben. Damit stimmen DB und Dateibestand überein. Eine laufende WAL-DB nicht einfach nur als `.sqlite3` kopieren; die Online Backup API erzeugt einen konsistenten DB-Snapshot. [SQLite: Backup API](https://www.sqlite.org/backup.html)

Deploymentkonfiguration, ENV-Zugänge und Zertifikats-/Schlüsselmaterial separat geschützt sichern; sie liegen nicht zwingend in `/data`. OCR-Sprachpakete werden über die dokumentierte Image-Version wiederhergestellt. Beim Restore Sessions widerrufen, Leases verwerfen und Jobs kontrolliert fortsetzen. Ein Sicherungsverzeichnis auf derselben Platte ist allein kein Ausfallschutz; zusätzlich auf separates lokales Medium oder selbstverwaltetes Backupziel kopieren.

## 19. Geplante Repository-Struktur

```text
paperless/
├── backend/
│   ├── app/
│   │   ├── api/                 # auth, documents, folders, tags, jobs, schedules
│   │   ├── models/              # SQLAlchemy-Modelle und Constraints
│   │   ├── schemas/             # Versionierte Request-/Response-Schemas
│   │   ├── services/            # storage, capture/pdf_assembly, batches, search, review, export, backup
│   │   ├── processing/          # State-Machine, Queue, Worker, Scheduler
│   │   ├── providers/           # rules, tesseract
│   │   └── config.py
│   ├── migrations/
│   ├── tests/                   # Unit-, Integrations-, Crash-/Recovery-Tests
│   └── pyproject.toml
├── frontend/
│   └── src/app/
│       ├── core/               # API, Auth, Polling
│       ├── features/           # Dokumente, Kamera, Stapelupload, Ordner, Tags, Prüfung, Jobs, Settings
│       └── shared/
├── tests/e2e/
├── fixtures/                   # Ausschließlich synthetische Testdokumente
├── deploy/                     # Container, Proxy, Backup/Restore
├── compose.yaml
├── .env.example
└── implementation.md
```

## 20. Umsetzung in verbindlicher Reihenfolge

| Phase | Ergebnis | Abnahme vor nächster Phase |
| --- | --- | --- |
| 1. Fundament und Designsystem | Backend/Frontend, Compose, HTTPS, Session-Auth, SQLite/FTS5, Ressourcenprofil; responsive UI-Komponenten und visuelle Konzepte für Desktop/iPhone/iPad | Login/Logout, Eigentümertrennung, persistente DB; Kernlayouts mit Touch und Tastatur in breiten und schmalen Ansichten geprüft. |
| 2. Archiv und Organisation | Upload, flacher Speicher, Dubletten, virtuelle Ordner, kanonische Tags/Aliase, Detailansicht mit PDF-/Bild-Viewer, Löschen | Ein Original in mehreren UI-Ordnern; „Invoice“ erzeugt keinen zweiten Rechnungstag; Viewer auf Desktop/Touch bedienbar; keine Fremddatenzugriffe. |
| 3. Queue, Stapel und Listenzustand | Persistente Queue, Worker, State-Machine, Extraktion/OCR mit Positionen, Suchprojektion und Viewer-Suche; 100er-Stapelupload und zentraler Listen-Polling-Service | 100 Dateien werden zuverlässig nacheinander verarbeitet; ein Statusrequest je Pollintervall reicht für alle 100; Reload/Recovery und Suchsprung im Viewer funktionieren. |
| 4. Klassifikation und Prüfung | Regeln, Metadatenvorschläge, `needs_review`, manuelle/Bulk-Zuordnung, Schutz manueller Entscheidungen | Unsichere Dokumente erscheinen in „Zu prüfen“; Korrekturen bleiben nach Neulauf bestehen. |
| 5. Kamera und vollständige PWA | Mehrseitiger Seitensammler, Serverentwürfe, Drehung/Zuschnitt/Reihenfolge, PDF-Zusammenbau, Einzelbilder, mobile Vorschau | iPhone und iPad erstellen mehrseitige PDFs mit korrekter Seitenfolge; Quellen erhalten, PDF-/Bildtext durchsuchbar; Desktop ebenfalls vollständig bedienbar. |
| 6. Zeitpläne und Betrieb | UI-Einstellungen für hochwertige OCR/Neuindizierung, Scheduler, lokaler Export, Backup/Restore, Ressourcen- und Designabnahme | Jobs laufen bei geschlossener UI; vollständige Wiederherstellung belegt; UI und Listenzugriffe unter 100er-Stapellast geprüft. |

Alle sechs Phasen gehören zur geplanten Version. Es gibt keine zusätzliche Advanced-KI-Phase. Designqualität, Responsivität und Touch-Bedienung sind Abnahmekriterien jeder UI-Änderung.

## 21. Prüfplan und Definition of Done

Tests konzentrieren sich auf Datenintegrität und vollständige Benutzerabläufe:

1. Text-PDF, Scan-PDF, Misch-PDF und JPEG/PNG/WebP/HEIC hochladen. Je Format mindestens ein bekanntes Wort finden; bei Mischseiten Bildtext trotz vorhandenem Header finden.
2. Leeres/unscharfes Dokument führt nachvollziehbar nach „Zu prüfen“; beschädigte Dateien und überschrittene Limits werden verständlich behandelt.
3. „Rechnung“, „RECHNUNG“, „Invoice“ und „Invoices“ ergeben dieselbe Tag-ID und denselben Tab. Unbekannte ähnliche Tags bleiben getrennt, bis ein Merge bestätigt ist; konkurrierende Anlage verletzt keine Eindeutigkeit.
4. Manuell bestehendes oder neues Tag zuordnen, Prüfung abschließen und anschließend reprocessen; manuelle Tags, Ausschlüsse und Feldkorrekturen bleiben bestehen.
5. Dokument in zwei virtuellen Ordnern anzeigen. Ordner verschieben/löschen und nachweisen, dass Originalhash und übrige Zuordnung unverändert sind.
6. Worker während OCR beenden und neu starten: Lease-Recovery, höchstens ein akzeptierter Commit, keine verlorenen Originale, Wiederaufnahme ab gültigem Checkpoint.
7. Absturz zwischen Dateispeicherung und DB-Commit sowie zwischen Löschmarkierung und Dateilöschung simulieren; Recovery hinterlässt einen nachvollziehbaren Zustand.
8. Gleichzeitig Benutzerkorrektur, Tag-Merge, Reprocessing oder Löschung ausführen; alte Workerresultate überschreiben nichts und stellen Gelöschtes nicht wieder her.
9. Kalenderplan bei geschlossener UI, Neustart, Zeitumstellung, überlappenden Plänen, RAM-Knappheit und Zeitfensterende prüfen.
10. Eigentümertrennung für Dokumente, Dateien, Suchtreffer, Alias-/Ordnerbeziehungen, Zähler, Jobs und Exporte prüfen; Session-/CSRF- und Logout-Ablauf abdecken.
11. Gesamten Kernablauf mit gesperrtem Internetzugriff testen. Keine externen Fonts, Analyse-APIs oder Cloud-Klassifizierung.
12. Backup auf leerer Installation wiederherstellen und Originalhashes, Kameraquellen samt Seitenreihenfolge/Bearbeitungen, Tags/Aliase, Ordner, manuelle OCR-Korrekturen, Zeitpläne und Suchbarkeit vergleichen.
13. Genau 100 gültige Dateien gemeinsam auswählen, mit maximal zwei Uploads gleichzeitig übertragen und mit maximal einem schweren Worker nacheinander verarbeiten. Zusätzlich einen gemischten Fehlerstapel testen: Dubletten, beschädigte Datei, Uploadabbruch, unzureichender Speicher. Erfolgreiche Einträge bleiben erhalten, Fehler stoppen den Rest nicht.
14. Netzwerk-Trace während eines 100er-Stapels erfassen: pro Pollzyklus genau ein `POST /processing/status`, alle 100 Einträge in einem Snapshot; weder Einzelstatusrequests noch parallele Polltimer bei gleichzeitig sichtbarem Detail-/Stapelpanel. Auswahlwechsel, unveränderte Revisionen und Stop/Restart des Pollings prüfen.
15. Auf realem iPhone und iPad mehrere Seiten aufnehmen, Bilder ergänzen, drehen, zuschneiden, umordnen und als ein PDF speichern. Seitenanzahl/-folge, Quellhashes und Suchwörter je Seite verifizieren. Außerdem einzelnes Bilddokument, 100-Seiten-Zusammenbau unter RAM-Limit, doppeltes Finalisieren und Workerabbruch beim Zusammenbau prüfen.
16. Kamerafreigabe abgelehnt, Dateiauswahl-Fallback, Netzwerkunterbrechung, App in Hintergrund und Reload testen. Bestätigte Serverentwürfe gehen nicht verloren; ungesicherte Aufnahmen werden nie als gespeichert ausgegeben.
17. Visuelle und interaktive Abnahme bei 320, 375, 390, 430, 768, 820, 1024, 1280, 1440, 1920, 2560 und 3840 CSS-Pixel Breite sowie dazwischen beim fließenden Resize; Hoch-/Querformat, iPad-Split-View, 200-%-Zoom, Bildschirmtastatur, Safe Areas und beide Themes prüfen. Browserautomation durch echte iPhone-/iPad-Safari- und installierte-PWA-Tests ergänzen.
18. Alle Kernaktionen mit Touch und ausschließlich Tastatur durchführen: Upload, Kamera, Seitensortierung, Ordner-/Tagverwaltung, Suche, Mehrfachauswahl, manuelle Prüfung. Fokus, VoiceOver, Kontrast, 44-Pixel-Trefferflächen, reduzierte Bewegung und stabile Listen unter laufendem Polling prüfen.
19. Viewer mit Text-PDF, Scan-PDF, gemischten Seitengrößen, vorhandenen Lesezeichen, einem 300-Seiten-PDF und hochauflösenden Bildern testen: schneller erster Inhalt, Seitenwechsel, Miniaturen, Zoom/Pan, Rotation, Großansicht, Textauswahl und Originaldownload. Auf echtem iPhone/iPad darf Blättern nicht zu stetig wachsendem Canvas-Speicher führen.
20. Viewer-Suche in Text-PDF, OCR-PDF und Bild prüft Trefferzahl, Seitensprung und korrekt transformierte Markierungen nach Rotation/Zoom. Manuelle Textkorrektur invalidiert veraltete Boxen. Autorisierung bei Range-Requests, `416`, fehlende Vorschau, HEIC-Fallback und Anzeigen während laufender OCR/Kamera-Zusammenstellung prüfen.

Leistungsmessung auf dem tatsächlichen Linux-Server: festgehaltener synthetischer Bestand von 10.000 Dokumenten mit durchschnittlich drei Seiten, zusätzlich lange Scans und ein OCR-Job unter Last. Zielwerte: p95 unter 300 ms für warme Such-/Listenabfragen, Status unter 200 ms, p95 unter 1 Sekunde für die Annahme nach vollständiger Dateiübertragung und Validierung kleiner Dateien. Cold-Cache-Läufe separat ausweisen. Diese Ziele müssen gemessen werden; sie sind keine bereits belegten Zusagen.

OCR-Laufzeit pro Seite, Queue-Wartezeit, Gesamtzeit jeDokument, CPU und Peak-RAM getrennt erfassen. Zusätzlich Kamera-PDF-Zusammenbau, 100er-Stapel, Browser-Speicher und Listenantwortgröße messen. Bei Überschreitung zuerst Rendering, Vorschauen, Uploadparallelität und interne Seitenpaketgrößen reduzieren, ohne den 100-Dateien-Umfang oder das Listenprinzip aufzugeben. Keine Leistung durch Auslassen notwendiger OCR, verlorene Jobs oder erzwungene Fehlklassifikation vortäuschen.

Fertig ist die Anwendung, wenn ein Upload selbstständig bis zu einer nachvollziehbaren Klassifizierung oder manuellen Prüfung gelangt, Originale unabhängig von UI-Ordnern erhalten bleiben, Synonyme gemeinsam gefiltert werden, erkannter Text lokal suchbar ist, mindestens 100 Dateien nacheinander mit gemeinsamem Listenpolling verarbeitet werden und mehrseitige Kamera-PDFs erstellt werden können. Die UI einschließlich PDF-/Bild-Viewer muss auf Desktop, iPhone und iPad visuell sowie mit Touch/Tastatur abgenommen sein. Hochwertige OCR und Neuindizierung bleiben über die UI planbar.
