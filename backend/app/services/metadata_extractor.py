from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple


DATE_PATTERNS = [
    # 24.12.2025 or 24/12/2025
    r"\b([0-3]?[0-9])[\./\-]([0-1]?[0-9])[\./\-](20\d{2}|19\d{2})\b",
    # 2025-12-24
    r"\b(20\d{2}|19\d{2})[\./\-]([0-1]?[0-9])[\./\-]([0-3]?[0-9])\b",
]

# Patterns for amount: 1.234,56 € or 1234.56 EUR or € 49,99
AMOUNT_PATTERNS = [
    r"(?:gesamtbetrag|endbetrag|rechnungsbetrag|total|summe|betrag|zahlbetrag)[\s\:\=]*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))\s*(€|eur|chf|\$|usd)?",
    r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))\s*(€|eur|chf|\$|usd)",
]


def parse_date_str(day_or_year: str, month: str, year_or_day: str, is_iso: bool = False) -> Optional[date]:
    try:
        if is_iso:
            y, m, d = int(day_or_year), int(month), int(year_or_day)
        else:
            d, m, y = int(day_or_year), int(month), int(year_or_day)
        if 1 <= m <= 12 and 1 <= d <= 31 and 1970 <= y <= 2100:
            return date(y, m, d)
    except Exception:
        pass
    return None


class MetadataExtractor:
    def extract_metadata(self, full_text: str, filename: str) -> Dict[str, Any]:
        """Extract title, sender, document_date, due_date, amount, and currency."""
        result: Dict[str, Any] = {
            "title": None,
            "sender": None,
            "document_date": None,
            "due_date": None,
            "amount": None,
            "currency": "EUR",
            "evidence": {},
        }

        if not full_text:
            result["title"] = filename
            return result

        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        # 1. Document Date
        doc_date, date_ev = self._find_date(full_text, keywords=["rechnungsdatum", "datum", "date", "ausstellungsdatum"])
        if doc_date:
            result["document_date"] = doc_date
            result["evidence"]["document_date"] = date_ev

        # 2. Due Date
        due_date, due_ev = self._find_date(full_text, keywords=["fällig am", "zahlbar bis", "fälligkeit", "due date", "leistungsdatum"])
        if due_date and due_date != doc_date:
            result["due_date"] = due_date
            result["evidence"]["due_date"] = due_ev

        # 3. Amount & Currency
        amt, curr, amt_ev = self._find_amount(full_text)
        if amt is not None:
            result["amount"] = amt
            result["currency"] = curr
            result["evidence"]["amount"] = amt_ev

        # 4. Sender (heuristic: top non-empty lines)
        sender = self._find_sender(lines)
        if sender:
            result["sender"] = sender
            result["evidence"]["sender"] = f"Top text line: {sender}"

        # 5. Suggested Title
        title = self._suggest_title(filename, result.get("sender"), result.get("document_date"))
        result["title"] = title

        return result

    def _find_date(self, text: str, keywords: list[str]) -> Tuple[Optional[date], Optional[str]]:
        # Check near keywords first
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw)
            if idx != -1:
                snippet = text[idx : idx + 100]
                m = re.search(r"(\d{1,2})[\./\-](\d{1,2})[\./\-](\d{4})", snippet)
                if m:
                    d = parse_date_str(m.group(1), m.group(2), m.group(3))
                    if d:
                        return d, f"Found near '{kw}': {m.group(0)}"

        # General date search
        m = re.search(r"\b(\d{1,2})[\./\-](\d{1,2})[\./\-](\d{4})\b", text)
        if m:
            d = parse_date_str(m.group(1), m.group(2), m.group(3))
            if d:
                return d, f"General date match: {m.group(0)}"

        # ISO format YYYY-MM-DD
        m_iso = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", text)
        if m_iso:
            d = parse_date_str(m_iso.group(1), m_iso.group(2), m_iso.group(3), is_iso=True)
            if d:
                return d, f"ISO date match: {m_iso.group(0)}"

        return None, None

    def _find_amount(self, text: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        text_lower = text.lower()
        for pattern in AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text_lower):
                raw_amt = match.group(1)
                raw_curr = match.group(2) if len(match.groups()) > 1 else None

                # Normalize amount string
                # Remove thousands separators
                cleaned = raw_amt.replace(" ", "")
                if "," in cleaned and "." in cleaned:
                    if cleaned.rfind(",") > cleaned.rfind("."):
                        cleaned = cleaned.replace(".", "").replace(",", ".")
                    else:
                        cleaned = cleaned.replace(",", "")
                elif "," in cleaned:
                    cleaned = cleaned.replace(",", ".")

                try:
                    val = float(cleaned)
                    cents = int(round(val * 100))
                    if 0 < cents < 100_000_000:  # reasonable upper limit: 1 million EUR
                        curr = "EUR"
                        if raw_curr:
                            curr_str = raw_curr.strip().upper()
                            if curr_str in ("€", "EUR"):
                                curr = "EUR"
                            elif curr_str in ("$", "USD"):
                                curr = "USD"
                            elif curr_str == "CHF":
                                curr = "CHF"
                        return cents, curr, f"Matched '{match.group(0)}' -> {cents/100:.2f} {curr}"
                except ValueError:
                    continue

        return None, "EUR", None

    def _find_sender(self, lines: list[str]) -> Optional[str]:
        for line in lines[:8]:
            # Skip very short or generic lines
            if len(line) < 3 or len(line) > 80:
                continue
            if any(term in line.lower() for term in ["rechnung", "invoice", "seite", "page", "datum", "date"]):
                continue
            # Probable company / sender name
            return line
        return None

    def _suggest_title(self, filename: str, sender: Optional[str], doc_date: Optional[date]) -> str:
        parts = []
        if sender:
            parts.append(sender)
        if doc_date:
            parts.append(doc_date.isoformat())
        if parts:
            return " - ".join(parts)
        # Fallback to base filename without extension
        return re.sub(r"\.[^.]+$", "", filename)


metadata_extractor = MetadataExtractor()
