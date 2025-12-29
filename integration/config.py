"""
Integration Configuration

Manages configuration for the Mazo Hedge Fund integration.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class IntegrationConfig:
    """Configuration for Mazo integration"""

    # Paths
    mazo_path: str = field(
        default_factory=lambda: os.environ.get(
            "MAZO_PATH",
            str(Path(__file__).parent.parent / "mazo")
        )
    )

    bun_path: str = field(
        default_factory=lambda: os.environ.get(
            "BUN_PATH",
            str(Path.home() / ".bun" / "bin" / "bun")
        )
    )

    # Timeouts
    mazo_timeout: int = field(
        default_factory=lambda: int(os.environ.get("MAZO_TIMEOUT", "300"))
    )

    # Defaults
    default_workflow_mode: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_WORKFLOW_MODE", "full")
    )

    default_research_depth: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_RESEARCH_DEPTH", "standard")
    )

    # Model settings
    default_model: str = field(
        default_factory=lambda: os.environ.get(
            "DEFAULT_MODEL",
            "claude-sonnet-4-5-20250929"
        )
    )

    # API Keys (inherited from main .env)
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY")
    )

    openai_api_base: Optional[str] = field(
        default_factory=lambda: os.environ.get("OPENAI_API_BASE")
    )

    financial_datasets_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("FINANCIAL_DATASETS_API_KEY")
    )

    def validate(self) -> bool:
        """Validate configuration"""
        errors = []

        # Check Mazo path
        if not Path(self.mazo_path).exists():
            errors.append(f"Mazo not found at {self.mazo_path}")

        # Check Bun path
        if not Path(self.bun_path).exists():
            errors.append(f"Bun not found at {self.bun_path}")

        # Check required API keys
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY not set")

        if not self.financial_datasets_api_key:
            errors.append("FINANCIAL_DATASETS_API_KEY not set")

        if errors:
            for error in errors:
                print(f"[Config Error] {error}")
            return False

        return True

    @classmethod
    def from_env(cls) -> "IntegrationConfig":
        """Load configuration from environment"""
        return cls()

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "mazo_path": self.mazo_path,
            "bun_path": self.bun_path,
            "mazo_timeout": self.mazo_timeout,
            "default_workflow_mode": self.default_workflow_mode,
            "default_research_depth": self.default_research_depth,
            "default_model": self.default_model,
            "has_openai_key": bool(self.openai_api_key),
            "has_openai_base": bool(self.openai_api_base),
            "has_financial_datasets_key": bool(self.financial_datasets_api_key),
        }


# Global config instance
config = IntegrationConfig.from_env()
