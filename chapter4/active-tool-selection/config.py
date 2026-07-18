"""Configuration for Active Tool Selection Agent."""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


def _map_model_for_openrouter(model: str) -> str:
    """Map a plain model id onto OpenRouter's `provider/model` form.

    Ids that already contain "/" pass through unchanged; gpt-*/o1-*/o3-*/o4-*
    become openai/…; claude-* becomes anthropic/claude-opus-4.8.
    """
    if "/" in model:
        return model
    m = model.lower()
    if m.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return f"openai/{model}"
    if m.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return model


# Universal fallback + gpt-5.x preference: route through OpenRouter when no direct
# OPENAI_API_KEY is configured, OR when the model is a gpt-5.x id (incl. gpt-5.6*)
# which needs OpenAI org-verification on the direct API. Explicit OPENAI_BASE_URL /
# OPENAI_MODEL overrides are kept.
_OR_KEY = os.getenv("OPENROUTER_API_KEY")
if _OR_KEY and (not OPENAI_API_KEY or OPENAI_MODEL.lower().startswith("gpt-5")):
    OPENAI_API_KEY = _OR_KEY
    if not os.getenv("OPENAI_BASE_URL"):
        OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
    OPENAI_MODEL = _map_model_for_openrouter(OPENAI_MODEL)

# Agent Configuration
AGENT_TEMPERATURE = 0.7
MAX_TOOL_REQUESTS = 5  # Maximum number of tool discovery iterations

# Semantic Routing Configuration
SIMILARITY_THRESHOLD = 0.15  # Minimum similarity score for tool matching
TOP_K_SERVERS = 3  # Number of top servers to search
TOP_K_TOOLS = 5  # Number of top tools to return per server
