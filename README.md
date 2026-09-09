# Paperless – Private, lokale Dokumentenverwaltung (PWA)

Eine private, vollständig lokal verarbeitende Dokumentenverwaltung als mobile PWA gemäß `implementaiton.md`.

## Kernmerkmale

- **Vollständig lokal**: Keine Dokumente, OCR-Texte oder Metadaten verlassen den Server.
- **Python 3.12+ Backend**: FastAPI, SQLAlchemy 2.0, SQLite WAL-Modus mit kurzen Schreibtransaktionen und `busy_timeout=30000`.
- **FTS5 Volltextsuche**: Integrierte SQLite FTS5 Suche mit `unicode61`-Tokenizer, BM25-Ranking und In-Dokument-Wortbox-Koordinaten.
- **PyMuPDF & Tesseract OCR**: Direkte Textextraktion mit intelligentem Fallback auf Tesseract OCR (`deu+eng`, 250 DPI, seitenweises Checkpointing).
- **Stapelverarbeitung (mind. 100 Dateien)**: Gestreamte Uploads (`UPLOAD_CONCURRENCY=2`), sequentieller Worker (`HEAVY_JOB_CONCURRENCY=1`), zentrales Listen-Polling (`POST /api/v1/processing/status`).
- **Kamera & Multi-Page Scanning**: Mobile Dokumenterfassung mit `getUserMedia`, Rotation, Zuschnitt und atomarem PDF-Zusammenbau.
- **Kanonische Tags & Aliase**: Intelligente Namensnormalisierung (NFKC, casefold), automatische Synonymauflösung (z.B. „Invoice“ -> „Rechnungen“).
- **Virtuelle Ordner**: Beliebige Ordnerbäume mit Zykluserkennung ohne Verschieben von Originaldateien.
- **Tab „Zu prüfen“**: Manuelle Klassifikation und Metadatenkorrektur mit dauerhaftem Überschreibschutz.
- **Automatisierte Zeitpläne**: Zeitfenster-basierte Wartung (hochwertige OCR, Neuindizierung, lokaler Export).
- **Online Backup API**: Konsistente WAL-Datenbanksicherung per SQLite Backup API.

## Schnellstart

### 1. Umgebungsvariablen

Kopieren Sie die Beispielkonfiguration:

```bash
cp .env.example .env
```

### 2. Lokaler Backend-Start

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Worker in einem separaten Terminal starten:

```bash
source backend/.venv/bin/activate
python -m app.processing.worker
```

### 3. Tests ausführen

```bash
./backend/.venv/bin/pytest -v backend/tests
```

### 4. Mit Docker Compose starten

```bash
docker compose up --build
```

### 5. Produktives Deployment auf eigenem Server

Eine vollständige Anleitung für das automatische Deployment via GitHub Actions und die Anbindung an deinen bestehenden Reverse Proxy (Nginx, Nginx Proxy Manager, Caddy, Traefik) für **`paperless.dominikw.de`** findest du in:
👉 **[server.md](file:///Users/dominik/Developer/github/paperless/server.md)**

