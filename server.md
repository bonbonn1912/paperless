# Server-Einrichtung & GitHub Actions Deployment für Paperless

Dieses Dokument beschreibt Schritt für Schritt, wie Paperless für die Domain **`paperless.dominikw.de`** bereitgestellt wird, ohne dass andere bestehende Anwendungen auf deinem Server beeinträchtigt werden.

---

## 1. Architektur & Kollisionsschutz

Damit deine anderen Anwendungen auf dem Server unberührt bleiben:
- **Keine Portkonflikte auf 80/443**: Der Paperless-Web-Container bindet standardmäßig **nur lokal auf `127.0.0.1:8088`** (`PAPERLESS_HOST_BIND=127.0.0.1`). Die öffentlichen Ports 80 und 443 bleiben vollständig deinem bestehenden Reverse Proxy überlassen.
- **Isoliertes Docker-Netzwerk**: Alle Paperless-Dienste (`api`, `worker`, `web`) kommunizieren in einem isolierten Bridge-Netzwerk (`paperless-net`).
- **Ressourcenbegrenzung (Schutz vor Server-Überlastung)**:
  - Worker CPU-Limit: maximal `2.0` Kerne.
  - Worker RAM-Limit: maximal `3072 MB` (3 GB).
  - OpenMP/OCR-Limit: `OMP_THREAD_LIMIT=2` (verhindert Thread-Spikes bei Tesseract).
  - Nur 1 schwerer Job gleichzeitig (`HEAVY_JOB_CONCURRENCY=1`).
- **Builds auf GitHub Actions**: Die rechenintensiven Docker-Builds (Node.js & Python/Tesseract) laufen in GitHub Actions und werden über das GitHub Container Registry (`ghcr.io`) bereitgestellt. Dein Server zieht nur die fertigen Images und wird beim Deployen nicht durch Kompilierungs-Spikes belastet.

---

## 2. Vorbereitung auf deinem Server

### Schritt 2.1: Verzeichnis anlegen
Verbinde dich per SSH mit deinem Server und erstelle das Installationsverzeichnis:

```bash
sudo mkdir -p /opt/paperless/data
sudo chown -R $USER:$USER /opt/paperless
cd /opt/paperless
```

> **Hinweis:** Falls du einen anderen Pfad bevorzugst (z. B. `~/paperless`), kannst du diesen verwenden. Trage ihn später als `SERVER_DEPLOY_PATH` in den GitHub Secrets ein.

### Schritt 2.2: `.env`-Datei erstellen
Erstelle `/opt/paperless/.env` mit deinen individuellen Zugangsdaten:

```bash
cat << 'EOF' > /opt/paperless/.env
# ==============================================================================
# Paperless Server-Konfiguration
# ==============================================================================

DOMAIN=paperless.dominikw.de
PAPERLESS_HOST_BIND=127.0.0.1
PAPERLESS_PORT=8088
PAPERLESS_DATA_DIR=./data

APP_ENV=production
DATA_DIR=/data
DATABASE_URL=sqlite:////data/database/app.sqlite3

# Ein sicherer Zufallsschlüssel (z. B. mit: openssl rand -hex 32)
SECRET_KEY=generiere-hier-einen-langen-geheimen-zufalls-string

# Benutzerzugang: admin / Passwort-Hash (Argon2id)
# Wichtig: In .env-Dateien für Docker Compose müssen Dollarzeichen verdoppelt werden ($$argon2id$$v=19$$...)!
APP_USERS_JSON={"admin":"$$argon2id$$v=19$$m=65536,t=3,p=4$$Fy29plb68Zwy7Mt7TySA6g$$VFIgxAUKS2E24O28/A4gMJ8nUCWmof+o/xIYWiqPYq0"}

# Hardware-Profile (4 Kerne / 6GB RAM)
HEAVY_JOB_CONCURRENCY=1
HEAVY_CPU_LIMIT=2
HEAVY_MEMORY_MB=3072
UPLOAD_CONCURRENCY=2
MAX_BATCH_FILES=100
MAX_UPLOAD_MB=100
OCR_LANGUAGES=deu+eng
EOF
```

### Schritt 2.3: Eigenes Admin-Passwort generieren
Um ein sicheres eigenes Passwort festzulegen, generiere einen Argon2id-Hash (z. B. mit Python auf deinem Server):

```bash
python3 -c '
from argon2 import PasswordHasher
ph = PasswordHasher()
pw = input("Neues Passwort eingeben: ")
# Dollarzeichen für Docker Compose verdoppeln ($ -> $$)
escaped_hash = ph.hash(pw).replace("$", "$$")
print("\nDein Eintrag für .env (APP_USERS_JSON):\nAPP_USERS_JSON={\"admin\":\"" + escaped_hash + "\"}")
'
```

Trage den ausgegebenen Wert in deine `/opt/paperless/.env` ein:
```bash
APP_USERS_JSON={"admin":"$$argon2id$$v=19$$m=65536,t=3,p=4$$..."}
```

---

## 3. Domain & Reverse Proxy konfigurieren

Setze zuerst im DNS deiner Domain `dominikw.de` einen **A-Record**:
- **Host / Subdomain:** `paperless`
- **Ziel / IP:** Die IPv4-Adresse deines Servers

Wähle nun den Reverse Proxy, der bereits auf deinem Server läuft:

### Option A: Bestehender Nginx auf dem Host
Falls auf deinem Server Nginx nativ läuft, erstelle eine neue Konfigurationsdatei:

`/etc/nginx/sites-available/paperless.dominikw.de`:
```nginx
server {
    listen 80;
    server_name paperless.dominikw.de;

    # Let's Encrypt Certbot Challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name paperless.dominikw.de;

    # SSL Zertifikate (werden von certbot eingetragen)
    # ssl_certificate /etc/letsencrypt/live/paperless.dominikw.de/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/paperless.dominikw.de/privkey.pem;

    client_max_body_size 1024M;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Range Requests für PDF.js Streaming
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;

        # Upload-Streaming & Timeout
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Aktivieren und SSL-Zertifikat mit Certbot anfordern:
```bash
sudo ln -s /etc/nginx/sites-available/paperless.dominikw.de /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d paperless.dominikw.de
```

---

### Option B: Nginx Proxy Manager (NPM GUI)
Falls du Nginx Proxy Manager im Docker nutzt:
1. Im NPM-Webinterface auf **Hosts** -> **Proxy Hosts** -> **Add Proxy Host** klicken.
2. **Details:**
   - **Domain Names:** `paperless.dominikw.de`
   - **Scheme:** `http`
   - **Forward Hostname / IP:** `172.17.0.1` (Docker Host Gateway) oder `host.docker.internal` (oder die interne IP des Servers).
   - **Forward Port:** `8088`
   - Haken setzen bei: **Block Common Exploits**, **Websockets Support**.
3. **SSL:**
   - SSL Certificate: *Request a new SSL Certificate*
   - Haken setzen bei: **Force SSL**, **HTTP/2 Support**, **HSTS Enabled**.
4. **Advanced (Custom Nginx Configuration):**
   Füge folgendes ein, damit große Uploads bis zu 1 GB und HTTP Range Requests für den PDF-Viewer einwandfrei funktionieren:
   ```nginx
   client_max_body_size 1024M;
   proxy_request_buffering off;
   proxy_buffering off;
   proxy_read_timeout 300s;
   proxy_send_timeout 300s;
   ```

---

### Option C: Caddy
Falls du Caddy nutzt, trage einfach folgendes in dein `Caddyfile` ein:
```caddy
paperless.dominikw.de {
    reverse_proxy 127.0.0.1:8088 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```
Caddy bezieht das SSL-Zertifikat vollautomatisch.

---

### Option D: Traefik
Falls Traefik als zentraler Reverse Proxy läuft:
Du kannst in `compose.yaml` den Dienst `web` einfach mit den Traefik-Labels versehen und in dein bestehendes Traefik-Netzwerk einbinden:
```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.paperless.rule=Host(`paperless.dominikw.de`)"
      - "traefik.http.routers.paperless.entrypoints=websecure"
      - "traefik.http.routers.paperless.tls.certresolver=letsencrypt"
      - "traefik.http.services.paperless.loadbalancer.server.port=80"
```

---

## 4. GitHub Repository konfigurieren

### Schritt 4.1: GitHub Packages Berechtigungen
Damit GitHub Actions die gebauten Docker-Container in das GitHub Container Registry (`ghcr.io`) pushen darf:
1. Gehe in deinem GitHub-Repository auf **Settings** -> **Actions** -> **General**.
2. Scrolle zu **Workflow permissions**.
3. Wähle **Read and write permissions** aus.
4. Klicke auf **Save**.

### Schritt 4.2: GitHub Secrets anlegen
Gehe in deinem GitHub-Repository auf **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret** und lege folgende Secrets an:

| Secret Name | Beschreibung | Beispiel / Wert |
|---|---|---|
| `SERVER_HOST` | Öffentliche IP oder Hostname deines Servers | `123.45.67.89` oder `dominikw.de` |
| `SERVER_USER` | SSH-Benutzername auf dem Server | `root` oder `deploy` |
| `SERVER_SSH_KEY` | Privater SSH-Schlüssel für den Server (OpenSSH Format) | `-----BEGIN OPENSSH PRIVATE KEY----- ...` |
| `SERVER_PORT` | SSH-Port (optional, falls abweichend) | `22` |
| `SERVER_DEPLOY_PATH` | Pfad zu Paperless auf dem Server | `/opt/paperless` |

> **Tipp für den SSH-Key:** Falls du noch keinen separaten Deployment-Key hast, erstelle einen auf deinem lokalen Rechner mit `ssh-keygen -t ed25519 -C "github-actions-deploy" -f deploy_key -N ""` und trage den Inhalt von `deploy_key.pub` auf deinem Server in `~/.ssh/authorized_keys` ein. Den privaten Schlüssel (`deploy_key`) trägst du als `SERVER_SSH_KEY` in GitHub ein.

### Schritt 4.3: Package Visibility auf GitHub (GHCR)
Nach dem ersten erfolgreichen Pipeline-Durchlauf erstellt GitHub die Container-Packages:
- `ghcr.io/<dein-user>/paperless-backend`
- `ghcr.io/<dein-user>/paperless-frontend`

1. Gehe auf GitHub auf dein Profil -> **Packages**.
2. Klicke auf das jeweilige Package -> **Package settings**.
3. **Empfohlen (Einfachste Option):** Scrolle ganz nach unten und ändere die Sichtbarkeit auf **Public**. Dann kann dein Server die Images ohne komplexe Authentifizierungstoken jederzeit aktualisieren.
4. *(Alternativ bei Private Package):* Falls die Packages privat bleiben sollen, erstelle unter *GitHub -> Settings -> Developer settings -> Personal access tokens (Classic)* ein Token mit dem Scope `read:packages` und logge dich einmalig auf dem Server ein:
   ```bash
   echo "DEIN_GITHUB_PAT" | docker login ghcr.io -u "DEIN_GITHUB_USER" --password-stdin
   ```

---

## 5. Deployment testen & ausführen

### Automatisch per Git Push:
Sobald du einen Commit auf den `main`-Branch pushst:
1. **GitHub Actions** führt automatisch die Backend-Tests (`pytest`) und den Frontend-Produktionsbuild aus.
2. Bei Erfolg werden die optimierten Multi-Stage Docker-Images für Backend und Frontend gebaut und zu `ghcr.io` gepusht.
3. Die Pipeline verbindet sich per SSH auf deinen Server in `/opt/paperless`.
4. Die `compose.yaml` wird aktualisiert, die neuen Images werden mit `docker compose pull` heruntergeladen und die Container mit `docker compose up -d` unterbrechungsfrei neu gestartet.

### Manuell über GitHub Actions:
Du kannst die Pipeline jederzeit manuell starten:
- Gehe im GitHub-Repository auf den Tab **Actions**.
- Wähle **CI / CD Pipeline** in der linken Seitenleiste.
- Klicke auf **Run workflow** -> Branch `main` auswählen -> **Run workflow**.

---

## 6. Nützliche Befehle auf dem Server

Im Verzeichnis `/opt/paperless`:

```bash
# Status aller Container ansehen
docker compose ps

# Live-Logs ansehen
docker compose logs -f

# Logs nur vom Worker (OCR-Verarbeitung) ansehen
docker compose logs -f worker

# Container manuell aktualisieren und neu starten
docker compose pull && docker compose up -d

# Manueller Health-Check
curl -i http://127.0.0.1:8088/health
```

---

## 7. Erstes Anmelden

Sobald der Proxy steht und die Container laufen:
1. Öffne im Browser **`https://paperless.dominikw.de`**.
2. Melde dich an mit:
   - **Benutzername:** `admin`
   - **Passwort:** dein gewähltes Passwort (bzw. das initiale Standard-Passwort `password123`, falls du den Beispiel-Hash aus `.env.example` übernommen hast).
3. Du kannst sofort Dokumente hochladen, durchsuchen und die Kamera-Scan PWA auf deinem Smartphone nutzen!
