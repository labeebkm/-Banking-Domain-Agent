"""Application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.2"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
DEBUG_AGENTS = os.getenv("DEBUG_AGENTS", "1").lower() not in {"0", "false", "no"}
