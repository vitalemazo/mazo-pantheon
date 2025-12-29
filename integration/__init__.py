"""
Mazo Hedge Fund Integration Package

This package provides tools for integrating AI Hedge Fund with Mazo
for enhanced financial research and trading decisions.
"""

from integration.mazo_bridge import MazoBridge, MazoResponse
from integration.config import config, IntegrationConfig

__all__ = [
    "MazoBridge",
    "MazoResponse",
    "config",
    "IntegrationConfig",
]
