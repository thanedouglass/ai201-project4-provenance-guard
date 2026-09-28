"""
SQLite Database Layer for Provenance Guard.
Provides persistent audit logging, creator appeals management,
provenance certificates, and analytics reporting.
"""

import sqlite3
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import Config

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create a thread-safe connection to the SQLite database."""
    path = db_path or Config.DATABASE_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_db()

    def init_db(self):
        """Create necessary tables and indexes if they do not already exist."""
        # Ensure parent directory exists
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with get_connection(self.db_path) as conn:
            # Submissions & Audit Trail Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                content_excerpt TEXT NOT NULL,
                content_type TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                raw_scores TEXT NOT NULL,
                composite_score REAL NOT NULL,
                attribution TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                label_variant TEXT NOT NULL,
                transparency_label TEXT NOT NULL,
                is_discordant INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                metadata TEXT
            );
            """)

            # Appeals Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id TEXT PRIMARY KEY,
                submission_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                assistance_type TEXT DEFAULT 'pure_human_no_ai',
                supporting_evidence TEXT,
                status TEXT NOT NULL DEFAULT 'under_review',
                reviewer_notes TEXT,
                resolved_at TEXT,
                FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            );
            """)

            # Provenance Certificates Table (Stretch Feature)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id TEXT PRIMARY KEY,
                submission_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                verification_method TEXT NOT NULL,
                verification_hash TEXT NOT NULL,
                badge_level TEXT NOT NULL,
                is_valid INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            );
            """)

            # Indexes for high performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON submissions(created_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_attribution ON submissions(attribution);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_appeals_submission_id ON appeals(submission_id);")
            conn.commit()

    def record_submission(self, content: str, content_type: str, analysis: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record a new content evaluation to the immutable audit log.
        Returns the generated submission_id.
        """
        submission_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        excerpt = (content[:150] + "...") if len(content) > 150 else content

        with get_connection(self.db_path) as conn:
            conn.execute("""
            INSERT INTO submissions (
                id, created_at, content_hash, content_excerpt, content_type, word_count,
                raw_scores, composite_score, attribution, confidence_score,
                label_variant, transparency_label, is_discordant, status, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (
                submission_id,
                created_at,
                content_hash,
                excerpt,
                content_type,
                analysis.get("word_count", len(content.split())),
                json.dumps(analysis.get("signals", {})),
                analysis["composite_ai_score"],
                analysis["attribution"],
                analysis["confidence_score"],
                analysis["label_variant"],
                analysis["transparency_label"],
                1 if analysis.get("is_discordant") else 0,
                json.dumps(metadata or {})
            ))
            conn.commit()

        return submission_id

    def get_submission(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full details of a submission, including associated appeals and certificates."""
        with get_connection(self.db_path) as conn:
            sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
            if not sub:
                return None

            sub_dict = dict(sub)
            sub_dict["raw_scores"] = json.loads(sub_dict["raw_scores"])
            sub_dict["metadata"] = json.loads(sub_dict["metadata"]) if sub_dict["metadata"] else {}

            # Fetch appeals for this submission
            appeals_cursor = conn.execute("SELECT * FROM appeals WHERE submission_id = ? ORDER BY created_at DESC", (submission_id,))
            sub_dict["appeals"] = [dict(row) for row in appeals_cursor.fetchall()]

            # Fetch certificate if any
            cert_row = conn.execute("SELECT * FROM certificates WHERE submission_id = ?", (submission_id,)).fetchone()
            sub_dict["certificate"] = dict(cert_row) if cert_row else None

            return sub_dict

    def record_appeal(self, submission_id: str, creator_id: str, reasoning: str,
                      assistance_type: str = "pure_human_no_ai",
                      supporting_evidence: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a contest appeal and transition submission status to 'under_review'.
        """
        with get_connection(self.db_path) as conn:
            # Check submission exists
            sub = conn.execute("SELECT id, status FROM submissions WHERE id = ?", (submission_id,)).fetchone()
            if not sub:
                raise ValueError(f"Submission with ID '{submission_id}' not found.")

            # Check if an appeal is already pending for this submission
            existing = conn.execute(
                "SELECT id FROM appeals WHERE submission_id = ? AND status = 'under_review'",
                (submission_id,)
            ).fetchone()
            if existing:
                raise ValueError("An active appeal is already under review for this submission.")

            appeal_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()

            # Insert appeal
            conn.execute("""
            INSERT INTO appeals (
                id, submission_id, created_at, creator_id, reasoning,
                assistance_type, supporting_evidence, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'under_review')
            """, (
                appeal_id,
                submission_id,
                created_at,
                creator_id,
                reasoning,
                assistance_type,
                supporting_evidence or ""
            ))

            # Update submission status
            conn.execute("UPDATE submissions SET status = 'under_review' WHERE id = ?", (submission_id,))
            conn.commit()

            return {
                "appeal_id": appeal_id,
                "submission_id": submission_id,
                "created_at": created_at,
                "status": "under_review",
                "creator_id": creator_id
            }

    def resolve_appeal(self, appeal_id: str, new_status: str, reviewer_notes: str = "") -> Dict[str, Any]:
        """
        Resolve an appeal as 'accepted' or 'rejected', updating both tables.
        """
        if new_status not in ("accepted", "rejected"):
            raise ValueError("new_status must be 'accepted' or 'rejected'")

        resolved_at = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            appeal = conn.execute("SELECT submission_id FROM appeals WHERE id = ?", (appeal_id,)).fetchone()
            if not appeal:
                raise ValueError(f"Appeal ID '{appeal_id}' not found.")

            submission_id = appeal["submission_id"]
            sub_status = "appeal_accepted" if new_status == "accepted" else "appeal_rejected"

            conn.execute("""
            UPDATE appeals
            SET status = ?, reviewer_notes = ?, resolved_at = ?
            WHERE id = ?
            """, (new_status, reviewer_notes, resolved_at, appeal_id))

            conn.execute("UPDATE submissions SET status = ? WHERE id = ?", (sub_status, submission_id))
            conn.commit()

            return {
                "appeal_id": appeal_id,
                "submission_id": submission_id,
                "status": new_status,
                "submission_status": sub_status,
                "resolved_at": resolved_at
            }

    def issue_certificate(self, submission_id: str, creator_id: str,
                          verification_method: str = "draft_revision_history",
                          badge_level: str = "verified_human_author") -> Dict[str, Any]:
        """
        Issue a cryptographic 'Verified Human' provenance certificate for an approved submission.
        """
        with get_connection(self.db_path) as conn:
            sub = conn.execute("SELECT id, attribution, content_hash FROM submissions WHERE id = ?", (submission_id,)).fetchone()
            if not sub:
                raise ValueError(f"Submission '{submission_id}' not found.")

            cert_id = str(uuid.uuid4())
            issued_at = datetime.now(timezone.utc).isoformat()
            # Cryptographic signature hash
            raw_data = f"{cert_id}:{submission_id}:{creator_id}:{sub['content_hash']}:{issued_at}"
            v_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

            conn.execute("""
            INSERT INTO certificates (
                id, submission_id, creator_id, issued_at, verification_method, verification_hash, badge_level, is_valid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (cert_id, submission_id, creator_id, issued_at, verification_method, v_hash, badge_level))
            conn.commit()

            return {
                "certificate_id": cert_id,
                "submission_id": submission_id,
                "creator_id": creator_id,
                "issued_at": issued_at,
                "verification_method": verification_method,
                "verification_hash": v_hash,
                "badge_level": badge_level,
                "is_valid": True,
                "badge_markup": f'<span class="provenance-badge badge-verified" data-cert="{cert_id}">🛡️ Verified Human Origin</span>'
            }

    def get_certificate(self, cert_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve certificate details by certificate ID."""
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM certificates WHERE id = ?", (cert_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["certificate_id"] = res["id"]
            sub = conn.execute("SELECT content_excerpt, attribution, confidence_score FROM submissions WHERE id = ?", (res["submission_id"],)).fetchone()
            if sub:
                res["submission_details"] = dict(sub)
            return res

    def get_audit_log(self, limit: int = 50, offset: int = 0, status: Optional[str] = None, attribution: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve structured audit log records with filtering and pagination."""
        query = "SELECT * FROM submissions"
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if attribution:
            conditions.append("attribution = ?")
            params.append(attribution)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["raw_scores"] = json.loads(item["raw_scores"])
                item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else {}
                # Include appeal count
                appeal_count = conn.execute("SELECT COUNT(*) as c FROM appeals WHERE submission_id = ?", (item["id"],)).fetchone()["c"]
                item["appeal_count"] = appeal_count
                results.append(item)
            return results

    def get_appeals(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List appeals with their associated submission context."""
        query = """
        SELECT a.*, s.content_excerpt, s.attribution as original_attribution,
               s.confidence_score as original_confidence, s.label_variant
        FROM appeals a
        JOIN submissions s ON a.submission_id = s.id
        """
        params = []
        if status:
            query += " WHERE a.status = ?"
            params.append(status)

        query += " ORDER BY a.created_at DESC LIMIT ?"
        params.append(limit)

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_analytics(self) -> Dict[str, Any]:
        """Compute aggregate platform analytics and telemetry."""
        with get_connection(self.db_path) as conn:
            total_submissions = conn.execute("SELECT COUNT(*) as c FROM submissions").fetchone()["c"]

            # Attribution breakdown
            human_count = conn.execute("SELECT COUNT(*) as c FROM submissions WHERE attribution = 'human'").fetchone()["c"]
            ai_count = conn.execute("SELECT COUNT(*) as c FROM submissions WHERE attribution = 'ai'").fetchone()["c"]
            uncertain_count = conn.execute("SELECT COUNT(*) as c FROM submissions WHERE attribution = 'uncertain'").fetchone()["c"]

            # Appeals metrics
            total_appeals = conn.execute("SELECT COUNT(*) as c FROM appeals").fetchone()["c"]
            pending_appeals = conn.execute("SELECT COUNT(*) as c FROM appeals WHERE status = 'under_review'").fetchone()["c"]
            accepted_appeals = conn.execute("SELECT COUNT(*) as c FROM appeals WHERE status = 'accepted'").fetchone()["c"]
            rejected_appeals = conn.execute("SELECT COUNT(*) as c FROM appeals WHERE status = 'rejected'").fetchone()["c"]

            # Confidence & Discordance metrics
            avg_conf = conn.execute("SELECT AVG(confidence_score) as a FROM submissions").fetchone()["a"] or 0.0
            avg_score = conn.execute("SELECT AVG(composite_score) as a FROM submissions").fetchone()["a"] or 0.0
            discordant_count = conn.execute("SELECT COUNT(*) as c FROM submissions WHERE is_discordant = 1").fetchone()["c"]

            # Certificates issued
            total_certs = conn.execute("SELECT COUNT(*) as c FROM certificates WHERE is_valid = 1").fetchone()["c"]

            # Appeal rate calculation: percentage of non-human decisions appealed
            flagged_count = ai_count + uncertain_count
            appeal_rate = (total_appeals / flagged_count * 100.0) if flagged_count > 0 else 0.0

            return {
                "total_submissions": total_submissions,
                "attributions": {
                    "human": human_count,
                    "ai": ai_count,
                    "uncertain": uncertain_count,
                    "human_percent": round((human_count / total_submissions * 100), 1) if total_submissions > 0 else 0.0,
                    "ai_percent": round((ai_count / total_submissions * 100), 1) if total_submissions > 0 else 0.0,
                    "uncertain_percent": round((uncertain_count / total_submissions * 100), 1) if total_submissions > 0 else 0.0
                },
                "appeals": {
                    "total": total_appeals,
                    "pending": pending_appeals,
                    "accepted": accepted_appeals,
                    "rejected": rejected_appeals,
                    "appeal_rate_percent": round(appeal_rate, 2)
                },
                "telemetry": {
                    "avg_confidence": round(avg_conf, 4),
                    "avg_composite_score": round(avg_score, 4),
                    "discordant_signal_count": discordant_count,
                    "certificates_issued": total_certs
                }
            }
