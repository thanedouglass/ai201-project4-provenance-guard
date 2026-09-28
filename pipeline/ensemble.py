"""
Ensemble Detection Coordinator and Calibrated Confidence Engine for Provenance Guard.
Combines multiple orthogonal detection signals into a calibrated attribution decision.
"""

import math
from typing import Dict, Any, Optional
from config import Config
from pipeline.groq_detector import GroqDetector
from pipeline.stylometrics import StylometricDetector
from pipeline.entropy_detector import EntropyDetector
from pipeline.platform_metadata import PlatformMetadataDetector
from pipeline.labels import resolve_transparency_label

class EnsemblePipeline:
    def __init__(self, groq_detector: Optional[GroqDetector] = None):
        self.groq_detector = groq_detector or GroqDetector(
            api_key=Config.GROQ_API_KEY,
            model=Config.GROQ_MODEL,
            timeout=Config.GROQ_TIMEOUT
        )
        self.stylometric_detector = StylometricDetector()
        self.entropy_detector = EntropyDetector()
        self.metadata_detector = PlatformMetadataDetector()

    def evaluate(self, content: str, content_type: str = "text", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute full multi-signal pipeline on submitted content and return structured attribution.
        """
        text = (content or "").strip()
        words = text.split()
        word_count = len(words)
        is_short_content = word_count < Config.SHORT_CONTENT_WORD_COUNT

        # 1. Execute Signal 1: Groq LLM Forensic Inspector
        s1_result = self.groq_detector.analyze(text)

        # 2. Execute Signal 2: Stylometric & Lexical Diversity Heuristics
        s2_result = self.stylometric_detector.analyze(text)

        # 3. Execute Signal 3: Structural Entropy & Compression
        s3_result = self.entropy_detector.analyze(text)

        # 4. Execute Signal 4: Platform Metadata & Structural Context
        s4_result = self.metadata_detector.analyze(text, content_type=content_type, metadata=metadata)

        # Base weights from Config
        weights = {
            "signal_1_groq": Config.WEIGHT_GROQ,
            "signal_2_stylometrics": Config.WEIGHT_STYLOMETRICS,
            "signal_3_entropy": Config.WEIGHT_ENTROPY,
            "signal_4_metadata": Config.WEIGHT_METADATA if s4_result.get("has_metadata") else 0.0
        }

        # Normalize weights so they sum to 1.0
        total_weight = sum(weights.values())
        norm_weights = {k: v / total_weight for k, v in weights.items()}

        scores = {
            "signal_1_groq": s1_result["score"],
            "signal_2_stylometrics": s2_result["score"],
            "signal_3_entropy": s3_result["score"],
            "signal_4_metadata": s4_result["score"]
        }

        # Weighted Mean Score (estimated raw AI probability)
        raw_composite_score = sum(norm_weights[k] * scores[k] for k in norm_weights)

        # Epistemic Uncertainty: Inter-signal variance
        signal_variance = sum(
            norm_weights[k] * ((scores[k] - raw_composite_score) ** 2)
            for k in norm_weights
        )
        signal_std_dev = math.sqrt(signal_variance)

        # Variance Penalty: If signals disagree significantly (std_dev > 0.22),
        # pull score toward ambiguous center (0.50)
        calibrated_score = raw_composite_score
        is_discordant = signal_std_dev >= Config.VARIANCE_DISCORDANCE_THRESHOLD
        if signal_std_dev > 0.22:
            shrinkage = min(0.50, signal_std_dev * 0.8)
            calibrated_score = (raw_composite_score * (1.0 - shrinkage)) + (0.50 * shrinkage)

        # Classification and Confidence Mapping
        # If signals strongly contradict each other or content is ultra-short & borderline, force uncertain
        if is_discordant:
            attribution = "uncertain"
            label_variant_key = "uncertain"
            confidence = round(max(0.60, min(0.95, 1.0 - (2.0 * abs(calibrated_score - 0.50)))), 4)
            uncertainty_reason = f"High signal discordance (standard deviation={signal_std_dev:.3f}) indicates conflicting markers."
        elif is_short_content and (0.30 <= calibrated_score <= 0.75):
            attribution = "uncertain"
            label_variant_key = "uncertain"
            confidence = 0.65
            uncertainty_reason = f"Ultra-short content ({word_count} words) falls within conservative uncertainty margin."
        elif calibrated_score <= Config.HUMAN_THRESHOLD:
            attribution = "human"
            label_variant_key = "high_confidence_human"
            # Confidence is high when score is close to 0.0
            confidence = round(max(0.65, min(0.99, 1.0 - calibrated_score)), 4)
            uncertainty_reason = "Consistent human stylometric and contextual markers across signals."
        elif calibrated_score >= Config.AI_THRESHOLD:
            attribution = "ai"
            label_variant_key = "high_confidence_ai"
            # Confidence is high when score is close to 1.0
            confidence = round(max(0.70, min(0.99, calibrated_score)), 4)
            uncertainty_reason = "Strong synthetic syntactic cadences, transitional clichés, and low entropy."
        else:
            attribution = "uncertain"
            label_variant_key = "uncertain"
            # Uncertainty confidence reflects how close it is to the ambiguous center (0.50)
            confidence = round(max(0.60, min(0.95, 1.0 - (2.0 * abs(calibrated_score - 0.50)))), 4)
            uncertainty_reason = f"Calibrated score ({calibrated_score:.2f}) lies in the ambiguous threshold band ({Config.HUMAN_THRESHOLD} - {Config.AI_THRESHOLD})."

        label_details = resolve_transparency_label(label_variant_key)

        return {
            "attribution": attribution,
            "confidence_score": confidence,
            "composite_ai_score": round(calibrated_score, 4),
            "raw_composite_score": round(raw_composite_score, 4),
            "signal_discordance_std": round(signal_std_dev, 4),
            "is_discordant": is_discordant,
            "is_short_content": is_short_content,
            "word_count": word_count,
            "label_variant": label_variant_key,
            "transparency_label": label_details["text"],
            "transparency_badge": label_details["display_name"],
            "uncertainty_reason": uncertainty_reason,
            "signals": {
                "signal_1_groq_llm": {
                    "name": "Groq LLM Forensic Inspector",
                    "weight": round(norm_weights["signal_1_groq"], 2),
                    "ai_score": s1_result["score"],
                    "confidence": s1_result["confidence"],
                    "model": s1_result.get("model"),
                    "source": s1_result.get("source"),
                    "markers": s1_result.get("markers", []),
                    "reasoning": s1_result.get("reasoning")
                },
                "signal_2_stylometrics": {
                    "name": "Stylometric & Lexical Diversity Heuristics",
                    "weight": round(norm_weights["signal_2_stylometrics"], 2),
                    "ai_score": s2_result["score"],
                    "confidence": s2_result["confidence"],
                    "metrics": s2_result.get("metrics", {}),
                    "reasoning": s2_result.get("reasoning")
                },
                "signal_3_entropy": {
                    "name": "Compression & N-Gram Repetition Detector",
                    "weight": round(norm_weights["signal_3_entropy"], 2),
                    "ai_score": s3_result["score"],
                    "confidence": s3_result["confidence"],
                    "metrics": s3_result.get("metrics", {}),
                    "reasoning": s3_result.get("reasoning")
                },
                "signal_4_metadata": {
                    "name": "Platform & Structural Context Analyzer",
                    "weight": round(norm_weights["signal_4_metadata"], 2),
                    "ai_score": s4_result["score"],
                    "confidence": s4_result["confidence"],
                    "has_metadata": s4_result.get("has_metadata", False),
                    "platform": s4_result.get("platform"),
                    "markers": s4_result.get("markers", []),
                    "reasoning": s4_result.get("reasoning")
                }
            }
        }
