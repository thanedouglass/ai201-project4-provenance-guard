"""
Integration tests for Provenance Guard Flask API endpoints.
Tests submission, appeals workflow, audit logs, certificates, and analytics.
"""

import pytest
import json
import tempfile
import os
from app import create_app
from database import DatabaseManager

@pytest.fixture
def client():
    # Use temporary SQLite file for isolated test database
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    if os.path.exists(db_path):
        os.remove(db_path)

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert "groq_model" in data

def test_submit_valid_content(client):
    payload = {
        "content": (
            "The morning fog crept over the harbor, cold and tasting faintly of kerosene. "
            "Old Marcus pulled his knit cap down over his ears and cursed the diesel engine that refused to turn over. "
            "Twenty years on this pier, and every November was the same slow war with frost."
        ),
        "content_type": "short_story",
        "creator_id": "marcus_author"
    }
    res = client.post("/submit", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert "submission_id" in data
    assert data["attribution"] in ("human", "ai", "uncertain")
    assert 0.0 <= data["confidence_score"] <= 1.0
    assert "transparency_label" in data
    assert "signals" in data
    assert data["status"] == "active"

def test_submit_invalid_payload(client):
    # Empty payload
    res = client.post("/submit", json={})
    assert res.status_code == 400

    # Too short text
    res = client.post("/submit", json={"content": "Hi"})
    assert res.status_code == 400

def test_appeals_workflow_and_edge_cases(client):
    # 1. Create a submission first
    submit_res = client.post("/submit", json={
        "content": "In conclusion, it is important to delve into the vibrant tapestry of technology and human growth. Furthermore, this serves as a testament to progress.",
        "content_type": "blog_post",
        "creator_id": "test_creator"
    })
    sub_id = submit_res.get_json()["submission_id"]

    # 2. File an appeal with insufficient reasoning (< 20 chars) -> should fail
    fail_res = client.post("/appeal", json={
        "submission_id": sub_id,
        "creator_id": "test_creator",
        "reasoning": "Too short"
    })
    assert fail_res.status_code == 400

    # 3. File a valid appeal
    appeal_res = client.post("/appeal", json={
        "submission_id": sub_id,
        "creator_id": "test_creator",
        "reasoning": "I wrote this essay by hand during my morning commute. The transition phrases were chosen intentionally for formal rhetorical effect.",
        "assistance_type": "pure_human_no_ai",
        "supporting_evidence": "https://example.com/draft-notes"
    })
    assert appeal_res.status_code == 201
    appeal_data = appeal_res.get_json()
    appeal_id = appeal_data["appeal"]["appeal_id"]

    # 4. Verify submission status updated to 'under_review'
    sub_check = client.get(f"/submit/{sub_id}")
    assert sub_check.status_code == 200
    assert sub_check.get_json()["status"] == "under_review"

    # 5. Edge Case 1: Repeated/Spam appeal on already active review -> should return 409 Conflict
    dup_res = client.post("/appeal", json={
        "submission_id": sub_id,
        "creator_id": "test_creator",
        "reasoning": "Duplicate spam appeal while the previous appeal is still pending review."
    })
    assert dup_res.status_code == 409

    # 6. Resolve the appeal
    resolve_res = client.post(f"/appeal/{appeal_id}/resolve", json={
        "status": "accepted",
        "reviewer_notes": "Reviewed author handwritten notes and verified human intent."
    })
    assert resolve_res.status_code == 200
    assert resolve_res.get_json()["resolution"]["status"] == "accepted"

    # Verify submission updated to 'appeal_accepted'
    sub_final = client.get(f"/submit/{sub_id}")
    assert sub_final.get_json()["status"] == "appeal_accepted"

def test_audit_log_endpoint(client):
    # Submit 3 distinct contents to populate the audit log
    for i in range(3):
        client.post("/submit", json={
            "content": f"Sample creative work number {i} for testing audit log persistence and structure.",
            "content_type": "blog_post"
        })

    log_res = client.get("/log?limit=10")
    assert log_res.status_code == 200
    log_data = log_res.get_json()
    assert log_data["total_returned"] >= 3
    assert len(log_data["entries"]) >= 3

    entry = log_data["entries"][0]
    assert "id" in entry
    assert "created_at" in entry
    assert "composite_score" in entry
    assert "attribution" in entry
    assert "confidence_score" in entry
    assert "transparency_label" in entry
    assert "raw_scores" in entry

def test_provenance_certificate(client):
    # Submit content
    submit_res = client.post("/submit", json={
        "content": "Authentic poetry written under the northern lights.",
        "content_type": "poem"
    })
    sub_id = submit_res.get_json()["submission_id"]

    # Issue certificate
    cert_res = client.post("/certificate/issue", json={
        "submission_id": sub_id,
        "creator_id": "poet_jane",
        "verification_method": "draft_revision_history"
    })
    assert cert_res.status_code == 201
    cert_data = cert_res.get_json()
    cert_id = cert_data["certificate"]["certificate_id"]

    # Fetch certificate
    fetch_res = client.get(f"/certificate/{cert_id}")
    assert fetch_res.status_code == 200
    assert fetch_res.get_json()["certificate_id"] == cert_id
    assert fetch_res.get_json()["is_valid"] == 1

def test_analytics_endpoint(client):
    # Submit a sample
    client.post("/submit", json={
        "content": "Creative story excerpt for analytics telemetry testing.",
        "content_type": "short_story"
    })
    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_submissions" in data
    assert "attributions" in data
    assert "appeals" in data
    assert "telemetry" in data
    assert data["total_submissions"] >= 1
