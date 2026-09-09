from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Document
from app.models.tag import DocumentTag, DocumentTagOverride
from app.services.ai_classifier import AIClassifier, ai_classifier
from app.services.classifier import classifier
from app.services.tags import tag_service


@pytest.fixture
def mock_ollama_response():
    return {
        "model": "qwen3.5:2b-q4_K_M",
        "created_at": "2026-09-09T18:00:00Z",
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "document_type": "Rechnungen",
                "confidence": 0.96,
                "title": "Telekom Mobilfunkrechnung September 2026",
                "sender": "Telekom Deutschland GmbH",
                "document_date": "2026-09-01",
                "due_date": "2026-09-15",
                "amount": 49.95,
                "currency": "EUR",
                "tags": ["Mobilfunk", "Rechnungen", "Telekommunikation", "ZusatzTag4", "ZusatzTag5"],
                "keywords": ["5G", "Handyvertrag", "Datenvolumen", "Roaming", "Tarif"],
                "reasoning": "Monatliche Mobilfunkrechnung mit Rechnungsbetrag und Zahlungsziel.",
            }),
        },
        "done": True,
    }


def test_ai_classifier_request_payload_and_parsing(mock_ollama_response):
    classifier_instance = AIClassifier()

    with patch.object(classifier_instance, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_ollama_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_get_client.return_value = mock_client

        res = classifier_instance.classify_document(
            full_text="Telekom Deutschland GmbH Rechnung Nr. 12345678 Betrag 49,95 EUR",
            filename="rechnung.pdf",
            available_categories=["Rechnungen", "Verträge", "Belege"],
        )

        assert res is not None
        assert res["document_type"] == "Rechnungen"
        assert res["confidence"] == 0.96
        assert res["title"] == "Telekom Mobilfunkrechnung September 2026"
        assert res["sender"] == "Telekom Deutschland GmbH"
        assert res["document_date"] == date(2026, 9, 1)
        assert res["due_date"] == date(2026, 9, 15)
        assert res["amount"] == 4995  # 49.95 EUR -> 4995 cents
        assert res["currency"] == "EUR"
        assert len(res["tags"]) <= 3  # Strictly capped at max 3 tags!
        assert len(res["keywords"]) == 5
        assert "5G" in res["keywords"]

        # Verify call parameters sent to Ollama
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]

        assert payload["model"] == settings.OLLAMA_MODEL
        assert payload["keep_alive"] == "3m"
        assert isinstance(payload["format"], dict)
        assert payload["format"]["type"] == "object"
        assert "document_type" in payload["format"]["properties"]
        assert "confidence" in payload["format"]["properties"]
        assert payload["think"] is False
        assert payload["options"]["num_ctx"] == 8192
        assert payload["options"]["temperature"] == 0.1


def test_ai_classifier_fallback_on_connection_error():
    classifier_instance = AIClassifier()

    with patch.object(classifier_instance, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_get_client.return_value = mock_client

        res = classifier_instance.classify_document(
            full_text="Beispieltext für ein Dokument",
            filename="doc.pdf",
        )

        assert res is None


def test_ai_classifier_fallback_on_invalid_json():
    classifier_instance = AIClassifier()

    with patch.object(classifier_instance, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Das ist kein JSON Antworttext"}
        }
        mock_client.post.return_value = mock_resp
        mock_get_client.return_value = mock_client

        res = classifier_instance.classify_document(
            full_text="Beispieltext für ein Dokument",
            filename="doc.pdf",
        )

        assert res is None


def test_classifier_end_to_end_with_ai(db_session: Session, mock_ollama_response):
    owner = "ai_test_user"
    tag_service.ensure_default_tags(db_session, owner)

    doc = Document(
        id="doc-ai-test-1",
        owner=owner,
        original_name="telekom_rechnung.pdf",
        storage_key="telekom_rechnung.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256="dummy-sha256",
        title="telekom_rechnung.pdf",
        classification_state="pending",
    )
    db_session.add(doc)
    db_session.commit()

    with patch.object(ai_classifier, "classify_document") as mock_ai_call:
        mock_ai_call.return_value = {
            "document_type": "Rechnungen",
            "confidence": 0.95,
            "title": "Telekom Rechnung September 2026",
            "sender": "Telekom Deutschland GmbH",
            "document_date": date(2026, 9, 1),
            "due_date": date(2026, 9, 15),
            "amount": 4995,
            "currency": "EUR",
            "tags": ["Rechnungen"],
            "reasoning": "Rechnung der Telekom Deutschland GmbH mit ausgewiesenem Betrag.",
        }

        metadata = {"title": "telekom_rechnung.pdf"}
        state, _reasons, tags = classifier.classify_document(
            db=db_session,
            owner=owner,
            document_id=doc.id,
            full_text="Telekom Rechnung 49,95 EUR",
            metadata=metadata,
            run_id="run-ai-1",
        )

        assert state == "classified"
        assert len(tags) > 0
        assert metadata["title"] == "Telekom Rechnung September 2026"
        assert metadata["sender"] == "Telekom Deutschland GmbH"
        assert metadata["amount"] == 4995

        # Check that tag Rechnungen was assigned with source="ai"
        assigned_tag = (
            db_session.query(DocumentTag)
            .filter(DocumentTag.document_id == doc.id)
            .first()
        )
        assert assigned_tag is not None
        assert assigned_tag.source == "ai"
        assert assigned_tag.score == 0.95


def test_classifier_new_tag_creation_requires_frontend_approval(db_session: Session):
    owner = "ai_new_tag_user"
    tag_service.ensure_default_tags(db_session, owner)

    # Verify "Wissenschaft" does not exist yet
    tag_wiss, exists, _ = tag_service.resolve_name(db_session, owner, "Wissenschaft")
    assert not exists
    assert tag_wiss is None

    doc = Document(
        id="doc-academic-paper-1",
        owner=owner,
        original_name="1-s2.0-S0306437924000826-main.pdf",
        storage_key="1-s2.0-S0306437924000826-main.pdf",
        mime_type="application/pdf",
        file_size=2048,
        sha256="dummy-paper-sha256",
        title="1-s2.0-S0306437924000826-main.pdf",
        classification_state="pending",
    )
    db_session.add(doc)
    db_session.commit()

    with patch.object(ai_classifier, "classify_document") as mock_ai_call:
        mock_ai_call.return_value = {
            "document_type": "Wissenschaft",
            "confidence": 0.98,
            "title": "Kognitive Effekte von Modularisierung",
            "sender": "Karlsruhe Institute of Technology",
            "document_date": date(2024, 7, 6),
            "due_date": None,
            "amount": None,
            "currency": "EUR",
            "tags": ["Prozessmodell", "Forschung"],
            "reasoning": "Wissenschaftlicher Fachartikel ohne Rechnungsdaten.",
        }

        metadata = {"title": "1-s2.0-S0306437924000826-main.pdf"}
        state, reasons, tags = classifier.classify_document(
            db=db_session,
            owner=owner,
            document_id=doc.id,
            full_text="Scientific paper about process models",
            metadata=metadata,
            run_id="run-academic-1",
        )

        # Must require review because a new tag was suggested!
        assert state == "needs_review"
        assert "new_tag_suggested" in reasons
        assert len(tags) >= 1

        # Check that the new tag "Wissenschaft" was created
        tag_wiss, exists, _ = tag_service.resolve_name(db_session, owner, "Wissenschaft")
        assert exists
        assert tag_wiss is not None
        assert tag_wiss.kind == "document_type"

        # Check that secondary tags were also created
        tag_pm, exists_pm, _ = tag_service.resolve_name(db_session, owner, "Prozessmodell")
        assert exists_pm
        assert tag_pm is not None
        assert tag_pm.kind == "topic"

        # Verify DocumentTags are attached to the document
        assigned = db_session.query(DocumentTag).filter(DocumentTag.document_id == doc.id).all()
        assigned_ids = {a.tag_id for a in assigned}
        assert tag_wiss.id in assigned_ids
        assert tag_pm.id in assigned_ids


def test_classifier_respects_manual_overrides_when_ai_runs(db_session: Session):
    owner = "ai_override_user"
    tag_service.ensure_default_tags(db_session, owner)
    tag_vertraege, _, _ = tag_service.resolve_name(db_session, owner, "Verträge")

    doc = Document(
        id="doc-ai-override-1",
        owner=owner,
        original_name="vertrag.pdf",
        storage_key="vertrag.pdf",
        mime_type="application/pdf",
        file_size=512,
        sha256="dummy-override-sha",
        title="Mein Manueller Vertrag",
        classification_state="classified",
    )
    db_session.add(doc)
    db_session.commit()

    # User manually confirmed Verträge
    db_session.add(DocumentTag(document_id=doc.id, tag_id=tag_vertraege.id, source="manual"))
    db_session.add(DocumentTagOverride(document_id=doc.id, tag_id=tag_vertraege.id, state="confirmed", owner=owner))
    db_session.commit()

    with patch.object(ai_classifier, "classify_document") as mock_ai_call:
        # AI would wrongly think this is an invoice
        mock_ai_call.return_value = {
            "document_type": "Rechnungen",
            "confidence": 0.99,
            "title": "Falsche Rechnung",
            "tags": ["Rechnungen"],
        }

        state, _reasons, _tags = classifier.classify_document(
            db=db_session,
            owner=owner,
            document_id=doc.id,
            full_text="Text mit vielen Rechnungsnummern",
            metadata={},
            run_id="run-override",
        )

        assert state == "classified"
        # The manual tag is preserved!
        assigned = db_session.query(DocumentTag).filter(DocumentTag.document_id == doc.id).all()
        assert len(assigned) == 1
        assert assigned[0].tag_id == tag_vertraege.id
        assert assigned[0].source == "manual"


def test_classifier_strictly_caps_at_3_tags_and_stores_keywords(db_session: Session):
    owner = "ai_cap_test_user"
    tag_service.ensure_default_tags(db_session, owner)

    doc = Document(
        id="doc-ai-cap-1",
        owner=owner,
        original_name="großer_bericht.pdf",
        storage_key="bericht.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256="dummy-cap-sha256",
        title="großer_bericht.pdf",
        classification_state="pending",
    )
    db_session.add(doc)
    db_session.commit()

    with patch.object(ai_classifier, "classify_document") as mock_ai_call:
        mock_ai_call.return_value = {
            "document_type": "Forschung",
            "confidence": 0.95,
            "title": "KI und Prozessmodellierung",
            "sender": "Institut für Informatik",
            # AI returns 6 tags - system must cap at MAX 3
            "tags": ["Forschung", "KI", "Prozessmodellierung", "Workflow", "BPMN", "Automatisierung"],
            # Up to 50 background search keywords
            "keywords": [
                "Machine Learning", "Neuronale Netze", "Prompt Engineering", "Sprachmodell",
                "Deep Learning", "Transformers", "LLM", "Embedding", "Retrieval", "RAG"
            ],
            "reasoning": "Akademischer Forschungsbericht über KI-Systeme.",
        }

        metadata = {"title": "großer_bericht.pdf"}
        state, reasons, tags = classifier.classify_document(
            db=db_session,
            owner=owner,
            document_id=doc.id,
            full_text="Forschungsbericht über KI",
            metadata=metadata,
            run_id="run-cap-1",
        )

        # 1. State must require review for newly created tags
        assert state == "needs_review"
        assert "new_tag_suggested" in reasons

        # 2. Maximum 3 visible tags returned and assigned in DB!
        assert len(tags) <= 3
        assigned_doc_tags = (
            db_session.query(DocumentTag)
            .filter(DocumentTag.document_id == doc.id)
            .all()
        )
        assert len(assigned_doc_tags) <= 3

        # 3. Keywords are stored in metadata for pipeline indexing
        assert metadata.get("keywords") is not None
        assert len(metadata["keywords"]) == 10
        assert "Machine Learning" in metadata["keywords"]
        assert "Transformers" in metadata["keywords"]


def test_parse_and_validate_response_normalizes_dates_and_snake_case():
    classifier_instance = AIClassifier()
    raw_response = json.dumps({
        "document_type": "academic_exam_results",
        "confidence": 0.99,
        "title": "Fakultät Wirtschaft & Management - Prüfungsergebnisse",
        "sender": "Fakultät Wirtschaft & Management",
        "document_date": "01.01.2025 - 31.12.2025",
        "due_date": None,
        "amount": None,
        "currency": "EUR",
        "tags": ["wirtschaftswissenschaften", "pruefungs_ergebnisse"],
        "keywords": ["Marketing", "Controlling", "Logistik"],
        "reasoning": "Notenübersicht der Hochschule.",
    })

    parsed = classifier_instance._parse_and_validate_response(raw_response)
    assert parsed is not None
    # Snake case mapped to German title
    assert parsed["document_type"] == "Prüfungsergebnisse"
    # German date parsed successfully
    assert parsed["document_date"] == date(2025, 1, 1)
    # Snake case in tags cleaned
    assert "Pruefungs Ergebnisse" in parsed["tags"] or "pruefungs_ergebnisse" not in parsed["tags"]
    assert len(parsed["tags"]) <= 3
    assert len(parsed["keywords"]) == 3

