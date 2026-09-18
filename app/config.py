"""Application configuration and environment settings."""

import os
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TIMEOUT_SECONDS = float(os.getenv("TIMEOUT_SECONDS", "5.0"))
