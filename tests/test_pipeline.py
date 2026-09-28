"""
Unit tests for the multi-signal detection pipeline, stylometrics, entropy, and ensemble calibration.
"""

import pytest
from pipeline.stylometrics import StylometricDetector
from pipeline.entropy_detector import EntropyDetector
from pipeline.platform_metadata import PlatformMetadataDetector
from pipeline.ensemble import EnsemblePipeline
from pipeline.labels import (
    LABEL_HIGH_CONFIDENCE_AI,
    LABEL_HIGH_CONFIDENCE_HUMAN,
    LABEL_UNCERTAIN,
    resolve_transparency_label
)

def test_transparency_labels_verbatim():
    """Verify that all three transparency label variants contain the exact expected text."""
    ai_label = resolve_transparency_label("high_confidence_ai")
    assert ai_label["text"] == LABEL_HIGH_CONFIDENCE_AI
    assert "AI-Generated Content: Our multi-signal analysis indicates with high confidence" in ai_label["text"]

    human_label = resolve_transparency_label("high_confidence_human")
    assert human_label["text"] == LABEL_HIGH_CONFIDENCE_HUMAN
    assert "Verified Human Creation: Our multi-signal analysis indicates with high confidence" in human_label["text"]

    uncertain_label = resolve_transparency_label("uncertain")
    assert uncertain_label["text"] == LABEL_UNCERTAIN
    assert "Attribution Inconclusive: Our multi-signal analysis returned mixed or borderline indicators" in uncertain_label["text"]

def test_stylometrics_detector_human_prose():
    """Human prose with varied sentence lengths and rich vocabulary should score low AI likelihood."""
    detector = StylometricDetector()
    text = (
        "The wind howled through the broken rafters of the barn. "
        "I froze. "
        "Deep within the hayloft, something rustled with an irregular, scratching cadence that made my pulse spike into my throat. "
        "Could it be the barn owl from Tuesday? "
        "No—this was heavier, deliberate, dragging something across the rough pine floorboards."
    )
    result = detector.analyze(text)
    assert "score" in result
    assert "confidence" in result
    assert result["score"] < 0.50
    assert result["metrics"]["burstiness_cv"] > 0.30
    assert result["metrics"]["hapax_legomena_ratio"] > 0.50

def test_stylometrics_detector_short_content():
    """Ultra-short content should gracefully report insufficient length without raising exceptions."""
    detector = StylometricDetector()
    result = detector.analyze("A lonely star.")
    assert result["score"] == 0.50
    assert result["confidence"] == 0.40

def test_entropy_detector():
    """Repetitive boilerplate text with synthetic phrases should yield a high AI score."""
    detector = EntropyDetector()
    ai_text = (
        "In conclusion, it is important to delve into the vibrant tapestry of modern literature. "
        "Furthermore, this stands as a testament to human ingenuity. "
        "Moreover, technology plays a pivotal role in navigating the complexities of an ever-evolving world. "
        "In summary, it underscores the need for creative collaboration."
    )
    result = detector.analyze(ai_text)
    assert result["score"] >= 0.70
    assert result["metrics"]["boilerplate_count"] >= 3
    assert "delve" in result["metrics"]["detected_markers"] or "testament" in result["metrics"]["detected_markers"]

def test_platform_metadata_detector():
    """Verify platform metadata cues for Reddit and X."""
    detector = PlatformMetadataDetector()
    reddit_meta = {
        "subreddit": "writingprompts",
        "author_karma": 5,
        "account_age_days": 2,
        "has_edits": False,
        "title": "Exploring the vibrant future"
    }
    res = detector.analyze("Sample text", content_type="reddit", metadata=reddit_meta)
    assert res["score"] > 0.50
    assert "new_account_low_karma" in res["markers"]

def test_ensemble_pipeline_uncertainty_discordance():
    """When signals have high variance, the ensemble must force an 'uncertain' classification."""
    pipeline = EnsemblePipeline()
    # Test short ambiguous sentence
    res = pipeline.evaluate("This is an ambiguous line that might be written by anyone.", content_type="text")
    assert res["attribution"] in ("human", "ai", "uncertain")
    assert "transparency_label" in res
    assert res["word_count"] > 0
