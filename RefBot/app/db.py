import aiosqlite
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DATABASE_FILE = 'bot.db'

async def create_db():
    """Создание базы данных и таблиц, если их нет."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                referral_level1 INTEGER DEFAULT 0,
                bonus REAL DEFAULT 0,
                is_subscribed BOOLEAN DEFAULT FALSE,
                bonus_count INTEGER DEFAULT 0,
                last_bonus_time TEXT,
                subscription_bonus_received BOOLEAN DEFAULT FALSE,
                referrer_id INTEGER,
                paid_amount REAL DEFAULT 0,
                sent_notification INTEGER DEFAULT 0,
                username TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                total_users INTEGER DEFAULT 0,
                total_paid REAL DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL
            )
        """)

        # Добавляем создание таблицы referral_bonuses
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_bonuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                UNIQUE (referrer_id, user_id)
            )
        """)

        await create_bonus_settings()  # Создание таблицы для настроек бонуса
        await create_withdrawals_table()
        await create_payeer_wallets_table()
        

        # Создаем запись для статистики, если её нет
        await db.execute("INSERT INTO bot_stats (total_users, total_paid) SELECT 0, 0 WHERE NOT EXISTS (SELECT 1 FROM bot_stats)")

        await db.commit()

async def create_bonus_settings():
    """Создание таблицы для настроек бонуса."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bonus_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bonus_amount REAL NOT NULL,
                bonus_time INTEGER NOT NULL
            )
        """)
        await db.commit()

async def init_bonus_settings():
    """Инициализация настроек бонуса."""
    bonus_settings = await get_bonus_settings()
    if not bonus_settings:
        await update_bonus_settings(1.0, 24)  # Инициализируем настройки по умолчанию

async def get_user(user_id: int):
    """Получение информации о пользователе."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("""
            SELECT user_id, balance, referral_level1, bonus, is_subscribed, bonus_count, last_bonus_time, subscription_bonus_received, referrer_id, paid_amount, username
            FROM users WHERE user_id = ?
        """, (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    "user_id": result[0],
                    "balance": result[1],
                    "referral_level1": result[2],
                    "bonus": result[3],
                    "is_subscribed": result[4],
                    "bonus_count": result[5],
                    "last_bonus_time": result[6],
                    "subscription_bonus_received": result[7],
                    "referrer_id": result[8],
                    "paid_amount": result[9],  # Добавлено поле paid_amount
                    "username": result[10]  # Добавлено поле username
                }
            return None




async def mark_as_subscribed(user_id: int):
    """Отметить, что пользователь подписался и бонус начислен."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        # Проверяем, не был ли уже начислен бонус
        cursor = await db.execute("SELECT subscription_bonus_received FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()

        if result and not result[0]:  # Если бонус еще не был получен
            await db.execute("UPDATE users SET is_subscribed = TRUE, subscription_bonus_received = TRUE WHERE user_id = ?", (user_id,))
            await db.commit()
            return True  # Возвращаем True, чтобы показать, что бонус был начислен
        else:
            return False  # Возвращаем False, если бонус уже был получен


async def create_user(user_id: int, username: str = None, referrer_id: int = None):
    """Создание нового пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("INSERT INTO users (user_id, balance, referrer_id, username) VALUES (?, ?, ?, ?)", (user_id, 0.0, referrer_id, username))
            await db.commit()

            # Обновляем статистику
            await update_bot_stats()
    except aiosqlite.Error as e:
        print(f"Ошибка при создании пользователя: {e}")



async def update_bot_stats():
    """Обновление статистики бота."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT total_paid FROM bot_stats")
            result = await cursor.fetchone()
            if result:
                total_paid = result[0]
            else:
                total_paid = 0

            await db.execute("UPDATE bot_stats SET total_users = ?, total_paid = ?", (total_users, total_paid))
            await db.commit()
    except aiosqlite.Error as e:
        print(f"Ошибка при обновлении статистики бота: {e}")
    except Exception as e:
        print(f"Непредвиденная ошибка при обновлении статистики бота: {e}")


async def update_balance(user_id: int, amount: float):
    """Обновление баланса пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def update_referral_count(user_id: int):
    """Обновление счетчика рефералов пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET referral_level1 = referral_level1 + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def update_bonus_count(user_id: int):
    """Обновление счетчика бонусов пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET bonus_count = bonus_count + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def update_is_subscribed(user_id: int, is_subscribed: bool):
    """Обновление статуса подписки пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET is_subscribed = ? WHERE user_id = ?", (is_subscribed, user_id))
        await db.commit()

async def get_is_subscribed(user_id: int):
    """Получение статуса подписки пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return bool(result[0])
            return False

async def get_referral_count(user_id: int):
    """Получение количества рефералов пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT referral_level1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return result[0]
            return 0

async def create_payeer_wallets_table():
    """Создание таблицы для хранения Payeer кошельков пользователей."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        try:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payeer_wallets (
                    user_id INTEGER PRIMARY KEY,
                    payeer_id TEXT,
                    username TEXT
                )
            """)
            await db.commit()
        except aiosqlite.OperationalError as e:
            if "duplicate column name: username" in str(e):
                print("Column username already exists in payeer_wallets")
            else:
                raise  # Перебросить исключение, если это другая ошибка



async def get_saved_payeer_id(user_id: int):
    """Получение сохраненного Payeer ID пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT payeer_id FROM payeer_wallets WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None


async def set_payeer_wallet(user_id: int, payeer_id: str):
    """Установка Payeer кошелька для пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("INSERT OR REPLACE INTO payeer_wallets (user_id, payeer_id) VALUES (?, ?)", (user_id, payeer_id))
        await db.commit()

async def get_payeer_id(user_id: int):
    """Получение номера кошелька PAYEER пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT payeer_id FROM payeer_wallets WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None


async def create_users_table():
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0.0
            )
        ''')
        await db.commit()

async def update_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        try:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
        except aiosqlite.Error as e:
            print(f"Ошибка при обновлении баланса: {e}")

async def get_user_balance(user_id: int):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return row[0]
        else:
            return None

async def add_user(user_id: int):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        try:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
        except aiosqlite.Error as e:
            print(f"Ошибка при добавлении пользователя: {e}")

# Пример использования
async def process_manual_withdraw(user_id: int, amount: float):
    await add_user(user_id)  # Добавляем пользователя, если его нет
    balance = await get_user_balance(user_id)
    if balance is not None:
        if balance >= amount:
            await update_user_balance(user_id, -amount)  # Вычитаем сумму из баланса
            print(f"Вывод средств для пользователя {user_id} успешно обработан.")
        else:
            print(f"Недостаточно средств у пользователя {user_id}.")
    else:
        print(f"Пользователь с ID {user_id} не найден.")

async def create_bot_stats():
    """Создание таблицы статистики бота."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_users INTEGER DEFAULT 0,
                    total_paid REAL DEFAULT 0.0
                )
            """)
            await db.commit()
            
            # Инициализируем запись в таблице, если она еще не создана
            async with db.execute("SELECT * FROM bot_stats") as cursor:
                if not await cursor.fetchone():
                    await db.execute("INSERT INTO bot_stats (total_users, total_paid) VALUES (0, 0.0)")
                    await db.commit()
                    
            print("Таблица статистики бота создана или уже существует.")
    except aiosqlite.Error as e:
        print(f"Ошибка при создании таблицы статистики бота: {e}")
    except Exception as e:
        print(f"Непредвиденная ошибка при создании таблицы статистики бота: {e}")


async def get_bot_stats():
    """Получение статистики бота."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute("SELECT total_users, total_paid FROM bot_stats") as cursor:
                result = await cursor.fetchone()
                if result:
                    print(f"Статистика бота: total_users={result[0]}, total_paid={result[1]}")
                    return {
                        "total_users": result[0],
                        "total_paid": result[1]
                    }
                else:
                    print("Статистика бота не найдена.")
                    return None
    except aiosqlite.Error as e:
        print(f"Ошибка при получении статистики бота: {e}")
        return None
    except Exception as e:
        print(f"Непредвиденная ошибка при получении статистики бота: {e}")
        return None


async def add_referral(user_id: int, level: int):
    """Добавление реферала пользователю."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        if level == 1:
            await db.execute("UPDATE users SET referral_level1 = referral_level1 + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def add_bonus(user_id: int, amount: float):
    """Добавление бонуса пользователю."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_bonus(user_id: int):
    """Получение текущего бонуса пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT bonus FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def reset_bonus(user_id: int):
    """Сброс бонуса пользователя после его получения."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET bonus = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

async def create_db_channel():
    """Создание базы данных и таблиц, если их нет."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL
            )
        """)
        await db.commit()

async def get_channel_id():
    """Получение ID канала/чата."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT channel_id FROM channel_settings LIMIT 1") as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def set_channel_id(channel_id: str):
    """Установка ID канала/чата."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("DELETE FROM channel_settings")  # Очищаем старые данные
        await db.execute("INSERT INTO channel_settings (channel_id) VALUES (?)", (channel_id,))
        await db.commit()

async def update_last_bonus_time(user_id: int, time: str):
    """Обновление времени последнего получения бонуса."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET last_bonus_time = ? WHERE user_id = ?", (time, user_id))
        await db.commit()

async def get_last_bonus_time(user_id: int):
    """Получение времени последнего получения бонуса."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT last_bonus_time FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def get_bonus_settings():
    """Получение настроек бонуса."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT bonus_amount, bonus_time FROM bonus_settings") as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    "bonus_amount": result[0],
                    "bonus_time": result[1]
                }
            else:
                await update_bonus_settings(1.0, 24)  # Инициализируем настройки по умолчанию
                return await get_bonus_settings()  # Повторно получаем настройки

async def update_bonus_settings(amount: float, time: int):
    """Обновление настроек бонуса."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("DELETE FROM bonus_settings")  # Очищаем старые данные
        await db.execute("INSERT INTO bonus_settings (bonus_amount, bonus_time) VALUES (?, ?)", (amount, time))
        await db.commit()

async def get_referrer_id(user_id: int):
    """Получение ID реферера."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return result[0]
            return None

async def update_subscription_bonus_received(user_id: int):
    """Обновление флага о получении бонуса за подписку."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("UPDATE users SET subscription_bonus_received = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
            print(f"Флаг бонуса за подписку обновлен для пользователя {user_id}.")
    except aiosqlite.Error as e:
        print(f"Ошибка при обновлении флага бонуса за подписку: {e}")
    except Exception as e:
        print(f"Непредвиденная ошибка при обновлении флага бонуса за подписку: {e}")

async def check_referral_bonus(referrer_id: int, user_id: int):
    """Проверка, был ли уже начислен бонус рефереру за этого реферала."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT * FROM referral_bonuses WHERE referrer_id = ? AND user_id = ?", (referrer_id, user_id)) as cursor:
            result = await cursor.fetchone()
            return bool(result)

async def mark_referral_bonus(referrer_id: int, user_id: int):
    """Отметка о том, что бонус рефереру начислен."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("INSERT INTO referral_bonuses (referrer_id, user_id) VALUES (?, ?)", (referrer_id, user_id))
        await db.commit()

async def update_bonus_count(user_id: int):
    """Обновление счетчика бонусов пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET bonus_count = bonus_count + 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def create_withdrawals_table():
    """Создание таблицы для заявок на вывод средств."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                payeer_id TEXT,
                amount REAL
            )
        """)
        await db.commit()


async def add_withdrawal(user_id: int, payeer_id: str, amount: float):
    """Добавление заявки на вывод средств."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("INSERT INTO withdrawals (user_id, payeer_id, amount) VALUES (?, ?, ?)", (user_id, payeer_id, amount))
            await db.commit()
            logger.info(f"Заявка на вывод с ID Payeer {payeer_id} на сумму {amount} руб. от пользователя {user_id} добавлена.")
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при добавлении заявки на вывод: {e}")
    except Exception as e:
        logger.exception("Произошла непредвиденная ошибка при добавлении заявки на вывод")


async def get_withdrawals():
    """Получение всех заявок на вывод средств."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute("SELECT id, user_id, payeer_id, amount FROM withdrawals") as cursor:
                result = await cursor.fetchall()
                # Преобразуем результат в список словарей
                withdrawals = []
                for row in result:
                    withdrawal = {
                        "id": row[0],
                        "user_id": row[1],
                        "payeer_id": row[2],
                        "amount": row[3]
                    }
                    withdrawals.append(withdrawal)
                return withdrawals
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при получении заявок на вывод: {e}")
        return None
    except Exception as e:
        logger.exception("Произошла непредвиденная ошибка при получении заявок на вывод")
        
async def get_withdrawals_for_admin():
    """Получение всех заявок на вывод средств для админки."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            async with db.execute("""
                SELECT user_id, SUM(amount) as total_amount
                FROM withdrawals
                GROUP BY user_id
            """) as cursor:
                result = await cursor.fetchall()
                withdrawals = []
                for row in result:
                    withdrawal = {
                        "user_id": row[0],
                        "total_amount": row[1]
                    }
                    withdrawals.append(withdrawal)
                return withdrawals
    except aiosqlite.Error as e:
        logger.error(f"Ошибка при получении заявок на вывод: {e}")
        return None
    except Exception as e:
        logger.exception("Произошла непредвиденная ошибка при получении заявок на вывод")


async def delete_withdrawal(user_id: int):
    """Удаление заявки на вывод средств по ID пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("DELETE FROM withdrawals WHERE user_id = ?", (user_id,))
        await db.commit()

async def save_payeer_id(user_id: int, payeer_id: str, username: str):
    """Сохранение Payeer ID и username пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("""
            INSERT INTO payeer_wallets (user_id, payeer_id, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET payeer_id = excluded.payeer_id, username = excluded.username
        """, (user_id, payeer_id, username))
        await db.commit()



async def save_username(user_id: int, username: str):
    """Сохранение username пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        await db.commit()


async def update_paid_amount(user_id: int, amount: float):
    """Обновление выплаченной суммы для пользователя."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET paid_amount = paid_amount + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_paid_users():
    """Получение информации о пользователях, которым были выплачены средства."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("SELECT user_id, paid_amount FROM users WHERE paid_amount > 0") as cursor:
            result = await cursor.fetchall()
            return result

async def get_new_paid_users():
    """Получение информации о новых выплатах."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with db.execute("""
            SELECT user_id, paid_amount, username 
            FROM users 
            WHERE paid_amount > 0 AND sent_notification = 0
        """) as cursor:
            result = await cursor.fetchall()
            return result



async def mark_notification_sent(user_id: int):
    """Отметка о том, что уведомление было отправлено."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET sent_notification = 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def save_user_info(user_id: int, username: str):
    """Сохранение информации о пользователе."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        await db.commit()

async def update_withdrawal_status(user_id: int, is_paid: bool):
    """Обновление статуса заявки."""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute("UPDATE withdrawals SET is_paid = ? WHERE user_id = ?", (int(is_paid), user_id))
        await db.commit()
