from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("ai_classifier")

DEFAULT_CATEGORIES = [
    "Rechnungen",
    "Verträge",
    "Belege",
    "Versicherungen",
    "Steuer",
    "Bank",
    "Behörden",
    "Gesundheit",
    "Korrespondenz",
    "Anleitungen",
    "Garantien",
]

CLASSIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "description": "Die Hauptkategorie des Dokuments auf Deutsch.",
        },
        "confidence": {
            "type": "number",
            "description": "Konfidenzwert zwischen 0.0 und 1.0.",
        },
        "title": {
            "type": "string",
            "description": "Aussagekräftiger Titel für das Gesamtdokument.",
        },
        "sender": {
            "type": "string",
            "description": "Absender, Hochschule, Aussteller, Unternehmen oder Institution.",
        },
        "document_date": {
            "type": ["string", "null"],
            "description": "Dokumentendatum als String (YYYY-MM-DD oder DD.MM.YYYY) oder null.",
        },
        "due_date": {
            "type": ["string", "null"],
            "description": "Fälligkeitsdatum oder null.",
        },
        "amount": {
            "type": ["number", "null"],
            "description": "Rechnungsbetrag als Zahl (z.B. 49.99) oder null.",
        },
        "currency": {
            "type": ["string", "null"],
            "description": "Währung ('EUR', 'USD', 'CHF') oder null.",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Maximal 3 sichtbare Haupt-Tags auf Deutsch.",
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Bis zu 50 semantische Suchbegriffe für die Hintergrundsuche.",
        },
        "reasoning": {
            "type": "string",
            "description": "Kurze Begründung (1-2 Sätze) für die Klassifizierung.",
        },
    },
    "required": [
        "document_type",
        "confidence",
        "title",
        "sender",
        "tags",
        "keywords",
        "reasoning",
    ],
}


class AIClassifier:
    """Classifies documents using a local Ollama LLM (e.g. qwen3.5:2b-q4_K_M)."""

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=settings.OLLAMA_TIMEOUT_SECONDS)
        return self._client

    def is_available(self) -> bool:
        """Check if the configured Ollama instance is reachable."""
        if not settings.OLLAMA_ENABLED:
            return False
        try:
            client = self._get_client()
            url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
            resp = client.get(url, timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def classify_document(
        self,
        full_text: str,
        filename: str,
        available_categories: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Classify document text using Ollama.
        Returns parsed dictionary on success, or None if Ollama is unavailable or fails.
        """
        if not settings.OLLAMA_ENABLED:
            return None

        if not full_text or len(full_text.strip()) < 10:
            logger.info("Text too short for AI classification (%d chars)", len(full_text or ""))
            return None

        categories = available_categories or DEFAULT_CATEGORIES
        categories_str = ", ".join(categories)

        # 8k context window: truncate text safely (~20k characters leaves ~2.5k tokens headroom)
        truncated_text = self._truncate_text_for_context(full_text, max_chars=20_000)

        system_prompt = (
            "Du bist ein generischer Dokumenten-Klassifikator für ein Dokumenten-Management-System (Paperless).\n"
            "Deine AUSSCHLIESSLICHE Aufgabe ist die allgemeine Klassifizierung und Metadaten-Extraktion des Gesamtdokuments.\n\n"
            f"Verfügbare Standard-Dokumentenkategorien:\n[{categories_str}]\n\n"
            "STRIKTE VERBOTE & FORMAT-VORGABEN:\n"
            "- Erstelle NIEMALS dokumentspezifische Tabellen, Modullisten, Prüfungsergebnisse, Notenspiegel, Zeilenauflistungen oder Detailanalysen!\n"
            "- Erfinde NIEMALS eigene JSON-Schlüssel (wie 'summary', 'detailed_results', 'grades', 'modules', 'assessment' etc.)!\n"
            "- Deine Antwort MUSS GENAU und AUSSCHLIESSLICH den generischen Feldern des vorgegebenen JSON-Schemas entsprechen.\n\n"
            "Feld-Definitionen:\n"
            "1. 'document_type': Wähle eine der vorgegebenen Standardkategorien, wenn sie passt. "
            "Falls KEINE passt (z.B. bei Prüfungen, Zeugnissen, Studienunterlagen, Verträgen etc.), vergebe ein treffendes deutsches Substantiv (z.B. 'Studium', 'Prüfungsergebnisse', 'Notenübersicht', 'Forschung', 'Bewerbung'). Keine englischen Begriffe mit Unterstrichen.\n"
            "2. 'confidence': Konfidenzwert zwischen 0.0 (unsicher) und 1.0 (sicher).\n"
            "3. 'title': Prägnanter, aussagekräftiger Titel für das Gesamtdokument (z.B. 'Prüfungsergebnisse Fakultät Wirtschaft 2025' oder 'Telekom Rechnung September 2026').\n"
            "4. 'sender': Die im Dokument genannte Institution, Hochschule, Universität, Fakultät, Unternehmen oder Person (z.B. 'Fakultät Wirtschaft & Management' oder 'Telekom Deutschland GmbH'). NIEMALS 'AI Assistant' oder 'Ollama'!\n"
            "5. 'document_date': Datum des Dokuments als String (z.B. 'YYYY-MM-DD' oder 'DD.MM.YYYY') oder null.\n"
            "6. 'due_date': Zahlungsziel / Fälligkeitsdatum ('YYYY-MM-DD') oder null.\n"
            "7. 'amount': Rechnungs- oder Zahlungsbetrag als reine Dezimalzahl (z.B. 49.99) oder null.\n"
            "8. 'currency': Währungscode ('EUR', 'USD', 'CHF') oder null.\n"
            "9. 'tags': Liste von MAXIMAL 3 sichtbaren Tags auf Deutsch (z.B. ['Studium', 'Prüfungsergebnisse']). Keinesfalls mehr als 3 Tags!\n"
            "10. 'keywords': Liste von bis zu 50 semantischen Stichwörtern, Fachbegriffen und Themen für die Volltextsuche im Hintergrund. "
            "Hier dürfen auch relevante Begriffe stehen, die nicht wörtlich im Text vorkommen. Diese Stichwörter sind im Frontend unsichtbar und dienen rein der Suche.\n"
            "11. 'reasoning': Maximal 1-2 kurze Sätze Begründung zur Einordnung des Dokuments.\n"
        )

        user_content = (
            f"Dateiname: {filename}\n\n"
            f"Dokumententext (OCR):\n"
            f"```\n{truncated_text}\n```"
        )

        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "format": CLASSIFICATION_JSON_SCHEMA,
            "think": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "num_ctx": settings.OLLAMA_CONTEXT_WINDOW,
                "temperature": 0.1,
            },
        }

        # Prepare preview for logging
        preview_text = truncated_text[:350].strip().replace("\n", " ")
        if len(truncated_text) > 350:
            preview_text += "..."

        logger.info("============================================================")
        logger.info("[AIClassifier] Sende Klassifizierungsaufruf an Ollama:")
        logger.info("  -> Modell:            %s", settings.OLLAMA_MODEL)
        logger.info("  -> Kontextfenster:    %d Tokens", settings.OLLAMA_CONTEXT_WINDOW)
        logger.info("  -> Keep-Alive:        %s", settings.OLLAMA_KEEP_ALIVE)
        logger.info("  -> Dateiname:         '%s'", filename)
        logger.info("  -> Kategorien:        %s", categories_str)
        logger.info("  -> Text-Umfang:       %d Zeichen (OCR-Gesamtlänge: %d Zeichen)", len(truncated_text), len(full_text))
        logger.info("  -> OCR-Textauszug:    \"%s\"", preview_text)
        logger.info("============================================================")

        try:
            client = self._get_client()
            url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
            response = client.post(url, json=payload)
            # Graceful fallback if an older Ollama doesn't support schema objects in 'format'
            if response.status_code == 400 and isinstance(payload.get("format"), dict):
                logger.warning("Ollama rejected JSON schema format. Falling back to format='json'.")
                fallback_payload = dict(payload)
                fallback_payload["format"] = "json"
                response = client.post(url, json=fallback_payload)

            response.raise_for_status()

            raw_json = response.json()
            content = raw_json.get("message", {}).get("content", "")
            logger.info("[AIClassifier] Erhaltene Ollama-Antwort (JSON):\n%s", content.strip())

            parsed = self._parse_and_validate_response(content)
            if parsed:
                amt_str = (
                    f"{parsed['amount'] / 100:.2f} {parsed.get('currency', 'EUR')}"
                    if parsed.get("amount") is not None
                    else "Keiner"
                )
                tags_str = ", ".join(parsed.get("tags") or []) or "Keine"
                kw_list = parsed.get("keywords") or []
                kw_preview = ", ".join(kw_list[:6]) + (f" (+{len(kw_list)-6} weitere)" if len(kw_list) > 6 else "")
                logger.info("============================================================")
                logger.info("[AIClassifier] Extrahierte Klassifizierung & Metadaten:")
                logger.info("  -> Dokumententyp:          '%s' (Konfidenz: %.2f)", parsed.get("document_type"), parsed.get("confidence", 0.0))
                logger.info("  -> Titel:                  '%s'", parsed.get("title"))
                logger.info("  -> Absender:               '%s'", parsed.get("sender"))
                logger.info("  -> Belegdatum:             %s | Fällig: %s", parsed.get("document_date"), parsed.get("due_date"))
                logger.info("  -> Gesamtbetrag:           %s", amt_str)
                logger.info("  -> Sichtbare Tags (max 3):  %s", tags_str)
                logger.info("  -> Such-Stichwörter (≤50):  %d Begriffe (%s)", len(kw_list), kw_preview or "Keine")
                logger.info("  -> Begründung:             %s", parsed.get("reasoning"))
                logger.info("============================================================")
            return parsed

        except httpx.ConnectError:
            logger.warning(
                "Could not connect to Ollama at %s. Falling back to rule-based classifier.",
                settings.OLLAMA_BASE_URL,
            )
            return None
        except httpx.TimeoutException:
            logger.warning(
                "Timeout (%ds) waiting for Ollama response (%s). Falling back to rule-based classifier.",
                settings.OLLAMA_TIMEOUT_SECONDS,
                settings.OLLAMA_MODEL,
            )
            return None
        except Exception as e:
            logger.warning("Ollama classification failed: %s. Falling back to rule-based classifier.", e)
            return None

    def _truncate_text_for_context(self, text: str, max_chars: int = 20_000) -> str:
        """Truncate long OCR text, preserving head and tail where dates/totals reside."""
        if len(text) <= max_chars:
            return text
        head_len = int(max_chars * 0.7)
        tail_len = max_chars - head_len
        return (
            text[:head_len]
            + "\n\n... [Text gekürzt für 8k Kontextfenster] ...\n\n"
            + text[-tail_len:]
        )

    def _parse_and_validate_response(self, content: str) -> dict[str, Any] | None:
        """Parse, validate, and normalize JSON response from Ollama."""
        if not content:
            return None

        # Clean markdown wrappers if present
        clean_content = content.strip()
        if clean_content.startswith("```"):
            clean_content = re.sub(r"^```(?:json)?\s*", "", clean_content)
            clean_content = re.sub(r"\s*```$", "", clean_content)

        try:
            data = json.loads(clean_content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to decode Ollama JSON response: %s (Raw: %s)", e, content[:200])
            return None

        if not isinstance(data, dict):
            return None

        # Normalize document_type (support alternative keys from LLM)
        doc_type = (
            data.get("document_type")
            or data.get("category")
            or data.get("classification")
            or data.get("doc_type")
            or data.get("type")
            or ""
        )
        doc_type = str(doc_type).strip()
        doc_type_clean = doc_type.lower().replace("_", " ").strip()
        type_mapping = {
            "academic exam results": "Prüfungsergebnisse",
            "exam results": "Prüfungsergebnisse",
            "academic report": "Prüfungsergebnisse",
            "academic paper": "Forschung",
            "research paper": "Forschung",
            "invoice": "Rechnungen",
            "contract": "Verträge",
            "receipt": "Belege",
            "insurance": "Versicherungen",
            "tax": "Steuer",
            "bank statement": "Bank",
            "official document": "Behörden",
            "health": "Gesundheit",
        }
        if doc_type_clean in type_mapping:
            doc_type = type_mapping[doc_type_clean]
        elif "_" in doc_type:
            doc_type = doc_type.replace("_", " ").title()

        if not doc_type:
            return None

        # Normalize confidence
        try:
            confidence = float(data.get("confidence", 0.85))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.85

        # Normalize title and sender
        title = data.get("title")
        if title:
            title = str(title).strip() or None

        raw_sender = (
            data.get("sender")
            or data.get("authors")
            or data.get("author")
            or data.get("journal")
            or data.get("publisher")
            or data.get("institution")
        )
        sender: str | None = None
        if isinstance(raw_sender, list):
            sender = ", ".join(str(s).strip() for s in raw_sender if str(s).strip()) or None
        elif raw_sender:
            sender = str(raw_sender).strip() or None

        # Disallow hallucinated AI self-references as sender
        if sender and sender.lower() in ("ai assistant", "ollama", "ki-assistent", "assistant", "ki assistent", "ai"):
            sender = None

        # Normalize dates (YYYY-MM-DD)
        doc_date = self._parse_iso_date(data.get("document_date"))
        due_date = self._parse_iso_date(data.get("due_date"))

        # Normalize amount to cents
        cents = self._normalize_amount_to_cents(data.get("amount"))

        # Currency
        currency = str(data.get("currency") or "EUR").strip().upper()
        if currency not in ("EUR", "USD", "CHF", "GBP"):
            currency = "EUR"

        # Tags (strictly capped to max 3 visible tags)
        raw_tags = (
            data.get("tags")
            or data.get("categories")
            or []
        )
        tags: list[str] = []
        if isinstance(raw_tags, list):
            for t in raw_tags:
                t_str = str(t).strip()
                if "_" in t_str:
                    t_str = t_str.replace("_", " ").title()
                if t_str and t_str not in tags:
                    tags.append(t_str)
        elif isinstance(raw_tags, str):
            for t in raw_tags.split(","):
                t_str = t.strip()
                if "_" in t_str:
                    t_str = t_str.replace("_", " ").title()
                if t_str and t_str not in tags:
                    tags.append(t_str)
        tags = tags[:3]

        # Background search keywords (up to 50 terms for FTS5 search, invisible in UI)
        raw_keywords = (
            data.get("keywords")
            or data.get("search_keywords")
            or data.get("stichwoerter")
            or []
        )
        keywords: list[str] = []
        if isinstance(raw_keywords, list):
            for kw in raw_keywords:
                kw_str = str(kw).strip()
                if kw_str and len(kw_str) >= 2 and kw_str not in keywords:
                    keywords.append(kw_str)
        elif isinstance(raw_keywords, str):
            for kw in raw_keywords.split(","):
                kw_str = kw.strip()
                if kw_str and len(kw_str) >= 2 and kw_str not in keywords:
                    keywords.append(kw_str)
        keywords = keywords[:50]

        # Reasoning
        reasoning = str(data.get("reasoning") or "").strip()

        return {
            "document_type": doc_type,
            "confidence": confidence,
            "title": title,
            "sender": sender,
            "document_date": doc_date,
            "due_date": due_date,
            "amount": cents,
            "currency": currency,
            "tags": tags,
            "keywords": keywords,
            "reasoning": reasoning,
        }

    def _parse_iso_date(self, val: Any) -> date | None:
        if not val or not isinstance(val, str):
            return None
        val_clean = val.strip()

        # 1. Match YYYY-MM-DD
        m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", val_clean)
        if m_iso:
            try:
                y, mth, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
                if 1970 <= y <= 2100 and 1 <= mth <= 12 and 1 <= d <= 31:
                    return date(y, mth, d)
            except Exception:
                pass

        # 2. Match DD.MM.YYYY
        m_de = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", val_clean)
        if m_de:
            try:
                d, mth, y = int(m_de.group(1)), int(m_de.group(2)), int(m_de.group(3))
                if 1970 <= y <= 2100 and 1 <= mth <= 12 and 1 <= d <= 31:
                    return date(y, mth, d)
            except Exception:
                pass

        # 3. Match DD/MM/YYYY
        m_slash = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", val_clean)
        if m_slash:
            try:
                d, mth, y = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
                if 1970 <= y <= 2100 and 1 <= mth <= 12 and 1 <= d <= 31:
                    return date(y, mth, d)
            except Exception:
                pass

        return None

    def _normalize_amount_to_cents(self, val: Any) -> int | None:
        if val is None:
            return None
        try:
            if isinstance(val, (int, float)):
                fval = float(val)
            elif isinstance(val, str):
                cleaned = val.replace("€", "").replace("EUR", "").replace("CHF", "").replace("$", "").strip()
                cleaned = cleaned.replace(" ", "")
                if "," in cleaned and "." in cleaned:
                    if cleaned.rfind(",") > cleaned.rfind("."):
                        cleaned = cleaned.replace(".", "").replace(",", ".")
                    else:
                        cleaned = cleaned.replace(",", "")
                elif "," in cleaned:
                    cleaned = cleaned.replace(",", ".")
                fval = float(cleaned)
            else:
                return None

            cents = int(round(fval * 100))
            if 0 < cents < 100_000_000:
                return cents
        except Exception:
            pass
        return None


ai_classifier = AIClassifier()
