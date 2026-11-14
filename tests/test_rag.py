"""
Automated Unit Tests for RAG Knowledge Retrieval Pipeline.
Validates chunking, vector indexing, retrieval precision,
source attribution, and graceful handling of unsupported/irrelevant queries.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.rag_engine import RAGEngine, DocumentChunk
from config import DOCUMENTS_DIR


@pytest.fixture
def rag_instance():
    return RAGEngine(documents_dir=DOCUMENTS_DIR)


def test_rag_indexes_clinical_documents(rag_instance):
    """Verify RAG engine indexes approved protocol files from knowledge base."""
    assert len(rag_instance.indexed_files) >= 3
    assert len(rag_instance.chunks) > 10
    assert rag_instance.vectorizer is not None
    assert rag_instance.tfidf_matrix is not None


def test_rag_retrieves_emergency_evidence_for_chest_pain(rag_instance):
    """Verify query for acute chest pain retrieves emergency escalation protocol."""
    query = "crushing chest pain radiating down arm"
    results = rag_instance.retrieve(query, top_k=3)

    assert len(results) > 0
    top = results[0]
    assert "chest" in top["text"].lower() or "emergency" in top["title"].lower()
    assert top["filename"] == "campus_emergency_escalation_protocol.txt"
    assert top["score"] > 0.15


def test_rag_retrieves_respiratory_guideline_for_fever_cough(rag_instance):
    """Verify query for cough and high fever retrieves respiratory guidelines."""
    query = "cough lasting 4 days with fever"
    results = rag_instance.retrieve(query, top_k=3)

    assert len(results) > 0
    filenames = [r["filename"] for r in results]
    assert any("respiratory" in f or "triage" in f for f in filenames)


def test_rag_handles_irrelevant_query_gracefully(rag_instance):
    """Verify totally irrelevant domain query returns empty list due to score threshold."""
    query = "quantum electrodynamics and orbital spacecraft docking mechanics"
    results = rag_instance.retrieve(query, min_score=0.20)
    assert len(results) == 0


def test_rag_grounded_evidence_citations(rag_instance):
    """Verify generated evidence contains explicit source organization and section citations."""
    symptoms = ["severe shortness of breath / stridor"]
    evidence = rag_instance.generate_grounded_evidence(patient_symptoms=symptoms)

    assert evidence["has_evidence"] is True
    assert len(evidence["retrieved_chunks"]) > 0
    assert "campus_emergency_escalation_protocol.txt" in evidence["summary"]
    assert "disclaimer" in evidence


def test_rag_unsupported_query_returns_safety_fallback(rag_instance):
    """Verify query without evidence generates safety explanation rather than hallucinations."""
    evidence = rag_instance.generate_grounded_evidence(
        patient_symptoms=["Galactic warp coil plasma fluctuation zyx987"]
    )
    assert evidence["has_evidence"] is False
    assert "No matching institutional clinical guidelines were found" in evidence["summary"]
