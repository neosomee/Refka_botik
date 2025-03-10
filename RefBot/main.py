# main.py

import aiosqlite
import asyncio
import logging
import app.db as db
from aiogram import Bot, Dispatcher, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, BaseFilter, StateFilter
from app.keyboards import subscription_keyboard
from app.db import (
    delete_withdrawal, get_user, create_db, init_bonus_settings, update_user_balance, create_users_table, add_withdrawal, get_user_balance, get_withdrawals, get_saved_payeer_id, save_payeer_id, create_payeer_wallets_table
)
from app.referals import (
    handle_start_command, handle_sub_channel, handle_get_bonus,
    handle_profile, handle_referral_program, notify_admin_new_user
)

from app.db import DATABASE_FILE
from app.keyboards import (
    main_menu_keyboard,
    admin_menu_keyboard, create_withdrawal_keyboard, mailing_confirmation_keyboard
)

# Класс состояний для вывода средств
class WithdrawalStates(StatesGroup):
    payeer_id = State()
    amount = State()

# Класс состояний для рассылки
class MailingState(StatesGroup):
    waiting_for_text = State()
    confirming = State()

# Конфигурация
TOKEN = 
CHANNEL_ID = 
ADMIN_ID = []
CHANNEL_FOR_PAYMENT = 

# Инициализация хранилища
storage = MemoryStorage()

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# Инициализация роутера
router = Router()

# Фильтр для админа
class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        print(f"Проверяем ID пользователя: {user_id}")
        print(f"Список админов: {ADMIN_ID}")
        return user_id in ADMIN_ID


# Пользовательский фильтр для текста
class MyTextFilter(BaseFilter):
    def __init__(self, text: str):
        self.text = text

    async def __call__(self, message: Message) -> bool:
        return message.text.lower() == self.text.lower()

class AdminState(StatesGroup):
    enter_amount = State()
    enter_user_id = State()
    enter_withdraw_data = State()

# Обработчики команд
@router.message(Command("start"))
async def start_command_handler(message: types.Message, bot: Bot):
    await handle_start_command(message, bot)  # Передаем bot в handle_start_command


# Обработчик callback для кнопки "Я подписался"
@router.callback_query(lambda callback: callback.data == "sub_channel")
async def sub_channel_handler(callback: types.CallbackQuery, bot: Bot):
    await handle_sub_channel(callback, bot, channel_id=CHANNEL_ID)

# Обработчики для кнопок меню
@router.message(MyTextFilter("💼 Профиль"))
async def profile_handler(message: types.Message):
    await handle_profile(message)

@router.message(MyTextFilter("🎁 Бонус"))
async def get_bonus_handler(message: types.Message, bot: Bot):  # Add bot argument
    await handle_get_bonus(message, bot)  # Передаем bot


@router.message(MyTextFilter("🧑‍🤝‍🧑 реферальная система"))
async def referral_handler(message: types.Message):
    await handle_referral_program(message)

@router.message(MyTextFilter("ℹ️ о проекте"))
async def about_handler(message: types.Message):
    await message.answer("""
💰 Заработай с нами! 💰

Приветствуем Вас в нашем уникальном проекте, где Вы можете зарабатывать деньги, приглашая друзей!

Как это работает?

Приглашайте друзей: Поделитесь своей реферальной ссылкой с друзьями и знакомыми.

Получайте 1 рубль за каждого: За каждого приглашенного человека, который зарегистрируется по Вашей ссылке, проявит активность (подписка на канал/получение бонуса), Вы получите 1 рубль на свой баланс.

Выводите деньги: Как только Ваш баланс достигнет минимальной суммы для вывода, Вы сможете легко вывести свои заработанные средства.

Почему стоит участвовать?

Простота: Не требуется никаких специальных навыков.

Быстрый заработок: Зарабатывайте деньги, просто делясь ссылкой.

Поддержка: Наша команда всегда готова помочь Вам с любыми вопросами.

Присоединяйтесь к нам и начните зарабатывать прямо сейчас! 💸
""")

def validate_withdrawal_amount(amount: float) -> bool:
    """Проверяет, соответствует ли сумма вывода минимальному порогу."""
    return amount >= 10  # Минимальная сумма вывода 10 рублей

@router.message(lambda message: message.text == "💰 ВЫВОД", StateFilter(None))
async def withdraw_cmd(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.clear()

    user_id = message.from_user.id
    user = await get_user(user_id)

    if user:
        payeer_id = await get_saved_payeer_id(user_id)

        if payeer_id:
            await state.set_state(WithdrawalStates.amount)
            await message.answer("🟢 Введите сумму вывода:")
        else:
            await state.set_state(WithdrawalStates.payeer_id)
            await message.answer("🟢 Введите номер кошелька PAYEER. Настоятельно рекомендуем 5 раз перепроверять номер кошелька он начинается на P английскую:", reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer("🔴 Профиль не найден.")
        await state.clear()

@router.message(WithdrawalStates.payeer_id)
async def get_payeer_id(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.clear()

    # Сохраняем Payeer ID и username
    await save_payeer_id(
        user_id=message.from_user.id,
        payeer_id=message.text,
        username=message.from_user.username or "unknown"
    )

    await state.set_state(WithdrawalStates.amount)
    await message.answer("⚪ Введите сумму вывода:")

@router.message(WithdrawalStates.amount)
async def get_amount(message: types.Message, state: FSMContext):
    if await state.get_state() != WithdrawalStates.amount:
        await state.clear()
        await message.answer("🔴 Пожалуйста, начните процесс вывода средств заново.", reply_markup=main_menu_keyboard)
        return

    if not message.text.replace('.', '', 1).isdigit():
        await message.answer("🔴 Пожалуйста, введите корректную сумму. Вывод средств отменен.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("🔴 Пожалуйста, введите корректную сумму. Вывод средств отменен.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    user_id = message.from_user.id
    user = await get_user(user_id)

    # Проверяем условия для вывода средств
    if user['referral_level1'] < 10:  # Необходимо не менее 10 рефералов
        await message.answer("🔴 Для вывода средств необходимо пригласить не менее 10 рефералов.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    if amount < 10:  # Минимальная сумма вывода составляет 10 рублей
        await message.answer("🔴 Минимальная сумма вывода составляет 10 рублей.", reply_markup=main_menu_keyboard)
        await state.clear()
        return

    payeer_id = await get_saved_payeer_id(user_id)

    try:
        # Получаем баланс пользователя
        balance = await get_user_balance(user_id)
        if balance is None:
            await message.answer("🔴 Пользователь не найден.", reply_markup=main_menu_keyboard)
            await state.clear()
            return

        if balance < amount:
            await message.answer("🔴 Недостаточно средств на балансе.", reply_markup=main_menu_keyboard)
            await state.clear()
            return

        # Вычитаем сумму из баланса и добавляем заявку на вывод
        await update_user_balance(user_id, -amount)
        await add_withdrawal(user_id, payeer_id, amount)
        await message.answer("✅ Заявка на вывод средств успешно создана.", reply_markup=main_menu_keyboard)
        await state.clear()

    except Exception as e:
        logging.error(f"🔴 Ошибка при обработке вывода средств: {e}")
        await message.answer("🔴 Произошла ошибка при обработке запроса. Попробуйте позже.", reply_markup=main_menu_keyboard)
        await state.clear()


@router.message(Command("admin"))
async def admin_command_handler(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.clear()

    if message.from_user.id in ADMIN_ID:  # Проверка прав
        await message.answer("🟢 Админ-меню:", reply_markup=admin_menu_keyboard)
    else:
        await message.answer("🔴 У вас нет доступа к админ-меню.")


# Обработчики админ-меню
@router.callback_query(lambda callback: callback.data == "back_to_admin")
async def back_to_admin_handler(callback: types.CallbackQuery):
    if callback.from_user.id in ADMIN_ID:  # Проверка прав
        await callback.message.edit_text("🟢 Админ-меню:", reply_markup=admin_menu_keyboard)
    else:
        await callback.answer("🔴 У вас нет доступа к админ-меню.")

# Обработчик кнопки "Заявки на вывод"
@router.callback_query(lambda callback: callback.data == "start_mailing")
async def start_mailing_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🟢 Впишите внизу текст, который вы хотите отправить в рассылке:")
    await state.set_state(MailingState.waiting_for_text)

@router.message(MailingState.waiting_for_text)
async def process_mailing_text(message: types.Message, state: FSMContext):
    mailing_text = message.text
    await message.answer(f"Вы ввели следующий текст для рассылки:\n{mailing_text}")
    await state.update_data(mailing_text=mailing_text)
    await state.set_state(MailingState.confirming)
    await message.answer("🟢 Подтвердите отправку рассылки:", reply_markup=mailing_confirmation_keyboard)

@router.callback_query(lambda callback: callback.data == "confirm_mailing")
async def confirm_mailing_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✔️ Рассылка начата. Пожалуйста, подождите...")
    data = await state.get_data()
    mailing_text = data.get('mailing_text')

    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_user = TRUE") as cursor:
            user_ids = await cursor.fetchall()

    for row in user_ids:
        user_id = row[0]  # Извлекаем user_id из кортежа
        await bot.send_message(user_id, mailing_text)
        await asyncio.sleep(7)  # Задержка в 7 секунд между отправками

    await bot.send_message(ADMIN_ID[0], "✔️ Рассылка завершена.")  # Убедитесь, что ADMIN_ID - это список
    await state.clear()

@router.callback_query(lambda callback: callback.data == "cancel_mailing")
async def cancel_mailing_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔴 Рассылка отменена.")
    await state.clear()

@router.callback_query(lambda callback: callback.data == "view_withdrawals")
async def view_withdrawals_handler(callback: types.CallbackQuery):
    try:
        withdrawals = await db.get_withdrawals_for_admin()

        if not withdrawals:
            await callback.message.edit_text("🔴 Нет активных заявок на вывод средств.")
            return

        # Ожидаем выполнения асинхронной функции
        keyboard = await create_withdrawal_keyboard(withdrawals)

        await callback.message.edit_text("🟢 Активные заявки на вывод средств:", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Ошибка в view_withdrawals_handler: {e}")
        await callback.answer("🔴 Произошла ошибка при обработке запроса. Попробуйте позже.")

async def send_payment_message(user_id: int, amount: float):
    """Отправка сообщения о выплате в Telegram-канал."""
    user = await db.get_user(user_id)
    username = user.get('username', "unknown")

    message_text = f"@{username} вывел {amount} руб на PAYEER."
    await bot.send_message(CHANNEL_FOR_PAYMENT, message_text)

@router.callback_query(lambda callback: callback.data.startswith("pay_"))
async def pay_withdrawal_callback(callback: types.CallbackQuery):
    data = callback.data.split("_")
    user_id = int(data[1])  # Извлекаем user_id из данных
    amount = float(data[2])  # Извлекаем amount из данных

    # Обновляем выплаченную сумму
    await db.update_paid_amount(user_id, amount)

    # Удаляем заявку на вывод
    await db.delete_withdrawal(user_id)

    await callback.answer("🟢 Оплачено!")

    # Отправляем уведомление о новой выплате
    await send_payment_message(user_id, amount)

    # Обновляем список заявок
    await view_withdrawals_handler(callback)

@router.callback_query(lambda callback: callback.data.startswith("delete_user_"))
async def delete_user_callback(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[2])  # Извлекаем user_id из данных

        await db.delete_withdrawal(user_id)

        await callback.answer(f"Пользователь с ID {user_id} удален.")

        await view_withdrawals_handler(callback)
    except Exception as e:
        logging.error(f"Ошибка при удалении пользователя: {e}")
        await callback.answer("Произошла ошибка при удалении пользователя.")



async def main():
    await create_db()
    await init_bonus_settings()
    await create_payeer_wallets_table()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
