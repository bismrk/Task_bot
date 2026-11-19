"""Smoke tests verifying environment, dependencies, and async test runner."""

import pytest


def test_core_dependencies_importable() -> None:
    """Verifies REQ-NFR-01: Core framework packages can be imported without error."""
    import aiogram
    import aiosqlite
    import apscheduler
    import fastapi
    import google.genai
    import pydantic
    import sqlalchemy

    assert aiogram is not None
    assert aiosqlite is not None
    assert apscheduler is not None
    assert fastapi is not None
    assert google.genai is not None
    assert pydantic is not None
    assert sqlalchemy is not None


@pytest.mark.asyncio
async def test_async_execution() -> None:
    """Verifies that pytest-asyncio executes coroutines as expected."""
    result = await _async_add(2, 3)
    assert result == 5


async def _async_add(a: int, b: int) -> int:
    return a + b
