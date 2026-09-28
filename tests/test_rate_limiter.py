"""
Tests for Flask-Limiter rate limiting on Provenance Guard endpoints.
"""

import pytest
import os
import tempfile
from app import create_app
from config import Config

def test_rate_limiting_on_submit():
    """Verify that rapid requests beyond the rate limit trigger HTTP 429."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    
    # Override rate limit to a small value for testing
    original_limit = Config.RATE_LIMIT_SUBMIT
    Config.RATE_LIMIT_SUBMIT = "3 per minute"

    try:
        app = create_app(db_path=db_path)
        app.config["TESTING"] = False  # Limiter is typically disabled when TESTING is True

        with app.test_client() as client:
            payload = {"content": "Sample sentence for testing rate limiting thresholds."}
            
            # Send 3 allowed requests
            statuses = []
            for _ in range(3):
                r = client.post("/submit", json=payload)
                statuses.append(r.status_code)

            assert 201 in statuses

            # 4th request must trigger 429 Too Many Requests
            fourth_res = client.post("/submit", json=payload)
            assert fourth_res.status_code == 429
            data = fourth_res.get_json()
            assert "Rate limit exceeded" in data.get("error", "")
    finally:
        Config.RATE_LIMIT_SUBMIT = original_limit
        os.close(db_fd)
        if os.path.exists(db_path):
            os.remove(db_path)
