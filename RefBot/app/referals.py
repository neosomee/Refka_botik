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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# Настройка логирования
logging.basicConfig(level=logging.INFO)



# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def notify_admin_new_user(message: types.Message, bot: Bot):
    """Уведомляет администраторов о новом пользователе."""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    referrer_id = None

    # Обработка реферальной ссылки
    if ' ' in message.text:
        referrer_id = message.text.split(' ')[1]
        try:
            referrer_id = int(referrer_id)
        except ValueError:
            referrer_id = None

    admin_message = f"Новый пользователь зашел в бота!\n\n"
    admin_message += f"ID: {user_id}\n"
    admin_message += f"Ник: @{username}\n"

    if referrer_id:
        admin_message += f"Зашел по реферальной ссылке пользователя с ID: {referrer_id}"
    else:
        admin_message += "Зашел без реферальной ссылки."

    from main import ADMIN_ID
    for admin_id in ADMIN_ID:
        try:
            await bot.send_message(admin_id, admin_message)
        except TelegramAPIError as e:
            logging.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")


async def handle_start_command(message: types.Message, bot: Bot):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"

    # Проверяем наличие пользователя в базе данных
    user = await db.get_user(user_id)

    # Обработка реферальной ссылки
    if ' ' in message.text:
        referrer_id = message.text.split(' ')[1]
        try:
            referrer_id = int(referrer_id)
            if referrer_id != user_id:
                if not user:
                    # Если пользователя нет в базе данных - создаем его с указанием реферера.
                    await db.create_user(user_id, username, referrer_id)
                    await message.answer("🟢 Вы зарегистрированы по реферальной ссылке! Для продолжения напишите еще раз /start")
                    await give_referral_bonus_on_link(referrer_id, bot)

                    # Уведомляем администраторов о новом пользователе
                    await notify_admin_new_user(message, bot)

                    return
                else:
                    await message.answer("🟢 Вы уже зарегистрированы.")
                    return
            else:
                await message.answer("🟠 Нельзя регистрироваться по собственной реферальной ссылке!")
                return
        except ValueError:
            await message.answer("🟠 Некорректный реферальный код.")
            return

    if not user:
        # Если пользователя нет в базе данных - создаем его.
        await db.create_user(user_id, username)
        await message.answer("🟢 Привет! Добро пожаловать в бот.")
        await message.answer("🟠 Чтобы использовать бота, вам нужно подписаться на наш канал.")
        await message.answer("🟠 Чтобы продолжить, подпишитесь на наш канал:", reply_markup=subscription_keyboard)

        # Уведомляем администраторов о новом пользователе.
        await notify_admin_new_user(message, bot)

        return

    # Если пользователь уже существует
    if user.get("is_subscribed", False):
        await message.answer("🟢 Добро пожаловать! Вы уже подписаны и можете пользоваться ботом.", reply_markup=main_menu_keyboard)
    else:
        await message.answer("🟠 Чтобы продолжить, подпишитесь на наш канал:", reply_markup=subscription_keyboard)


async def handle_sub_channel(callback: types.CallbackQuery, bot: Bot, channel_id: int):
    """Обработчик нажатия кнопки 'Я подписался'."""
    try:
        user_id = callback.from_user.id
        user = await db.get_user(user_id)

        # Проверяем, получили ли мы пользователя из базы данных
        if user is None:
            logging.warning(f"Пользователь с ID {user_id} не найден в базе данных!")
            await callback.answer("Произошла ошибка. Пользователь не найден.", show_alert=True)
            return

        # Проверяем, был ли уже начислен бонус за подписку
        channel_id_from_db = await db.get_channel_id()
        channel_id = channel_id_from_db or channel_id

        if not channel_id:
            await callback.answer("🔴 Канал/чат не настроен. Обратитесь к администратору.", show_alert=True)
            return

        try:
            chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        except TelegramAPIError as e:
            print(f"🔴 Ошибка при получении информации о пользователе из канала: {e}")
            await callback.answer("🔴 Произошла ошибка при проверке подписки. Попробуйте позже.", show_alert=True)
            return

        # Проверяем, подписан ли пользователь на канал
        if chat_member.status in ('member', 'administrator', 'creator', 'restricted'):
            # Пользователь подписан или является админом/создателем

            # Если у пользователя статус restricted, возможно, он временно ограничен в правах
            # В этом случае мы не начисляем бонус, но считаем, что он подписан на канал
            if chat_member.status == 'restricted':
                await callback.message.answer("🟣 Вы подписаны на канал, но имеете временные ограничения. Бонус не начислен.",
                                              reply_markup=types.ReplyKeyboardRemove())
                return

            # Проверяем, был ли уже начислен бонус за подписку
            if not user.get('subscription_bonus_received', False):
                # Начисляем бонус пользователю за подписку
                await db.update_balance(user_id, 0.10)
                await db.mark_as_subscribed(user_id)

                # Отмечаем, что бонус за подписку начислен
                await db.update_subscription_bonus_received(user_id)

                # Выводим сообщение о подписке и получении бонуса
                await callback.message.edit_text(
                    "🟢 Спасибо за подписку! Вам начислен бонус 0.10 руб.",
                    
                )

                # Получаем ID реферера
                referrer_id = await db.get_referrer_id(user_id)

                if referrer_id:

                    await db.add_referral(referrer_id, 1)
                    # Проверяем, был ли уже начислен бонус рефереру за этого реферала
                    if not await db.check_referral_bonus(referrer_id, user_id):
                        # Начисляем бонус рефереру за реферала 1 уровня
                        await db.update_balance(referrer_id, 1.0)

                        # Отмечаем, что бонус рефереру начислен
                        await db.mark_referral_bonus(referrer_id, user_id)

                        # Уведомляем реферера
                        await bot.send_message(referrer_id,
                                               f"🟢 Ваш реферал подписался и получил бонус! Вам начислено 1.0 рублей.")
                    else:
                        await bot.send_message(referrer_id,
                                               f"✔️Вы уже получили бонус за этого реферала.")

            else:
                inline_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="✔️Подписаться", url="https://t.me/EMRN_CHANNEL")],
                        [InlineKeyboardButton(text="✔️Я подписался", callback_data="sub_channel")]
                    ]
                )
                await callback.message.edit_text(
                    "⭕ Вы еще не подписаны на канал. Пожалуйста, подпишитесь.",
                    reply_markup=inline_keyboard  # Используем InlineKeyboardMarkup
                )
    except aiosqlite.Error as e:
        print(f"⭕ Ошибка при работе с базой данных: {e}")
        await callback.answer("⭕ Произошла ошибка при работе с базой данных. Попробуйте позже.", show_alert=True)

    


async def handle_get_bonus(message: types.Message, bot: Bot):
    """Обработчик нажатия кнопки 'Получить withdraw_keyboard'."""
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await message.answer("⭕️ Профиль не найден.")
        return

    # Проверяем, получил ли пользователь бонус ранее
    last_bonus_time = await db.get_last_bonus_time(user_id)
    if last_bonus_time:
        try:
            last_bonus_datetime = datetime.strptime(last_bonus_time, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            time_diff = now - last_bonus_datetime
            hours_diff = time_diff.total_seconds() / 3600  # Разница в часах

            if hours_diff < 24:  # Кулдаун 24 часа
                await message.answer("⭕️ Вы уже получали бонус. Пожалуйста, подождите 24 часа перед следующим запросом.")
                return
        except Exception as e:
            logger.exception("Ошибка при обработке времени:")
            await message.answer("⭕️ Произошла ошибка. Попробуйте позже.", show_alert=True)
            return

    bonus_amount = 0.15  # Бонус для реферала
    referral_bonus_amount = 0.05  # Бонус для реферера

    # Получаем ID реферера
    referrer_id = await db.get_referrer_id(user_id)
    logger.info(f"Для пользователя {user_id} получен реферер ID: {referrer_id}")

    # Начисляем бонус пользователю
    await db.update_balance(user_id, bonus_amount)
    logger.info(f"Пользователю {user_id} начислен бонус {bonus_amount}")
    await db.update_last_bonus_time(user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    await db.update_bonus_count(user_id)

    # Начисляем бонус рефереру каждый раз, когда его реферал получает бонус
    if referrer_id:
        # Начисляем бонус рефереру
        await db.update_balance(referrer_id, referral_bonus_amount)  # Начисляем бонус рефереру
        logger.info(f"Рефереру {referrer_id} начислен бонус {referral_bonus_amount}")

        try:
            # Уведомляем реферера о начислении бонуса
            await bot.send_message(referrer_id, f"✅ Вам начислено {referral_bonus_amount:.2f} руб. за вашего реферала!")
        except Exception as e:
            logger.exception(f"Не удалось отправить уведомление рефереру {referrer_id}:")
    
    else:
        logger.info("Реферер не найден.")

    # Обновляем баланс для вывода средств и уведомляем пользователя о получении бонуса
    await message.answer(f"✅ Бонус получен! Ваш баланс для вывода средств обновлен. Вам начислено {bonus_amount:.2f} руб.")




                         
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
            f"- 🫂 Рефералов первого уровня: {user['referral_level1']} чел.\n"
            f"- 🎁 Получено бонусов: {user['bonus_count']} (сколько раз был получен бонус)\n"
            f"- 💳 Баланс: {round(user['balance'], 2)} руб.\n"
            f"- 💸 Выплачено: {round(user.get('paid_amount', 0), 2)} руб.\n"
            f"- 👥 пользователей всего: {bot_stats.get('total_users')} \n"
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
            f"☑️ Вот твоя реферальная ссылка: {referral_link}\n\n"
            f"☑️ Рефералы первого уровня: {user['referral_level1']}"
        )

        await message.answer(referral_info)
    else:
        await message.answer("⭕ Профиль не найден.")

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
        await bot.send_message(referrer_id, f"☑️ По вашей реферальной ссылке зарегистрировался новый пользователь! Вам начислено {bonus_amount} руб.")

    except Exception as e:
        logging.exception("🔴 Ошибка при начислении реферального бонуса")


async def give_referral_bonus_on_link(referrer_id: int, bot: Bot):
    """Начисление бонуса рефереру за переход по реферальной ссылке."""
    try:
        bonus_amount = 0.5

        await db.update_balance(referrer_id, bonus_amount)
        await bot.send_message(referrer_id, f"☑️ По вашей реферальной ссылке перешли! Вам начислено {bonus_amount} руб.")

    except Exception as e:
        logging.exception("🔴 Ошибка при начислении бонуса за переход по ссылке")