"""Pytest configuration for NanoGridBot tests."""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def mock_config(temp_dir):
    """Create a mock configuration for testing."""
    from nanogridbot.config import Config

    config = Config(
        base_dir=temp_dir,
        data_dir=temp_dir / "data",
        store_dir=temp_dir / "store",
        groups_dir=temp_dir / "groups",
        debug=True,
    )
    return config
