import os
import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand,
    MenuButtonCommands,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не указан")


ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}


DB = "orders.db"


STATUSES = {
    "ordered": "📝 Заказ оформлен",
    "warehouse": "📦 На складе",
    "preparing": "📤 Готовится к отправке",
    "transit": "🚚 Едет к вам",
    "city": "🏙 В вашем городе",
    "courier": "🛵 Передан курьеру",
    "delivered": "✅ Доставлен",
}


# Хранит временное действие администратора
admin_actions = {}


# =========================
# DATABASE
# =========================

def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'ordered',
            details TEXT DEFAULT 'Информация о заказе пока не добавлена.',
            photo_id TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def get_order(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, username, status, details, photo_id
        FROM orders
        WHERE user_id = ?
        """,
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    return result


def create_order(user_id, username):
    if get_order(user_id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO orders
        (user_id, username, status, details, photo_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            username or "",
            "ordered",
            "Информация о заказе пока не добавлена.",
            None,
        ),
    )

    conn.commit()
    conn.close()


def update_status(user_id, status):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE orders
        SET status = ?
        WHERE user_id = ?
        """,
        (status, user_id),
    )

    conn.commit()
    conn.close()


def update_details(user_id, details):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE orders
        SET details = ?
        WHERE user_id = ?
        """,
        (details, user_id),
    )

    conn.commit()
    conn.close()


def update_photo(user_id, photo_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE orders
        SET photo_id = ?
        WHERE user_id = ?
        """,
        (photo_id, user_id),
    )

    conn.commit()
    conn.close()


def get_all_orders():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, username, status
        FROM orders
        ORDER BY user_id
        """
    )

    result = cur.fetchall()

    conn.close()

    return result


# =========================
# KEYBOARDS
# =========================

def main_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="📦 Мой заказ",
        callback_data="my_order",
    )

    builder.adjust(1)

    return builder.as_markup()


def admin_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="👥 Клиенты",
        callback_data="admin_clients",
    )

    builder.adjust(1)

    return builder.as_markup()


def client_menu(user_id):
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🚚 Изменить статус",
        callback_data=f"change_status:{user_id}",
    )

    builder.button(
        text="📝 Изменить заказ",
        callback_data=f"edit_order:{user_id}",
    )

    builder.adjust(1)

    return builder.as_markup()


def status_menu(user_id):
    builder = InlineKeyboardBuilder()

    for key, name in STATUSES.items():
        builder.button(
            text=name,
            callback_data=f"status:{user_id}:{key}",
        )

    builder.adjust(1)

    return builder.as_markup()


def edit_menu(user_id):
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🛍 Изменить детали",
        callback_data=f"edit_details:{user_id}",
    )

    builder.button(
        text="📸 Добавить/изменить фото",
        callback_data=f"edit_photo:{user_id}",
    )

    builder.adjust(1)

    return builder.as_markup()


# =========================
# ORDER FORMAT
# =========================

def format_order(order):
    user_id, username, status, details, photo_id = order

    text = (
        "📦 <b>Мой заказ</b>\n\n"
        f"Статус: <b>{STATUSES.get(status, status)}</b>\n\n"
        f"🛍 <b>Детали заказа:</b>\n{details}"
    )

    return text, photo_id


# =========================
# MAIN
# =========================

async def main():

    init_db()

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode="HTML"
        ),
    )

    dp = Dispatcher()

    # =========================
    # START
    # =========================

    @dp.message(CommandStart())
    async def start(message: Message):

        create_order(
            message.from_user.id,
            message.from_user.username,
        )

        await message.answer(
            "👋 <b>Добро пожаловать в BSHOP!</b>\n\n"
            "Здесь ты можешь отслеживать свой заказ.",
            reply_markup=main_menu(),
        )

    # =========================
    # MY ID
    # =========================

    @dp.message(Command("id"))
    async def get_id_command(message: Message):

        await message.answer(
            "🆔 Твой Telegram ID:\n\n"
            f"<code>{message.from_user.id}</code>"
        )

    # =========================
    # MY ORDER COMMAND
    # =========================

    @dp.message(Command("order"))
    async def order_command(message: Message):

        create_order(
            message.from_user.id,
            message.from_user.username,
        )

        order = get_order(
            message.from_user.id
        )

        text, photo_id = format_order(order)

        if photo_id:

            await message.answer_photo(
                photo=photo_id,
                caption=text,
            )

        else:

            await message.answer(
                text
            )

    # =========================
    # ADMIN
    # =========================

    @dp.message(Command("admin"))
    async def admin(message: Message):

        if message.from_user.id not in ADMIN_IDS:

            await message.answer(
                "⛔ Доступ запрещён."
            )

            return

        await message.answer(
            "⚙️ <b>Панель администратора</b>",
            reply_markup=admin_menu(),
        )

    # =========================
    # CLIENT: MY ORDER BUTTON
    # =========================

    @dp.callback_query(F.data == "my_order")
    async def my_order(callback: CallbackQuery):

        create_order(
            callback.from_user.id,
            callback.from_user.username,
        )

        order = get_order(
            callback.from_user.id
        )

        text, photo_id = format_order(order)

        if photo_id:

            await callback.message.answer_photo(
                photo=photo_id,
                caption=text,
            )

        else:

            await callback.message.answer(
                text
            )

        await callback.answer()

    # =========================
    # ADMIN: CLIENTS
    # =========================

    @dp.callback_query(F.data == "admin_clients")
    async def admin_clients(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        orders = get_all_orders()

        if not orders:

            await callback.message.answer(
                "Пока клиентов нет."
            )

            await callback.answer()

            return

        builder = InlineKeyboardBuilder()

        for user_id, username, status in orders:

            name = (
                f"@{username}"
                if username
                else str(user_id)
            )

            builder.button(
                text=(
                    f"{name} — "
                    f"{STATUSES.get(status, status)}"
                ),
                callback_data=f"client:{user_id}",
            )

        builder.adjust(1)

        await callback.message.answer(
            "👥 <b>Клиенты:</b>",
            reply_markup=builder.as_markup(),
        )

        await callback.answer()

    # =========================
    # ADMIN: CLIENT
    # =========================

    @dp.callback_query(F.data.startswith("client:"))
    async def admin_client(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        user_id = int(
            callback.data.split(":")[1]
        )

        order = get_order(user_id)

        if not order:

            await callback.answer(
                "Заказ не найден",
                show_alert=True,
            )

            return

        text, _ = format_order(order)

        await callback.message.answer(
            f"👤 <b>Клиент:</b> "
            f"<code>{user_id}</code>\n\n"
            f"{text}",
            reply_markup=client_menu(user_id),
        )

        await callback.answer()

    # =========================
    # ADMIN: CHANGE STATUS MENU
    # =========================

    @dp.callback_query(F.data.startswith("change_status:"))
    async def change_status_menu(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        user_id = int(
            callback.data.split(":")[1]
        )

        await callback.message.answer(
            "🚚 <b>Выбери новый статус:</b>",
            reply_markup=status_menu(user_id),
        )

        await callback.answer()

    # =========================
    # ADMIN: CHANGE STATUS
    # =========================

    @dp.callback_query(F.data.startswith("status:"))
    async def change_status(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        parts = callback.data.split(":")

        user_id = int(parts[1])
        status = parts[2]

        if status not in STATUSES:

            await callback.answer(
                "Неизвестный статус",
                show_alert=True,
            )

            return

        update_status(
            user_id,
            status
        )

        await callback.answer(
            "Статус изменён ✅",
            show_alert=True,
        )

        # Уведомляем клиента
        try:

            await bot.send_message(
                user_id,
                "📦 <b>Статус заказа обновлён!</b>\n\n"
                "Новый статус:\n"
                f"<b>{STATUSES[status]}</b>",
            )

        except Exception:
            pass

        await callback.message.answer(
            "✅ <b>Статус изменён</b>\n\n"
            f"{STATUSES[status]}"
        )

    # =========================
    # ADMIN: EDIT ORDER
    # =========================

    @dp.callback_query(F.data.startswith("edit_order:"))
    async def edit_order(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        user_id = int(
            callback.data.split(":")[1]
        )

        await callback.message.answer(
            "📝 <b>Редактирование заказа</b>\n\n"
            "Выбери, что хочешь изменить:",
            reply_markup=edit_menu(user_id),
        )

        await callback.answer()

    # =========================
    # ADMIN: EDIT DETAILS
    # =========================

    @dp.callback_query(F.data.startswith("edit_details:"))
    async def edit_details(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        user_id = int(
            callback.data.split(":")[1]
        )

        admin_actions[
            callback.from_user.id
        ] = {
            "action": "details",
            "user_id": user_id,
        }

        await callback.message.answer(
            "📝 <b>Отправь информацию о заказе</b>\n\n"
            "Например:\n\n"
            "👕 Футболка — 1 шт.\n"
            "👖 Джогеры — 1 шт.\n"
            "💰 Сумма: 4 500 ₽"
        )

        await callback.answer()

    # =========================
    # ADMIN: EDIT PHOTO
    # =========================

    @dp.callback_query(F.data.startswith("edit_photo:"))
    async def edit_photo(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:

            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )

            return

        user_id = int(
            callback.data.split(":")[1]
        )

        admin_actions[
            callback.from_user.id
        ] = {
            "action": "photo",
            "user_id": user_id,
        }

        await callback.message.answer(
            "📸 <b>Отправь фотографию заказа.</b>"
        )

        await callback.answer()

    # =========================
    # ADMIN: TEXT
    # =========================

    @dp.message(F.text)
    async def admin_text(message: Message):

        if message.from_user.id not in ADMIN_IDS:
            return

        action = admin_actions.get(
            message.from_user.id
        )

        if not action:
            return

        if action["action"] != "details":
            return

        user_id = action["user_id"]

        update_details(
            user_id,
            message.text,
        )

        del admin_actions[
            message.from_user.id
        ]

        await message.answer(
            "✅ <b>Детали заказа сохранены!</b>\n\n"
            f"{message.text}"
        )

    # =========================
    # ADMIN: PHOTO
    # =========================

    @dp.message(F.photo)
    async def admin_photo(message: Message):

        if message.from_user.id not in ADMIN_IDS:
            return

        action = admin_actions.get(
            message.from_user.id
        )

        if not action:
            return

        if action["action"] != "photo":
            return

        user_id = action["user_id"]

        photo_id = message.photo[-1].file_id

        update_photo(
            user_id,
            photo_id,
        )

        del admin_actions[
            message.from_user.id
        ]

        await message.answer(
            "✅ <b>Фото заказа сохранено!</b>"
        )

    # =========================
    # TELEGRAM MENU
    # =========================

    await bot.set_my_commands(
        [
            BotCommand(
                command="order",
                description="📦 Мой заказ",
            ),
            BotCommand(
                command="id",
                description="🆔 Мой ID",
            ),
            BotCommand(
                command="admin",
                description="⚙️ Админ-панель",
            ),
        ]
    )

    await bot.set_chat_menu_button(
        menu_button=MenuButtonCommands(
            type="commands"
        )
    )

    print("BSHOP BOT STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

def db():
    return sqlite3.connect(DB)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'ordered',
            details TEXT DEFAULT 'Информация о заказе пока не добавлена.',
            photo_id TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def get_order(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, username, status, details, photo_id
        FROM orders
        WHERE user_id = ?
        """,
        (user_id,),
    )

    result = cur.fetchone()

    conn.close()

    return result


def create_order(user_id, username):
    if get_order(user_id):
        return

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO orders
        (user_id, username, status, details, photo_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            username or "",
            "ordered",
            "Информация о заказе пока не добавлена.",
            None,
        ),
    )

    conn.commit()
    conn.close()


def update_status(user_id, status):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE orders
        SET status = ?
        WHERE user_id = ?
        """,
        (status, user_id),
    )

    conn.commit()
    conn.close()


def get_all_orders():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, username, status
        FROM orders
        ORDER BY user_id
        """
    )

    result = cur.fetchall()

    conn.close()

    return result


def main_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="📦 Мой заказ",
        callback_data="my_order",
    )

    builder.adjust(1)

    return builder.as_markup()


def admin_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="👥 Клиенты",
        callback_data="admin_clients",
    )

    builder.adjust(1)

    return builder.as_markup()


def status_menu(user_id):
    builder = InlineKeyboardBuilder()

    for key, name in STATUSES.items():
        builder.button(
            text=name,
            callback_data=f"status:{user_id}:{key}",
        )

    builder.adjust(1)

    return builder.as_markup()


def format_order(order):
    user_id, username, status, details, photo_id = order

    text = (
        "📦 <b>Мой заказ</b>\n\n"
        f"Статус: <b>{STATUSES.get(status, status)}</b>\n\n"
        f"🛍 <b>Детали:</b>\n{details}"
    )

    return text, photo_id


async def main():
    init_db()

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode="HTML"
        ),
    )

    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message):
        create_order(
            message.from_user.id,
            message.from_user.username,
        )

        await message.answer(
            "👋 <b>Добро пожаловать в BSHOP!</b>\n\n"
            "Здесь ты можешь отслеживать свой заказ.",
            reply_markup=main_menu(),
        )

    @dp.message(Command("id"))
    async def get_id(message: Message):
        await message.answer(
            f"Твой Telegram ID:\n"
            f"<code>{message.from_user.id}</code>"
        )

    @dp.message(Command("admin"))
    async def admin(message: Message):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("⛔ Доступ запрещён.")
            return

        await message.answer(
            "⚙️ <b>Панель администратора</b>",
            reply_markup=admin_menu(),
        )

    @dp.callback_query(F.data == "my_order")
    async def my_order(callback: CallbackQuery):
        create_order(
            callback.from_user.id,
            callback.from_user.username,
        )

        order = get_order(callback.from_user.id)

        text, photo_id = format_order(order)

        if photo_id:
            await callback.message.answer_photo(
                photo=photo_id,
                caption=text,
            )
        else:
            await callback.message.answer(text)

        await callback.answer()

    @dp.callback_query(F.data == "admin_clients")
    async def admin_clients(callback: CallbackQuery):
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return

        orders = get_all_orders()

        if not orders:
            await callback.message.answer(
                "Пока клиентов нет."
            )
            await callback.answer()
            return

        builder = InlineKeyboardBuilder()

        for user_id, username, status in orders:
            name = (
                f"@{username}"
                if username
                else str(user_id)
            )

            builder.button(
                text=(
                    f"{name} — "
                    f"{STATUSES.get(status, status)}"
                ),
                callback_data=f"client:{user_id}",
            )

        builder.adjust(1)

        await callback.message.answer(
            "👥 <b>Клиенты:</b>",
            reply_markup=builder.as_markup(),
        )

        await callback.answer()

    @dp.callback_query(F.data.startswith("client:"))
    async def admin_client(callback: CallbackQuery):
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return

        user_id = int(
            callback.data.split(":")[1]
        )

        order = get_order(user_id)

        if not order:
            await callback.answer(
                "Заказ не найден",
                show_alert=True,
            )
            return

        text, _ = format_order(order)

        await callback.message.answer(
            f"👤 <b>Клиент:</b> "
            f"<code>{user_id}</code>\n\n"
            f"{text}\n\n"
            "Выбери новый статус:",
            reply_markup=status_menu(user_id),
        )

        await callback.answer()

    @dp.callback_query(F.data.startswith("status:"))
    async def change_status(callback: CallbackQuery):
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return

        parts = callback.data.split(":")

        user_id = int(parts[1])
        status = parts[2]

        if status not in STATUSES:
            await callback.answer(
                "Неизвестный статус",
                show_alert=True,
            )
            return

        update_status(user_id, status)

        await callback.answer(
            "Статус изменён ✅",
            show_alert=True,
        )

        try:
            await bot.send_message(
                user_id,
                "📦 <b>Статус заказа обновлён!</b>\n\n"
                f"Новый статус:\n"
                f"<b>{STATUSES[status]}</b>",
            )
        except Exception:
            pass

        await callback.message.answer(
            "✅ <b>Статус изменён</b>\n\n"
            f"{STATUSES[status]}"
        )

    print("BSHOP BOT STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
