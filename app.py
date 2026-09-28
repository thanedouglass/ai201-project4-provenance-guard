"""
Provenance Guard — Main Flask Application.
Provides rate-limited submission endpoints, appeals handling, audit logging,
provenance certification, and an interactive analytics dashboard.
"""

import os
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from database import DatabaseManager
from pipeline.ensemble import EnsemblePipeline

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("provenance_guard")

def create_app(db_path: str = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # Initialize Database & Pipeline
    db = DatabaseManager(db_path=db_path or Config.DATABASE_PATH)
    pipeline = EnsemblePipeline()

    # Rate Limiter setup (using client IP address)
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["300 per day", "100 per hour"],
        storage_uri=Config.RATE_LIMIT_STORAGE_URL,
        strategy="fixed-window"
    )

    # Attach instances to app context
    app.db = db
    app.pipeline = pipeline
    app.limiter = limiter

    # -------------------------------------------------------------
    # Error Handlers
    # -------------------------------------------------------------
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "error": "Rate limit exceeded",
            "message": "Too many requests. Provenance Guard rate limiting protects against automated inference scraping and adversarial testing.",
            "retry_after": e.description
        }), 429

    @app.errorhandler(400)
    def bad_request_handler(e):
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found_handler(e):
        return jsonify({"error": "Not Found", "message": "The requested resource was not found."}), 404

    @app.errorhandler(500)
    def server_error_handler(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

    # -------------------------------------------------------------
    # Health & System Status
    # -------------------------------------------------------------
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "healthy",
            "service": "Provenance Guard",
            "version": "1.0.0",
            "groq_model": Config.GROQ_MODEL,
            "has_groq_api_key": bool(Config.GROQ_API_KEY)
        }), 200

    # -------------------------------------------------------------
    # Content Submission Endpoint (Core Feature)
    # -------------------------------------------------------------
    @app.route("/submit", methods=["POST"])
    @app.route("/api/submit", methods=["POST"])
    @limiter.limit(Config.RATE_LIMIT_SUBMIT)
    def submit_content():
        """
        Accepts creative text content and optional platform metadata for provenance attribution.
        Returns attribution result, calibrated confidence, transparency label, and signal breakdown.
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Accept either 'content' or 'text' for maximum API compatibility
        content = (data.get("content") or data.get("text") or "").strip()
        if not content:
            return jsonify({"error": "Field 'content' (or 'text') is required and cannot be empty"}), 400

        if len(content) < 10:
            return jsonify({"error": "Content must be at least 10 characters long"}), 400

        content_type = data.get("content_type", "text")
        metadata = data.get("metadata", {})
        creator_id = data.get("creator_id", "anonymous")

        # Run multi-signal ensemble detection
        try:
            analysis = app.pipeline.evaluate(
                content=content,
                content_type=content_type,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            return jsonify({"error": "Analysis pipeline failed", "details": str(e)}), 500

        # Persist attribution decision in SQLite audit log
        submission_id = app.db.record_submission(
            content=content,
            content_type=content_type,
            analysis=analysis,
            metadata={"creator_id": creator_id, **metadata}
        )

        response_payload = {
            "submission_id": submission_id,
            "content_id": submission_id,
            "attribution": analysis["attribution"],
            "confidence": analysis["confidence_score"],
            "confidence_score": analysis["confidence_score"],
            "composite_ai_score": analysis["composite_ai_score"],
            "label_variant": analysis["label_variant"],
            "transparency_badge": analysis["transparency_badge"],
            "transparency_label": analysis["transparency_label"],
            "label": analysis["transparency_label"],
            "is_discordant": analysis["is_discordant"],
            "signal_discordance_std": analysis["signal_discordance_std"],
            "is_short_content": analysis["is_short_content"],
            "word_count": analysis["word_count"],
            "uncertainty_reason": analysis["uncertainty_reason"],
            "signals": analysis["signals"],
            "status": "active"
        }

        return jsonify(response_payload), 201

    # -------------------------------------------------------------
    # Submission Details Query
    # -------------------------------------------------------------
    @app.route("/submit/<submission_id>", methods=["GET"])
    @app.route("/api/submission/<submission_id>", methods=["GET"])
    def get_submission_details(submission_id):
        sub = app.db.get_submission(submission_id)
        if not sub:
            return jsonify({"error": f"Submission with ID '{submission_id}' not found"}), 404
        return jsonify(sub), 200

    # -------------------------------------------------------------
    # Creator Appeals Workflow (Core Feature)
    # -------------------------------------------------------------
    @app.route("/appeal", methods=["POST"])
    @app.route("/api/appeal", methods=["POST"])
    @app.route("/submit/<submission_id>/appeal", methods=["POST"])
    @limiter.limit(Config.RATE_LIMIT_APPEAL)
    def submit_appeal(submission_id=None):
        """
        Allows creators to contest a classification decision.
        Captures creator reasoning, logs the appeal, and transitions status to 'under_review'.
        """
        data = request.get_json(silent=True) or {}
        sub_id = submission_id or data.get("submission_id") or data.get("content_id")
        if not sub_id:
            return jsonify({"error": "Field 'submission_id' (or 'content_id') is required"}), 400

        creator_id = (data.get("creator_id") or "anonymous_creator").strip()

        reasoning = (data.get("reasoning") or data.get("creator_reasoning") or "").strip()
        if not reasoning or len(reasoning) < 20:
            return jsonify({"error": "Field 'reasoning' (or 'creator_reasoning') must be at least 20 characters explaining your creation process"}), 400

        assistance_type = data.get("assistance_type", "pure_human_no_ai")
        supporting_evidence = data.get("supporting_evidence", "")

        try:
            result = app.db.record_appeal(
                submission_id=sub_id,
                creator_id=creator_id,
                reasoning=reasoning,
                assistance_type=assistance_type,
                supporting_evidence=supporting_evidence
            )
            return jsonify({
                "message": "Appeal successfully filed. Content status has been updated to 'under review'.",
                "status": "under_review",
                "submission_id": sub_id,
                "content_id": sub_id,
                "appeal_reasoning": reasoning,
                "creator_reasoning": reasoning,
                "appeal": result
            }), 201
        except ValueError as ve:
            # 404 or 409 conflict
            err_msg = str(ve)
            if "not found" in err_msg.lower():
                return jsonify({"error": err_msg}), 404
            return jsonify({"error": err_msg}), 409
        except Exception as e:
            logger.error(f"Error filing appeal: {e}", exc_info=True)
            return jsonify({"error": "Failed to file appeal", "details": str(e)}), 500

    @app.route("/appeals", methods=["GET"])
    @app.route("/api/appeals", methods=["GET"])
    def list_appeals():
        status = request.args.get("status")
        limit = min(100, int(request.args.get("limit", 50)))
        appeals = app.db.get_appeals(status=status, limit=limit)
        return jsonify({"count": len(appeals), "appeals": appeals}), 200

    @app.route("/appeal/<appeal_id>/resolve", methods=["POST"])
    def resolve_appeal(appeal_id):
        """Allows platform moderators to resolve an appeal (accept or reject)."""
        data = request.get_json(silent=True) or {}
        new_status = data.get("status")
        reviewer_notes = data.get("reviewer_notes", "")

        if new_status not in ("accepted", "rejected"):
            return jsonify({"error": "Status must be 'accepted' or 'rejected'"}), 400

        try:
            res = app.db.resolve_appeal(appeal_id=appeal_id, new_status=new_status, reviewer_notes=reviewer_notes)
            return jsonify({"message": f"Appeal has been {new_status}.", "resolution": res}), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # -------------------------------------------------------------
    # Provenance Certificate (Stretch Feature)
    # -------------------------------------------------------------
    @app.route("/certificate/issue", methods=["POST"])
    @app.route("/api/certificate/issue", methods=["POST"])
    def issue_certificate():
        """
        Issues a 'Verified Human' digital provenance certificate for an eligible submission.
        """
        data = request.get_json(silent=True) or {}
        submission_id = data.get("submission_id")
        creator_id = data.get("creator_id", "verified_creator")
        verification_method = data.get("verification_method", "draft_revision_history")

        if not submission_id:
            return jsonify({"error": "Field 'submission_id' is required"}), 400

        try:
            cert = app.db.issue_certificate(
                submission_id=submission_id,
                creator_id=creator_id,
                verification_method=verification_method
            )
            return jsonify({"message": "Provenance certificate issued successfully.", "certificate": cert}), 201
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/certificate/<cert_id>", methods=["GET"])
    @app.route("/api/certificate/<cert_id>", methods=["GET"])
    def get_certificate(cert_id):
        cert = app.db.get_certificate(cert_id)
        if not cert:
            return jsonify({"error": f"Certificate '{cert_id}' not found"}), 404
        return jsonify(cert), 200

    # -------------------------------------------------------------
    # Audit Log Query Endpoint (Core Feature)
    # -------------------------------------------------------------
    @app.route("/log", methods=["GET"])
    @app.route("/api/log", methods=["GET"])
    def get_audit_log():
        """
        Returns structured audit trail records.
        Supports pagination (?limit=50&offset=0) and filters (?status=active&attribution=ai).
        """
        limit = min(100, int(request.args.get("limit", 50)))
        offset = max(0, int(request.args.get("offset", 0)))
        status = request.args.get("status")
        attribution = request.args.get("attribution")

        logs = app.db.get_audit_log(limit=limit, offset=offset, status=status, attribution=attribution)
        return jsonify({
            "total_returned": len(logs),
            "limit": limit,
            "offset": offset,
            "filters": {"status": status, "attribution": attribution},
            "entries": logs
        }), 200

    # -------------------------------------------------------------
    # Analytics & Dashboard Endpoints (Stretch Feature)
    # -------------------------------------------------------------
    @app.route("/api/analytics", methods=["GET"])
    def get_analytics():
        metrics = app.db.get_analytics()
        return jsonify(metrics), 200

    @app.route("/", methods=["GET"])
    @app.route("/dashboard", methods=["GET"])
    def dashboard_view():
        """Renders the comprehensive visual analytics and tester dashboard."""
        analytics = app.db.get_analytics()
        recent_logs = app.db.get_audit_log(limit=10)
        recent_appeals = app.db.get_appeals(limit=5)
        return render_template(
            "dashboard.html",
            analytics=analytics,
            recent_logs=recent_logs,
            recent_appeals=recent_appeals
        )

    return app

# Main entry point
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
