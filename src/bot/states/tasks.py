"""FSM state definitions for task flows."""

from aiogram.fsm.state import State, StatesGroup


class TaskIngestionState(StatesGroup):
    """FSM states for ingesting voice or text tasks."""

    waiting_confirmation = State()
    planning_tomorrow = State()
