"""
Pytest configuration for freqtrade-hyperliquid tests
"""

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
