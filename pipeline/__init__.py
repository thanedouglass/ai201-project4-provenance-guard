"""
Pipeline package initialization for Provenance Guard.
"""

from pipeline.ensemble import EnsemblePipeline
from pipeline.labels import (
    LABEL_HIGH_CONFIDENCE_AI,
    LABEL_HIGH_CONFIDENCE_HUMAN,
    LABEL_UNCERTAIN,
    resolve_transparency_label
)

__all__ = [
    "EnsemblePipeline",
    "LABEL_HIGH_CONFIDENCE_AI",
    "LABEL_HIGH_CONFIDENCE_HUMAN",
    "LABEL_UNCERTAIN",
    "resolve_transparency_label"
]
