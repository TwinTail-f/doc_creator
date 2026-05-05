"""
Shared test fixtures available to all test modules.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def minimal_confluence_config() -> dict:
    """Minimal valid ConfluenceConfigSchema-compatible dict for unit tests."""
    return {
        "url": "https://confluence.example.com",
        "token": "test-token-abc123",
        "space": "TEST",
        "verify_ssl": False,
        "confluence_request_timeout": 30,
        "publish_batch_size": 10,
        "publish_batch_delay_seconds": 0.0,
        "target_release_version": "Platform 2.0",
    }
