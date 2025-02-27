from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Клавиатура для подписки на канал
subscription_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал", url="https://t.me/EMRN_CHANNEL")],
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
    builder.button(text="Заявки на вывод", callback_data='view_withdrawals')  # Добавлена кнопка для просмотра заявок
    builder.adjust(1)
    return builder.as_markup()

admin_menu_keyboard = create_admin_keyboard()





def create_delete_user_keyboard(user_ids):
    keyboard = []

    for user_id in user_ids:
        button = InlineKeyboardButton(text=f"Удалить {user_id}", callback_data=f"delete_{user_id}")
        keyboard.append([button])

    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)