from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.classification import ClassificationResult, ClassificationRule
from app.models.document import Document
from app.models.tag import DocumentTag, DocumentTagOverride, Tag
from app.services.tags import tag_service


class RuleClassifier:
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
        Classify document using local deterministic rules.
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
            self._save_result(db, document_id, run_id, [], metadata, review_reasons)
            return "needs_review", review_reasons, []

        tag_scores: Dict[str, Dict[str, Any]] = {}

        # 2. Rule evaluation for standard document types
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

        # 3. Custom rules from ClassificationRule table
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
                        }

        # Filter out user-excluded tags
        valid_candidates = [
            cand for tid, cand in tag_scores.items() if tid not in excluded_tag_ids
        ]

        # 4. Determine state
        review_reasons = []
        if not valid_candidates:
            review_reasons.append("no_matching_rule")
            final_state = "needs_review"
            accepted_tags = []
        else:
            # Sort by score descending
            valid_candidates.sort(key=lambda x: x["score"], reverse=True)
            top_candidate = valid_candidates[0]

            # Check if there is ambiguity (multiple high candidates with different types)
            high_candidates = [c for c in valid_candidates if c["score"] >= 0.80]
            if len(high_candidates) > 1 and abs(high_candidates[0]["score"] - high_candidates[1]["score"]) < 0.05:
                review_reasons.append("ambiguous_type")
                final_state = "needs_review"
                accepted_tags = valid_candidates
            elif top_candidate["score"] >= 0.80:
                final_state = "classified"
                accepted_tags = [top_candidate]
            else:
                review_reasons.append("low_confidence")
                final_state = "needs_review"
                accepted_tags = valid_candidates

        # 5. Persist document_tags for accepted tags
        # Remove old rule-assigned tags
        db.query(DocumentTag).filter(
            DocumentTag.document_id == document_id,
            DocumentTag.source == "rule",
        ).delete()

        for cand in accepted_tags:
            db.add(DocumentTag(
                document_id=document_id,
                tag_id=cand["tag_id"],
                source="rule",
                score=cand["score"],
            ))

        self._save_result(db, document_id, run_id, valid_candidates, metadata, review_reasons)
        db.commit()
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
    ) -> None:
        res = ClassificationResult(
            document_id=document_id,
            run_id=run_id,
            suggested_tags=suggested_tags,
            suggested_fields={
                "title": metadata.get("title"),
                "sender": metadata.get("sender"),
                "document_date": metadata.get("document_date").isoformat() if metadata.get("document_date") else None,
                "amount": metadata.get("amount"),
                "currency": metadata.get("currency"),
            },
            evidence=metadata.get("evidence", {}),
            rule_version=1,
            review_reasons=review_reasons,
        )
        db.add(res)


classifier = RuleClassifier()
