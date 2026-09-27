import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://vectorless:vectorless_dev@localhost:5432/vectorless_rag"
)

# ANTHROPIC_API_KEY is read directly by the anthropic SDK; listed here only
# for reference / so `config.` is the one place that documents every env var.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# If these defaults don't resolve for your account, check
# docs.claude.com/en/docs/about-claude/models for current model names.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
CLAUDE_FAST_MODEL = os.environ.get("CLAUDE_FAST_MODEL", "claude-haiku-4-5-20251001")

NAV_BATCH_SIZE = int(os.environ.get("NAV_BATCH_SIZE", "40"))
NAV_MAX_CONCURRENCY = int(os.environ.get("NAV_MAX_CONCURRENCY", "8"))

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")]
