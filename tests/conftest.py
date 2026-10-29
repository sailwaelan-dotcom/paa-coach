"""Fixtures et utilitaires de test pour paa-coach."""

from __future__ import annotations

from pathlib import Path
import pytest
from google.adk.events import EventActions

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class MockToolContext:
    """Simulateur léger de ToolContext ADK pour les tests unitaires sans runner."""

    def __init__(self, initial_state: dict | None = None) -> None:
        self.state = initial_state if initial_state is not None else {}
        self.actions = EventActions()


@pytest.fixture
def mock_tool_context() -> MockToolContext:
    return MockToolContext()


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
