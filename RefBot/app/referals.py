# referals.py
from aiogram import types, Bot
import app.db as db
from app.keyboards import (
    main_menu_keyboard, subscription_keyboard,
     withdraw_keyboard 
)
from datetime import datetime
import aiosqlite
from aiogram.exceptions import TelegramAPIError
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def handle_start_command(message: types.Message, bot: Bot):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    # Обработка реферальной ссылки
    if ' ' in message.text:
        referrer_id = message.text.split(' ')[1]
        try:
            referrer_id = int(referrer_id)
            if referrer_id != user_id:
                if not user:
                    await db.create_user(user_id, referrer_id)
                    await message.answer("Вы зарегистрированы по реферальной ссылке! Для продолжения напишите еще раз /start")
                    await give_referral_bonus(referrer_id, user_id, bot)  # Передаем bot в give_referral_bonus
                else:
                    await message.answer("Вы уже зарегистрированы.")
            else:
                await message.answer("Нельзя регистрироваться по собственной реферальной ссылке!")
            return
        except ValueError:
            await message.answer("Некорректный реферальный код.")
            return

    if not user:
        await db.create_user(user_id)
        await message.answer("Привет! Добро пожаловать в бот.")
        await message.answer("Чтобы использовать бота, вам нужно подписаться на наш канал.")
        await message.answer("Чтобы продолжить, подпишитесь на наш канал:", reply_markup=subscription_keyboard)
    else:
        # Проверяем статус подписки
        if user.get("is_subscribed", False):
            await message.answer("Добро пожаловать! Вы уже подписаны и можете пользоваться ботом.", reply_markup=main_menu_keyboard)
        else:
            await message.answer("Чтобы продолжить, подпишитесь на наш канал:", reply_markup=subscription_keyboard)

async def handle_sub_channel(callback: types.CallbackQuery, bot: Bot, *, channel_id):
    """Обработчик нажатия кнопки 'Я подписался'."""
    try:
        user_id = callback.from_user.id
        user = await db.get_user(user_id)

        # Проверяем, был ли уже начислен бонус за подписку
        
        channel_id_from_db = await db.get_channel_id()
        channel_id = channel_id_from_db or channel_id

        if not channel_id:
            await callback.answer("Канал/чат не настроен. Обратитесь к администратору.", show_alert=True)
            return

        try:
            chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        except TelegramAPIError as e:
            print(f"Ошибка при получении информации о пользователе из канала: {e}")
            await callback.answer("Произошла ошибка при проверке подписки. Попробуйте позже.", show_alert=True)
            return

        if chat_member.status != 'left':
            # Начисляем бонус пользователю за подписку
            await db.update_balance(user_id, 1.0)
            await db.mark_as_subscribed(user_id)

            # Отмечаем, что бонус за подписку начислен
            await db.update_subscription_bonus_received(user_id)

            # Получаем ID реферера
            referrer_id = await db.get_referrer_id(user_id)

            if referrer_id:
                # Начисляем бонус рефереру за реферала 1 уровня
                await db.update_balance(referrer_id, 1.0)

                # Увеличиваем счетчик рефералов первого уровня
                await db.add_referral(referrer_id, 1)

                # Уведомляем реферера
                await bot.send_message(referrer_id, f"Ваш реферал подписался и получил бонус! Вам начислено 1.0 рублей.")

            await bot.send_message(
                chat_id=callback.message.chat.id,
                text="Спасибо за подписку! Теперь вы можете пользоваться ботом.",
                reply_markup=main_menu_keyboard
            )

            # Обновляем баланс для вывода средств
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text="Ваш баланс для вывода средств обновлен.",
            )
        else:
            await callback.message.edit_text(
                "Вы еще не подписаны на канал. Пожалуйста, подпишитесь.",
                reply_markup=subscription_keyboard
            )
    except aiosqlite.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
        await callback.answer("Произошла ошибка при работе с базой данных. Попробуйте позже.", show_alert=True)


async def give_referral_bonus(referrer_id: int, new_user_id: int, bot: Bot):
    """Начисление бонусов за рефералов."""
    try:
        # Проверяем, подписан ли реферал на канал
        new_user = await db.get_user(new_user_id)
        if new_user and new_user.get('is_subscribed', False):
            bonus_amount = 1.0  # 1 рубль за подписку реферала
        else:
            bonus_amount = 0.5  # 0.5 рубля, если реферал не подписан

        # Начисляем бонус рефереру
        await db.update_balance(referrer_id, bonus_amount)

        # Уведомляем реферера
        await bot.send_message(referrer_id, f"По вашей реферальной ссылке зарегистрировался новый пользователь! Вам начислено {bonus_amount} рублей.")

    except Exception as e:
        logging.exception("Ошибка при начислении реферального бонуса")

async def handle_get_bonus(message: types.Message):
    """Обработчик нажатия кнопки 'Получить withdraw_keyboard'."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if user:
        # Проверяем, получил ли пользователь бонус ранее
        last_bonus_time = await db.get_last_bonus_time(user_id)
        if last_bonus_time:
            try:
                last_bonus_datetime = datetime.strptime(last_bonus_time, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                time_diff = now - last_bonus_datetime
                hours_diff = time_diff.total_seconds() / 3600

                if hours_diff < 24:  # Время между бонусами (24 часа)
                    await message.answer(
                        f"Вы уже получали бонус сегодня. Подождите {24 - int(hours_diff)} часов."
                        
                    )
                    return
            except Exception as e:
                print(f"Ошибка при обработке времени: {e}")
                await message.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)
                return

        # Начисляем бонус пользователю
        await db.update_balance(user_id, 1.0)
        await db.update_last_bonus_time(user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        await db.update_bonus_count(user_id)

        # Проверяем, является ли пользователь рефералом 1 уровня
        if user['referral_level1'] > 0:
            # Получаем ID реферера
            referrer_id = await db.get_referrer_id(user_id)

            if referrer_id:
                # Начисляем бонус рефереру
                await db.update_balance(referrer_id, 0.1)

                # Увеличиваем счетчик рефералов второго уровня
                await db.add_referral(referrer_id, 2)

                # Уведомляем реферера
                await message.answer (referrer_id, f"Ваш реферал получил бонус! Вам начислено 0.1 рублей.")

        # Обновляем баланс для вывода средств
        await message.answer("Бонус получен! Ваш баланс для вывода средств обновлен.")
    else:
        await message.answer("Профиль не найден.")


async def handle_profile(message: types.Message):
    """Обработчик для отображения профиля пользователя."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if user:
        bot_stats = await db.get_bot_stats()

        # Формируем текст профиля
        profile_info = (
            " Ваш профиль:\n\n"
            f"- 🆔 Мой ID: {user_id}\n"
            f"- 🫂 Рефералов всего: {user['referral_level1']} чел.\n"
            f"- 🎁 Получено бонусов: {user['bonus_count']} (сколько раз был получен бонус)\n"
            f"- 💳 Баланс: {round(user['balance'], 2)} руб.\n"
        )
        await message.answer(profile_info)
    else:
        await message.answer("Профиль не найден.")


async def handle_referral_program(message: types.Message):
    """Обработчик для отображения информации о партнерской программе."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if user:
        # Генерируем реферальную ссылку
        bot_name = "EMRN_BOT"
        referral_link = f"https://t.me/{bot_name}?start={user_id}"

        # Формируем текст для отображения информации о рефералах
        referral_info = (
            f"Вот твоя реферальная ссылка: {referral_link}\n\n"
            f"Рефералы первого уровня: {user['referral_level1']}"
        )

        await message.answer(referral_info)
    else:
        await message.answer("Профиль не найден.")

