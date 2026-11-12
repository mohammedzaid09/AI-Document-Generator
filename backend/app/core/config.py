import os

from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI",
    "http://127.0.0.1:8000/api/auth/github/callback",
)
GITHUB_TOKEN_ENCRYPTION_KEY = os.getenv("GITHUB_TOKEN_ENCRYPTION_KEY")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash",
)

GEMINI_MAX_OUTPUT_TOKENS = int(
    os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1024")
)

AI_DAILY_REQUEST_LIMIT = int(
    os.getenv("AI_DAILY_REQUEST_LIMIT", "10")
)

AI_DAILY_TOKEN_LIMIT = int(
    os.getenv("AI_DAILY_TOKEN_LIMIT", "10000")
)

AI_MAX_INPUT_TOKENS = int(
    os.getenv("AI_MAX_INPUT_TOKENS", "8000")
)

AI_MAX_OUTPUT_TOKENS = int(
    os.getenv("AI_MAX_OUTPUT_TOKENS", "1024")
)

if not GITHUB_WEBHOOK_SECRET:
    raise ValueError("GITHUB_WEBHOOK_SECRET is not configured")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not configured")

if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY is not configured")