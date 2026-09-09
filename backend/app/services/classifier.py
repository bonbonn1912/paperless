from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.classification import ClassificationResult, ClassificationRule
from app.models.document import Document
from app.models.tag import DocumentTag, DocumentTagOverride, Tag
from app.services.ai_classifier import ai_classifier
from app.services.tags import tag_service

logger = logging.getLogger("classifier")

NEW_TAG_COLORS = [
    "#6366F1",  # Indigo
    "#8B5CF6",  # Violet
    "#EC4899",  # Pink
    "#14B8A6",  # Teal
    "#F97316",  # Orange
    "#06B6D4",  # Cyan
    "#10B981",  # Emerald
    "#3B82F6",  # Blue
    "#F59E0B",  # Amber
    "#84CC16",  # Lime
]


def _pick_tag_color(name: str) -> str:
    h = 0
    for char in name:
        h = (h * 31 + ord(char)) & 0xFFFFFFFF
    return NEW_TAG_COLORS[h % len(NEW_TAG_COLORS)]


def _clean_tag_name(raw: str) -> str | None:
    cleaned = re.sub(r"[^\w\s\-\.\/]", "", str(raw)).strip()
    cleaned = cleaned.strip("-._/")
    if len(cleaned) < 2 or len(cleaned) > 50:
        return None
    if cleaned.isdigit():
        return None
    return cleaned


class DocumentClassifier:
    def classify_document(
        self,
        db: Session,
        owner: str,
        document_id: str,
        full_text: str,
        metadata: Dict[str, Any],
        run_id: str,
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """
        Classify document using local AI (Ollama qwen3.5:2b-q4_K_M) with deterministic rule fallback.
        Returns: (classification_state, review_reasons, suggested_tags)
        """
        # 1. Check existing manual overrides
        overrides = (
            db.query(DocumentTagOverride)
            .filter(DocumentTagOverride.document_id == document_id, DocumentTagOverride.owner == owner)
            .all()
        )
        confirmed_tag_ids = {o.tag_id for o in overrides if o.state == "confirmed"}
        excluded_tag_ids = {o.tag_id for o in overrides if o.state == "excluded"}

        # If user previously confirmed tags manually, respect and keep them classified
        if confirmed_tag_ids:
            return "classified", [], [{"tag_id": tid, "source": "manual", "score": 1.0} for tid in confirmed_tag_ids]

        text_lower = (full_text or "").lower()
        text_length = len(text_lower.strip())

        # Check for empty / very low text quality
        if text_length < 15:
            review_reasons = ["no_text" if text_length == 0 else "low_text_quality"]
            self._save_result(db, document_id, run_id, [], metadata, review_reasons, rule_version=1)
            return "needs_review", review_reasons, []

        tag_scores: Dict[str, Dict[str, Any]] = {}
        ai_used = False
        is_new_doc_type = False
        has_new_tag = False
        matched_existing_tag = False
        newly_suggested_tags: List[str] = []

        # 2. Attempt AI Classification via Ollama (qwen3.5:2b-q4_K_M, 8k ctx, 3m keep_alive)
        if settings.OLLAMA_ENABLED:
            doc = db.query(Document).filter(Document.id == document_id).first()
            fname = doc.original_name if doc else metadata.get("title") or "Dokument"

            # Query existing canonical categories for this user
            existing_tags = [
                t.name
                for t in db.query(Tag).filter(Tag.owner == owner, Tag.kind == "document_type").all()
            ]

            ai_data = ai_classifier.classify_document(
                full_text=full_text,
                filename=fname,
                available_categories=existing_tags or None,
            )

            if ai_data:
                ai_used = True
                doc_type = ai_data.get("document_type")
                conf = ai_data.get("confidence", 0.90)
                reasoning = ai_data.get("reasoning", "")

                # 2.1 Resolve primary document type (or create new category if not existing)
                if doc_type:
                    clean_doc_type = _clean_tag_name(doc_type)
                    if clean_doc_type:
                        tag, was_existing, _ = tag_service.resolve_name(db, owner, clean_doc_type)
                        if tag:
                            matched_existing_tag = True
                            is_new = False
                        else:
                            # Dynamic category creation: create as document_type
                            tag = tag_service.create_tag(
                                db=db,
                                owner=owner,
                                name=clean_doc_type,
                                kind="document_type",
                                color=_pick_tag_color(clean_doc_type),
                            )
                            is_new_doc_type = True
                            has_new_tag = True
                            is_new = True
                            newly_suggested_tags.append(clean_doc_type)
                            logger.info(
                                "[Classifier] Neuer Tag '%s' (document_type) von KI vorgeschlagen & angelegt. Erfordert Freigabe im Frontend.",
                                clean_doc_type,
                            )

                        tag_scores[tag.id] = {
                            "tag_id": tag.id,
                            "tag_name": tag.name,
                            "score": conf,
                            "evidence": f"Ollama ({settings.OLLAMA_MODEL}): {reasoning}",
                            "source": "ai",
                            "is_new": is_new,
                        }

                # 2.2 Resolve secondary suggested tags (strictly capped to max 3 visible tags total)
                max_secondary = max(0, 3 - len(tag_scores))
                for st in (ai_data.get("tags", []) or [])[:max_secondary]:
                    clean_st = _clean_tag_name(st)
                    if not clean_st:
                        continue
                    st_tag, was_st_existing, _ = tag_service.resolve_name(db, owner, clean_st)
                    st_is_new = False
                    if st_tag:
                        matched_existing_tag = True
                    else:
                        st_tag = tag_service.create_tag(
                            db=db,
                            owner=owner,
                            name=clean_st,
                            kind="topic",
                            color=_pick_tag_color(clean_st),
                        )
                        has_new_tag = True
                        st_is_new = True
                        newly_suggested_tags.append(clean_st)
                        logger.info(
                            "[Classifier] Neues Schlagwort '%s' von KI vorgeschlagen & angelegt.",
                            clean_st,
                        )

                    if st_tag and st_tag.id not in tag_scores:
                        tag_scores[st_tag.id] = {
                            "tag_id": st_tag.id,
                            "tag_name": st_tag.name,
                            "score": round(max(0.65, conf * 0.9), 2),
                            "evidence": f"Ollama suggested tag '{clean_st}'",
                            "source": "ai",
                            "is_new": st_is_new,
                        }
                    if len(tag_scores) >= 3:
                        break

                # 2.3 Enrich metadata dictionary for downstream pipeline use
                if ai_data.get("keywords"):
                    metadata["keywords"] = ai_data["keywords"]
                    metadata["keywords_from_ai"] = True

                if ai_data.get("title"):
                    metadata["title"] = ai_data["title"]
                    metadata["title_from_ai"] = True
                if ai_data.get("sender"):
                    metadata["sender"] = ai_data["sender"]
                    metadata["sender_from_ai"] = True
                if ai_data.get("document_date"):
                    metadata["document_date"] = ai_data["document_date"]
                    metadata["date_from_ai"] = True
                if ai_data.get("due_date"):
                    metadata["due_date"] = ai_data["due_date"]
                    metadata["due_date_from_ai"] = True
                if ai_data.get("amount") is not None:
                    metadata["amount"] = ai_data["amount"]
                    metadata["currency"] = ai_data.get("currency", "EUR")
                    metadata["amount_from_ai"] = True

                if "evidence" not in metadata or not isinstance(metadata["evidence"], dict):
                    metadata["evidence"] = {}
                if reasoning:
                    metadata["evidence"]["ai_classification"] = f"AI ({settings.OLLAMA_MODEL}): {reasoning}"

        # 3. Deterministic Rule Evaluation Fallback (if AI disabled, failed, or produced no tags)
        if not tag_scores:
            logger.info("Using deterministic rule classifier (fallback or AI disabled)")
            # Rechnungen
            inv_matches = re.findall(
                r"\b(rechnungsnummer|rechnungs-nr|rechnung\s+nr|invoice\s+(?:number|no|#)|gesamtbetrag|zahlbetrag|fälligkeit)\b",
                text_lower,
            )
            has_amount = metadata.get("amount") is not None
            if (len(inv_matches) >= 2 or ("rechnungsnummer" in text_lower or "invoice" in text_lower)) and has_amount:
                self._add_tag_candidate(db, owner, tag_scores, "Rechnungen", 0.95, f"Invoice keywords: {inv_matches[:3]}, amount detected")
            elif len(inv_matches) >= 1:
                self._add_tag_candidate(db, owner, tag_scores, "Rechnungen", 0.60, f"Partial invoice matches: {inv_matches[:2]}")

            # Belege / Quittungen
            receipt_matches = re.findall(r"\b(kassenbeleg|kassenbon|quittung|beleg\s+nr|barzahlung|kartenzahlung|mwst-satz)\b", text_lower)
            if receipt_matches and has_amount:
                self._add_tag_candidate(db, owner, tag_scores, "Belege", 0.90, f"Receipt keywords: {receipt_matches}")

            # Verträge
            contract_matches = re.findall(r"\b(vertrag|vereinbarung|contract|agreement|vertragsparteien|vertragsdauer|kündigungsfrist)\b", text_lower)
            if len(contract_matches) >= 2:
                self._add_tag_candidate(db, owner, tag_scores, "Verträge", 0.92, f"Contract keywords: {contract_matches}")

            # Versicherungen
            ins_matches = re.findall(r"\b(versicherung|versicherungsschein|policen-nr|versicherungsnehmer|schadensfall)\b", text_lower)
            if ins_matches:
                self._add_tag_candidate(db, owner, tag_scores, "Versicherungen", 0.88, f"Insurance keywords: {ins_matches}")

            # Bank
            bank_matches = re.findall(r"\b(kontoauszug|iban|bic|kontonummer|buchungstag|valuta|alter kontostand|neuer kontostand)\b", text_lower)
            if len(bank_matches) >= 2:
                self._add_tag_candidate(db, owner, tag_scores, "Bank", 0.90, f"Bank statement keywords: {bank_matches}")

            # Steuer
            tax_matches = re.findall(r"\b(finanzamt|steuerbescheid|steuernummer|einkommensteuer|umsatzsteuer-voranmeldung)\b", text_lower)
            if tax_matches:
                self._add_tag_candidate(db, owner, tag_scores, "Steuer", 0.90, f"Tax keywords: {tax_matches}")

            # Gesundheit
            health_matches = re.findall(r"\b(rezept|befund|diagnose|patient|arztrechnung|arztpraxis|krankenkasse)\b", text_lower)
            if health_matches:
                self._add_tag_candidate(db, owner, tag_scores, "Gesundheit", 0.85, f"Health keywords: {health_matches}")

            # Behörden
            gov_matches = re.findall(r"\b(stadtverwaltung|landratsamt|bundesagentur|aktenzeichen|bescheid|bussgeldbescheid)\b", text_lower)
            if gov_matches:
                self._add_tag_candidate(db, owner, tag_scores, "Behörden", 0.85, f"Government authority keywords: {gov_matches}")

            # Custom rules from ClassificationRule table
            custom_rules = (
                db.query(ClassificationRule)
                .filter(ClassificationRule.owner == owner, ClassificationRule.is_active == True)
                .order_by(ClassificationRule.priority.desc())
                .all()
            )
            for rule in custom_rules:
                if self._matches_custom_rule(text_lower, metadata, rule.conditions):
                    for tid in rule.target_tag_ids:
                        tag = db.query(Tag).filter(Tag.id == tid).first()
                        if tag:
                            tag_scores[tid] = {
                                "tag_id": tag.id,
                                "tag_name": tag.name,
                                "score": 0.99,
                                "evidence": f"Custom rule '{rule.name}' matched",
                                "source": "rule",
                            }

        # Filter out user-excluded tags
        valid_candidates = [
            cand for tid, cand in tag_scores.items() if tid not in excluded_tag_ids
        ]

        # 4. Determine final classification state
        review_reasons = []
        requires_approval_for_new_tag = is_new_doc_type or (has_new_tag and not matched_existing_tag)

        if not valid_candidates:
            review_reasons.append("no_matching_rule")
            final_state = "needs_review"
            accepted_tags = []
        elif requires_approval_for_new_tag:
            # User requirement: If no matching existing tag was found and AI suggested a new one,
            # it MUST be approved in the frontend before being finalized!
            review_reasons.append("new_tag_suggested")
            final_state = "needs_review"
            valid_candidates.sort(key=lambda x: x["score"], reverse=True)
            accepted_tags = valid_candidates
            logger.info(
                "[Classifier] Dokument '%s' erhält Status 'needs_review' wegen neu vorgeschlagenem Tag [%s] zur Benutzer-Freigabe im Frontend.",
                fname,
                ", ".join(newly_suggested_tags),
            )
        else:
            # Sort by score descending
            valid_candidates.sort(key=lambda x: x["score"], reverse=True)
            top_candidate = valid_candidates[0]

            high_candidates = [c for c in valid_candidates if c["score"] >= 0.80]
            if len(high_candidates) > 1 and abs(high_candidates[0]["score"] - high_candidates[1]["score"]) < 0.05:
                review_reasons.append("ambiguous_type")
                final_state = "needs_review"
                accepted_tags = valid_candidates
            elif top_candidate["score"] >= 0.75:
                final_state = "classified"
                accepted_tags = [top_candidate]
            else:
                review_reasons.append("low_confidence")
                final_state = "needs_review"
                accepted_tags = valid_candidates

        # Strict limit: A document receives at most 3 visible tags per user requirement
        accepted_tags = accepted_tags[:3]

        # 5. Persist document_tags for accepted tags (cleaning previous auto-assigned tags)
        db.query(DocumentTag).filter(
            DocumentTag.document_id == document_id,
            DocumentTag.source.in_(["rule", "ai"]),
        ).delete(synchronize_session=False)

        source_label = "ai" if ai_used else "rule"
        for cand in accepted_tags:
            db.add(DocumentTag(
                document_id=document_id,
                tag_id=cand["tag_id"],
                source=cand.get("source", source_label),
                score=cand["score"],
            ))

        self._save_result(
            db=db,
            document_id=document_id,
            run_id=run_id,
            suggested_tags=valid_candidates,
            metadata=metadata,
            review_reasons=review_reasons,
            rule_version=2 if ai_used else 1,
        )
        db.commit()

        assigned_summary = [
            f"{c['tag_name']} ({c.get('source', source_label)}, Score: {c['score']:.2f})"
            for c in accepted_tags
        ]
        logger.info(
            "[Classifier] Dokument '%s' klassifiziert: Status=%s | Tags=[%s] | Gründe=%s",
            fname,
            final_state,
            ", ".join(assigned_summary) or "Keine",
            review_reasons or "Keine (erfolgreich)",
        )

        return final_state, review_reasons, accepted_tags

    def _add_tag_candidate(
        self,
        db: Session,
        owner: str,
        tag_scores: Dict[str, Dict[str, Any]],
        canonical_name: str,
        score: float,
        evidence: str,
    ) -> None:
        tag, _, _ = tag_service.resolve_name(db, owner, canonical_name)
        if tag:
            tag_scores[tag.id] = {
                "tag_id": tag.id,
                "tag_name": tag.name,
                "score": score,
                "evidence": evidence,
                "source": "rule",
            }

    def _matches_custom_rule(self, text_lower: str, metadata: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Evaluate JSON condition tree, e.g. {"all": [{"field": "text", "contains": "telekom"}]}."""
        if "all" in conditions:
            return all(self._eval_single_condition(text_lower, metadata, c) for c in conditions["all"])
        if "any" in conditions:
            return any(self._eval_single_condition(text_lower, metadata, c) for c in conditions["any"])
        return False

    def _eval_single_condition(self, text_lower: str, metadata: Dict[str, Any], cond: Dict[str, Any]) -> bool:
        field = cond.get("field", "text")
        op = cond.get("contains")
        if field == "text" and op:
            return op.lower() in text_lower
        if field == "sender" and op:
            sender = (metadata.get("sender") or "").lower()
            return op.lower() in sender
        return False

    def _save_result(
        self,
        db: Session,
        document_id: str,
        run_id: str,
        suggested_tags: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        review_reasons: List[str],
        rule_version: int = 1,
    ) -> None:
        doc_date = metadata.get("document_date")
        iso_doc_date = doc_date.isoformat() if hasattr(doc_date, "isoformat") else (str(doc_date) if doc_date else None)

        res = ClassificationResult(
            document_id=document_id,
            run_id=run_id,
            suggested_tags=suggested_tags,
            suggested_fields={
                "title": metadata.get("title"),
                "sender": metadata.get("sender"),
                "document_date": iso_doc_date,
                "amount": metadata.get("amount"),
                "currency": metadata.get("currency"),
                "keywords": metadata.get("keywords", []),
            },
            evidence=metadata.get("evidence", {}),
            rule_version=rule_version,
            review_reasons=review_reasons,
        )
        db.add(res)


# Alias classifier instance
classifier = DocumentClassifier()
RuleClassifier = DocumentClassifier
