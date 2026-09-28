"""
Signal 4: Platform Metadata & Multi-Modal Context Analyzer.
Analyzes structured metadata from platforms like Reddit, X (Twitter),
and artistic image descriptions/alt-text to evaluate origin authenticity.
"""

import re
from typing import Dict, Any, Optional

class PlatformMetadataDetector:
    def __init__(self):
        pass

    def analyze(self, text: str, content_type: str = "text", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze platform-specific metadata and structural cues.
        Returns a probability score (0.0 to 1.0) and confidence.
        """
        if not metadata:
            return {
                "score": 0.50,
                "confidence": 0.50,
                "has_metadata": False,
                "platform": content_type,
                "markers": [],
                "reasoning": "No platform metadata provided; neutral structural weighting applied."
            }

        score = 0.50
        markers = []
        platform = content_type.lower()

        # 1. Reddit Metadata Analysis
        if platform == "reddit" or "subreddit" in metadata:
            karma = metadata.get("author_karma", 100)
            account_age_days = metadata.get("account_age_days", 30)
            upvote_ratio = metadata.get("upvote_ratio", 0.85)
            has_edits = metadata.get("has_edits", False)
            title = metadata.get("title", "")

            # Bot accounts often have extremely low karma or brand new account age
            if karma < 10 and account_age_days < 7:
                score += 0.20
                markers.append("new_account_low_karma")
            elif karma > 500 and account_age_days > 90:
                score -= 0.15
                markers.append("established_reddit_contributor")

            if has_edits:
                score -= 0.10
                markers.append("contains_organic_edits")

            # Check title for robotic phrasing
            if title and re.search(r'\b(as an ai|in-depth analysis|unveiling the|exploring the)\b', title.lower()):
                score += 0.15
                markers.append("formulaic_reddit_title")

        # 2. X / Twitter Metadata Analysis
        elif platform in ("x", "twitter") or "tweet_length" in metadata or "hashtags" in metadata:
            hashtags = metadata.get("hashtags", [])
            is_thread = metadata.get("is_thread", False)
            thread_position = metadata.get("thread_position", 1)
            verified_creator = metadata.get("verified_creator", False)

            # Excessive hashtag packing is characteristic of spam bots
            if len(hashtags) > 5:
                score += 0.20
                markers.append("excessive_hashtags")
            elif 0 < len(hashtags) <= 2:
                score -= 0.05

            if verified_creator:
                score -= 0.15
                markers.append("verified_creator_handle")

            # Check for AI thread hook patterns
            if is_thread and thread_position == 1:
                first_lines = text.lower()[:150]
                if any(hook in first_lines for hook in ["a thread 🧵", "here's what you need to know", "most people don't know this"]):
                    score += 0.12
                    markers.append("viral_ai_thread_hook")

        # 3. Image Description / Alt-Text Analysis
        elif platform in ("image_description", "alt_text", "art_metadata") or "image_medium" in metadata:
            medium = metadata.get("image_medium", "")
            tags = metadata.get("tags", [])
            tag_str = " ".join(tags).lower() + " " + text.lower()

            # Midjourney/Stable Diffusion prompt markers
            ai_art_tags = [
                "octane render", "unreal engine", "8k resolution", "photorealistic",
                "volumetric lighting", "trending on artstation", "hyperrealistic", "masterpiece"
            ]
            found_art_tags = [t for t in ai_art_tags if t in tag_str]
            if found_art_tags:
                score += 0.35
                markers.append(f"ai_art_prompt_syntax:{','.join(found_art_tags)}")
            elif medium.lower() in ["oil on canvas", "watercolor", "charcoal", "sketch", "gouache"]:
                score -= 0.15
                markers.append("traditional_medium_provenance")

        # 4. Generic Creative Work Metadata (Revisions, Drafts)
        revisions_count = metadata.get("revision_count", 0)
        draft_time_minutes = metadata.get("draft_time_minutes", 0)
        if revisions_count >= 3 or draft_time_minutes >= 30:
            score -= 0.20
            markers.append("proven_revision_history")

        final_score = max(0.05, min(0.95, score))
        confidence = 0.75 if markers else 0.50

        reasoning = (
            f"Platform metadata ({platform}): detected cues: {', '.join(markers) if markers else 'none'}."
        )

        return {
            "score": round(final_score, 4),
            "confidence": round(confidence, 4),
            "has_metadata": True,
            "platform": platform,
            "markers": markers,
            "reasoning": reasoning
        }
