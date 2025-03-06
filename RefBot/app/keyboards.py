from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from app.db import get_payeer_id

# Клавиатура для подписки на канал
subscription_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал", url="https://t.me/hutneosome")],
        [InlineKeyboardButton(text="Я подписался", callback_data='sub_channel')]
    ]
)

# Основное меню с ReplyKeyboardMarkup
def create_main_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="ПРОФИЛЬ")
    builder.button(text="ПОЛУЧИТЬ БОНУС")
    builder.button(text="О ПРОЕКТЕ")
    builder.button(text="ВЫВОД СРЕДСТВ")
    builder.button(text="РЕФЕРАЛЬНАЯ СИСТЕМА")
    builder.adjust(2)  # Разместить кнопки в 2 столбца
    return builder.as_markup(resize_keyboard=True)

main_menu_keyboard = create_main_menu_keyboard()


# Клавиатура для вывода бонуса
withdraw_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Вывести бонус", callback_data='get_bonus')],
            ]
)



# Создаем InlineKeyboardMarkup с использованием InlineKeyboardBuilder
def create_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Заявки на вывод", callback_data='view_withdrawals')
    builder.adjust(1)
    return builder.as_markup()

admin_menu_keyboard = create_admin_keyboard()




async def create_withdrawal_keyboard(withdrawals):
    """Создание клавиатуры для заявок на вывод средств."""
    builder = InlineKeyboardBuilder()
    
    for withdrawal in withdrawals:
        user_id = withdrawal['user_id']
        total_amount = withdrawal['total_amount']
        payeer_id = await get_payeer_id(user_id)
        
        if payeer_id:
            button_pay = InlineKeyboardButton(
                text=f"Оплатить {total_amount} руб.",
                callback_data=f"pay_{user_id}_{total_amount}"
            )
            button = InlineKeyboardButton(
                text=f"{payeer_id}",
                callback_data=f"withdraw_{user_id}_{total_amount}"
            )
            button_delete = InlineKeyboardButton(
                text=f"Удалить",
                callback_data=f"delete_user_{user_id}"
            )
            builder.row(button, button_pay, button_delete)           
        else:
            # Если кошелька нет, выводим сообщение об ошибке
            button = InlineKeyboardButton(
                text=f"Ошибка: кошелек не найден для ID {user_id}",
                callback_data=f"withdraw_{user_id}_{total_amount}"
            )
            builder.add(button)
    
    return builder.as_markup()