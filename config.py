"""
Configuration settings for Provenance Guard.
Loads environment variables and defines system thresholds, rate limits, and model parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "provenance-guard-secure-key-2026")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = FLASK_ENV == "development"
    PORT = int(os.getenv("PORT", 5000))

    # Database configuration
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "provenance_guard.db"))

    # Groq API configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", 10.0))

    # Rate Limiting configuration
    # 10 submissions per minute, 100 per hour
    RATE_LIMIT_SUBMIT = os.getenv("RATE_LIMIT_SUBMIT", "10 per minute; 100 per hour")
    RATE_LIMIT_APPEAL = os.getenv("RATE_LIMIT_APPEAL", "5 per minute; 20 per hour")
    RATE_LIMIT_STORAGE_URL = "memory://"

    # Calibration Thresholds
    HUMAN_THRESHOLD = 0.35
    AI_THRESHOLD = 0.70
    VARIANCE_DISCORDANCE_THRESHOLD = 0.28
    SHORT_CONTENT_WORD_COUNT = 50

    # Ensemble Weights
    WEIGHT_GROQ = 0.40
    WEIGHT_STYLOMETRICS = 0.30
    WEIGHT_ENTROPY = 0.20
    WEIGHT_METADATA = 0.10
