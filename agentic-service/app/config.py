from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime configuration for the model gateway, read from environment/.env.

    MODEL_PROVIDER selects which backend the gateway talks to. Everything else
    is provider-specific configuration with sane local-dev defaults.
    """

    def __init__(self) -> None:
        self.model_provider: str = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()
        self.model_timeout_seconds: float = float(os.getenv("MODEL_TIMEOUT_SECONDS", "60"))

        # Ollama (local) settings
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

        # Which engine runs Brain 2's actions (Thalamus, Hippocampus, Broca, ...).
        # "langgraph" (default): the Python agents, via MODEL_PROVIDER above.
        # "claude": the matching Claude agent in .claude/agents/, run with the
        # Claude Code CLI on whatever account `claude` is signed in with.
        # Embeddings (/v1/embed) and /v1/complete always stay on MODEL_PROVIDER.
        self.agent_engine: str = os.getenv("AGENT_ENGINE", "langgraph").strip().lower()
        self.claude_cli: str = os.getenv("CLAUDE_CLI", "claude")
        self.claude_model: str = os.getenv("CLAUDE_MODEL", "")  # empty = each agent's own model
        self.claude_timeout_seconds: float = float(os.getenv("CLAUDE_TIMEOUT_SECONDS", "120"))
        # Folder whose .claude/agents/ holds the agents — the repo root by default.
        self.claude_project_dir: str = os.getenv(
            "CLAUDE_PROJECT_DIR", str(Path(__file__).resolve().parents[2])
        )

        # AWS Bedrock settings
        self.aws_region: str = os.getenv("AWS_REGION", "us-east-1")
        self.bedrock_model_id: str = os.getenv(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        self.bedrock_embedding_model_id: str = os.getenv(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        )


settings = Settings()
