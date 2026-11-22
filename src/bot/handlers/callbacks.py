"""Callback query handlers for task confirmation and modifications."""

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.tasks import TaskConfirmCallback
from src.schemas.task import ExtractedTask
from src.services.task_service import create_tasks_batch

logger = logging.getLogger(__name__)

router = Router(name="callbacks")
callbacks_router = router


@router.callback_query(TaskConfirmCallback.filter())
async def task_confirm_callback(
    callback_query: CallbackQuery,
    callback_data: TaskConfirmCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle task confirmation actions (save, edit, delete) with tenant security enforcement.

    Verifies REQ-AI-03, REQ-TSK-01, REQ-NFR-02:
    - Rejects callback if from_user.id does not match callback_data.user_id with alert.
    - If action == 'save':
      - Deserializes pending_tasks from FSM state.
      - If missing/expired, alerts user and removes keyboard.
      - Persists tasks to database with status 'todo' via create_tasks_batch.
      - Edits message to confirmation text and removes keyboard.
      - Clears FSM state and answers callback.
    - If action == 'edit':
      - Clears FSM state.
      - Edits message to prompt user for new input and removes keyboard.
      - Answers callback.
    - If action == 'delete':
      - Clears FSM state via state.clear().
      - If message is a Message instance, edits message text to cancellation notice and removes keyboard.
      - Answers callback with cancellation notification ("Скасовано!").
    """
    if callback_query.from_user is None:
        return

    # REQ-NFR-02 & REQ-AI-03: Tenant Security Check
    if callback_query.from_user.id != callback_data.user_id:
        await callback_query.answer(
            "⚠️ Ви не можете керувати завданнями іншого користувача.",
            show_alert=True,
        )
        return

    if callback_data.action == "save":
        state_data = await state.get_data()
        pending_raw = state_data.get("pending_tasks")

        if not pending_raw:
            await callback_query.answer(
                "⚠️ Завдання вже збережено або сесія застаріла.",
                show_alert=True,
            )
            if callback_query.message and isinstance(callback_query.message, Message):
                await callback_query.message.edit_reply_markup(reply_markup=None)
            return

        extracted_tasks = [ExtractedTask.model_validate(item) for item in pending_raw]
        await create_tasks_batch(
            session=session,
            user_id=callback_query.from_user.id,
            tasks=extracted_tasks,
        )

        if callback_query.message and isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                text="✅ <b>Завдання успішно збережено!</b>",
                reply_markup=None,
            )

        await state.clear()
        await callback_query.answer("Збережено!")
        return

    if callback_data.action == "edit":
        await state.clear()
        if callback_query.message and isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                text="✏️ Будь ласка, надиктуйте або надішліть текстом нове формулювання завдань.",
                reply_markup=None,
            )
        await callback_query.answer()
        return

    if callback_data.action == "delete":
        await state.clear()
        if callback_query.message and isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                text="🗑️ <b>Завдання скасовано та видалено.</b>",
                reply_markup=None,
            )
        await callback_query.answer("Скасовано!")
        return

    await callback_query.answer()
