# Lokale KI-Klassifizierung mit Ollama & Qwen 3.5

Paperless verfügt über eine zweistufige Pipeline für die Dokumentenanalyse:
1. **OCR-Textextraktion**: PyMuPDF & Tesseract erfassen Text und Wortkoordinaten seitenweise aus PDFs und Bildern.
2. **Semantische KI-Klassifizierung**: Der extrahierte Text wird an eine lokale **Ollama**-Instanz mit dem Modell **`qwen3.5:2b-q4_K_M`** übergeben.

Die KI bestimmt vollautomatisch den Dokumententyp, vergibt passende Tags und extrahiert Metadaten (Titel, Absender, Belegdatum, Fälligkeit, Betrag und Währung).

---

## 1. Kernmerkmale & Parameter

* **Modell:** `qwen3.5:2b-q4_K_M` (4-Bit-Quantisierung, ~1.9 GB RAM-Bedarf, schnell auch auf CPU).
* **Kontextfenster:** **8k Tokens** (`num_ctx: 8192`) – ideal für mehrseitige Verträge und Rechnungen.
* **Keep-Alive & Lifecycle:** **3 Minuten** (`keep_alive: "3m"`).
  * Nach der Verarbeitung eines Dokuments bleibt das Modell 3 Minuten im Arbeitsspeicher/VRAM.
  * Werden innerhalb dieser 3 Minuten weitere Dokumente verarbeitet (z. B. Stapel-Upload), antwortet das Modell sofort (Warm-Start).
  * Nach 3 Minuten Inaktivität entlädt Ollama das Modell automatisch, um den Arbeitsspeicher des Rechners bzw. Servers wieder vollständig freizugeben.
  * Beim nächsten Upload erfolgt ein Kaltstart (ca. 2–4 Sekunden Ladezeit auf moderner CPU/SSD).
* **Thinking-Mode-Steuerung:** Für moderne Modelle wie Qwen 3.5 wird `"think": False` an die Ollama-API übermittelt. Dadurch werden unproduktive interne Denk-Tokens (`<think>`) unterbunden und die strukturierte JSON-Klassifizierung erfolgt deterministisch innerhalb von 1–2 Sekunden.
* **Zero-Downtime-Fallback:** Ist Ollama nicht erreichbar, reagiert nicht rechtzeitig oder tritt ein Fehler auf, greift die Pipeline **ohne Unterbrechung** auf die deterministische Regex-Regel-Engine zurück.
* **Überschreibschutz:** Manuell im Tab „Zu prüfen“ bestätigte Tags oder geänderte Metadaten werden durch die KI niemals überschrieben.

---

## 2. Lokale Einrichtung (macOS)

### Schritt 2.1: Ollama prüfen & starten
Ollama ist auf deinem Mac bereits unter `/usr/local/bin/ollama` installiert und läuft als Hintergrunddienst.

Prüfe den Status im Terminal:
```bash
ollama list
curl -s http://localhost:11434/api/tags
```

Falls Ollama noch nicht gestartet ist, starte die Ollama-App oder führe im Terminal aus:
```bash
ollama serve
```

---

### Schritt 2.2: Modell herunterladen
Lade das gewünschte Modell in Ollama herunter:

```bash
ollama pull qwen3.5:2b-q4_K_M
```

> **Hinweis:** Falls das Tag in deiner Version abweicht oder du ein alternatives Modell testen möchtest (z. B. `qwen2.5:3b` oder `qwen2.5:1.5b`), kannst du dieses herunterladen und den Namen in der `.env` als `OLLAMA_MODEL=...` eintragen.

Teste das Modell kurz im Terminal:
```bash
ollama run qwen3.5:2b-q4_K_M "Hallo! Bestätige kurz deine Funktionsfähigkeit."
```

---

### Schritt 2.3: Konfiguration in der lokalen `.env`
Füge in deiner Projekt-`.env` (im Hauptordner) folgende Konfiguration ein:

```env
# AI / Ollama LLM Classification
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:2b-q4_K_M
OLLAMA_KEEP_ALIVE=3m
OLLAMA_CONTEXT_WINDOW=8192
OLLAMA_TIMEOUT_SECONDS=90
```

---

### Schritt 2.4: Entwicklungsserver starten
Starte wie gewohnt:

1. **Backend:**
   ```bash
   cd backend
   .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
2. **Worker:**
   ```bash
   cd backend
   .venv/bin/python -m app.processing.worker
   ```
3. **Frontend:**
   ```bash
   cd frontend
   npm start
   ```

Beim Hochladen eines Dokuments siehst du in den Worker-Logs:
```text
[INFO] [AIClassifier] Sende Klassifizierungsaufruf an Ollama:
  -> Modell:            qwen3.5:2b-q4_K_M
  -> Kontextfenster:    8192 Tokens
  -> Keep-Alive:        3m
  -> Dateiname:         'rechnung.pdf'
[INFO] [AIClassifier] Erhaltene Ollama-Antwort (JSON):
...
```

---

## 3. Server-Einrichtung (Produktion / Linux)

### Option A: Containerisiert mit Docker Compose (Standard)

In [`compose.yaml`](file:///Users/dominik/Developer/github/paperless/compose.yaml) ist der Dienst `ollama` vorkonfiguriert:

```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: paperless-ollama
    restart: unless-stopped
    volumes:
      - ${PAPERLESS_OLLAMA_DIR:-./data/ollama}:/root/.ollama
    networks:
      - paperless-net
    ports:
      - "${OLLAMA_HOST_BIND:-127.0.0.1}:${OLLAMA_PORT:-11434}:11434"
    environment:
      - OLLAMA_KEEP_ALIVE=3m
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 3072M
```

#### Schritt-für-Schritt auf dem Server:
1. Docker Compose starten:
   ```bash
   cd /opt/paperless
   docker compose up -d
   ```
2. Das Modell **einmalig** im Ollama-Container herunterladen (wird persistent in `./data/ollama` gespeichert):
   ```bash
   docker exec -it paperless-ollama ollama pull qwen3.5:2b-q4_K_M
   ```
3. Der `worker`-Container ist im selben Netzwerk (`paperless-net`) und greift standardmäßig über `http://ollama:11434` auf die KI zu.

---

### Option B: Nativer Ollama-Dienst auf dem Server (Empfohlen bei Nvidia-GPU)

Falls dein Server über eine Nvidia-Grafikkarte verfügt und du Ollama mit Hardware-Beschleunigung nutzen möchtest:

1. Installiere Ollama nativ auf dem Server-Host:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Modell herunterladen:
   ```bash
   ollama pull qwen3.5:2b-q4_K_M
   ```
3. In `/opt/paperless/.env` die URL auf den Host umleiten:
   ```env
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   ```
   *(oder die interne IP des Servers, z. B. `http://172.17.0.1:11434`)*

---

## 4. Strukturierte Metadaten-Extraktion, Sichtbare Tags & Hintergrund-Keywords

### Grammatik-erzwungenes JSON-Schema (Structured Outputs)
Um zu verhindern, dass das Modell bei tabellarischen oder komplexen Dokumenten (wie Notenübersichten, Prüfungslisten, Rechnungsaufstellungen) dokumentspezifische Ad-hoc-JSON-Strukturen erfindet (z. B. `summary`, `detailed_results`, `modules`, `grades`) oder mitten im Stream abbricht, wird die Ollama-API mit einem **strikten JSON-Schema (`format: CLASSIFICATION_JSON_SCHEMA`)** angesprochen.

Dadurch erzwingt die Inferenz-Engine (llama.cpp Grammar Sampler) auf Token-Ebene, dass **ausschließlich** die folgenden standardisierten Felder ausgegeben werden können:

```json
{
  "document_type": "Prüfungsergebnisse",
  "confidence": 0.99,
  "title": "Prüfungsergebnisse Wirtschaft & Management 2025",
  "sender": "Fakultät Wirtschaft & Management",
  "document_date": "2025-12-31",
  "due_date": null,
  "amount": null,
  "currency": "EUR",
  "tags": ["Prüfungsergebnisse", "Wirtschaft", "Studium"],
  "keywords": ["LPM67", "LPM68", "MKG40", "Notenübersicht", "Marketing", "Logistik"],
  "reasoning": "Akademische Noten- und Modulübersicht einer Hochschule."
}
```

### Trennung: Sichtbare Tags vs. Hintergrund-Suchbegriffe
1. **Maximal 3 sichtbare Tags (`tags`):**
   * Das LLM vergibt **höchstens 3 sichtbare Tags** (die Hauptkategorie und maximal 2 thematische Schlagwörter).
   * Diese erscheinen als saubere Pills/Badges im Frontend auf der Dokumentkarte, in der Detailansicht und im Filter.
   * Dadurch bleibt das UI aufgeräumt und übersichtlich ohne unzählige Tag-Chips.

2. **Bis zu 50 Hintergrund-Keywords (`keywords`):**
   * Das LLM generiert bis zu 50 semantische Stichwörter, Fachbegriffe, Synonyme, Abkürzungen und Kontext-Begriffe.
   * **Besonderheit:** Hier sind insbesondere auch Begriffe enthalten, die **gar nicht wörtlich im OCR-Text** stehen (z. B. Synonyme, englische/deutsche Fachausdrücke, übergeordnete Konzepte wie *BPM*, *Cloud Services*, *Eye-Tracking*).
   * **Nicht sichtbar im Frontend:** Diese Keywords werden **nicht** als Tags angelegt und müllen die Tag-Verwaltung nicht voll.
   * **Triggern in der Suche:** Sie werden direkt in den SQLite FTS5-Volltextindex (`search_documents`) aufgenommen. Sucht ein Benutzer im Suchfeld nach einem dieser Begriffe, wird das Dokument sofort gefunden und per BM25 gerankt.

### Dynamische Tag-Erstellung & Freigabe-Workflow:
1. **Neue Kategorien:** Passt keines der vorhandenen Standard-Tags, schlägt die KI eine neue treffende Kategorie vor (z. B. `Forschung`, `Studium`, `Bewerbung`).
2. **Automatisches Anlegen:** Neue Tags werden automatisch angelegt und dem Dokument zugeordnet.
3. **Zwingende Benutzer-Freigabe (`needs_review`):**
   * Wurde ein neuer Tag vorgeschlagen, erhält das Dokument den Status **`needs_review`** mit Grund `new_tag_suggested`.
   * Es erscheint im Frontend im Tab **„Zu prüfen“** (`/review`).
   * Nach Prüfung bestätigt der Benutzer die Zuweisung per Klick auf **„Freigeben & Bestätigen“** (`POST /api/v1/documents/{id}/review`) und das Dokument wechselt auf `classified`.
4. **Standard-Dokumente:** Passt ein Dokument zu einer bestehenden Kategorie mit $\ge 0.75$ Konfidenz (z. B. Rechnungen), wird es vollautomatisch direkt als `classified` abgelegt.

---

## 5. Wartung, Überwachung & Troubleshooting

### Wie prüfe ich, ob das Modell gerade im Speicher liegt?
Führe auf dem Rechner oder im Container aus:
```bash
# Auf dem Mac:
ollama ps

# Im Server-Container:
docker exec -it paperless-ollama ollama ps
```
Liegt das Modell im Speicher, siehst du die Auslastung und die verbleibende Keep-Alive-Zeit. Nach 3 Minuten Inaktivität verschwindet es aus der Liste.

---

### Was passiert bei einem Kaltstart?
Wenn das Modell nach mehr als 3 Minuten entladen wurde, dauert die Bearbeitung des ersten neuen Dokuments etwa 2–4 Sekunden länger, da das Modell von der SSD in den Arbeitsspeicher geladen wird. Alle nachfolgenden Dokumente werden ohne diese Verzögerung verarbeitet.

---

### Was passiert bei Verbindungsproblemen zu Ollama?
Die Pipeline stürzt **nicht** ab. Es wird eine Warnung geloggt und nahtlos auf die deterministischen Regeln zurückgegriffen:
```text
[WARNING] [ai_classifier] Could not connect to Ollama at http://localhost:11434. Falling back to rule-based classifier.
```
Dokumente werden in diesem Fall als `needs_review` oder anhand von Schlüsselwort-Treffern klassifiziert.

---

### Wie wechsle ich das Modell?
Du kannst jederzeit ein anderes Modell ausprobieren (z. B. `qwen2.5:3b` oder `mistral:7b`).
1. Modell pullen: `ollama pull <modellname>`
2. In der `.env` anpassen:
   ```env
   OLLAMA_MODEL=<modellname>
   ```
3. Worker neu starten. Fertig!
