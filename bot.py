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


# =========================
# СТАТУСЫ ЗАКАЗА
# =========================

STATUSES = {
    "registered": "👋 Клиент зарегистрирован",
    "ordered": "📝 Заказ оформлен",
    "warehouse": "📦 На складе",
    "preparing": "📤 Готовится к отправке",
    "transit": "🚚 Едет к вам",
    "city": "🏙 В вашем городе",
    "courier": "🛵 Передан курьеру",
    "delivered": "✅ Доставлен",
}


# =========================
# СТАТУСЫ ВОЗВРАТА
# =========================

RETURN_STATUSES = {
    "new": "🆕 Новая заявка",
    "review": "🔎 На рассмотрении",
    "approved": "✅ Возврат одобрен",
    "rejected": "❌ Возврат отклонён",
}


admin_actions = {}
return_requests = {}


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
            status TEXT DEFAULT 'registered',
            details TEXT DEFAULT 'Заказ пока не оформлен.',
            photo_id TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            reason TEXT,
            photos TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


# =========================
# ORDERS
# =========================

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
            "registered",
            "Заказ пока не оформлен.",
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
# RETURNS
# =========================

def create_return(user_id, username, reason, photos):
    conn = db()
    cur = conn.cursor()

    photos_text = ",".join(photos)

    cur.execute(
        """
        INSERT INTO returns
        (user_id, username, reason, photos, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            username or "",
            reason,
            photos_text,
            "new",
        ),
    )

    return_id = cur.lastrowid

    conn.commit()
    conn.close()

    return return_id


def get_returns():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, username, reason, photos, status, created_at
        FROM returns
        ORDER BY id DESC
        """
    )

    result = cur.fetchall()

    conn.close()

    return result


def get_return(return_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, username, reason, photos, status, created_at
        FROM returns
        WHERE id = ?
        """,
        (return_id,),
    )

    result = cur.fetchone()

    conn.close()

    return result


def update_return_status(return_id, status):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE returns
        SET status = ?
        WHERE id = ?
        """,
        (status, return_id),
    )

    conn.commit()
    conn.close()


# =========================
# CLIENT MENU
# =========================

def main_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="📦 Мой заказ",
        callback_data="my_order",
    )

    builder.button(
        text="↩️ Возврат / обмен",
        callback_data="return_start",
    )

    builder.adjust(1)

    return builder.as_markup()


# =========================
# ADMIN MENU
# =========================

def admin_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="👥 Клиенты",
        callback_data="admin_clients",
    )

    builder.button(
        text="↩️ Заявки на возврат",
        callback_data="admin_returns",
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


def return_status_menu(return_id):
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🔎 На рассмотрении",
        callback_data=f"return_status:{return_id}:review",
    )

    builder.button(
        text="✅ Одобрить",
        callback_data=f"return_status:{return_id}:approved",
    )

    builder.button(
        text="❌ Отклонить",
        callback_data=f"return_status:{return_id}:rejected",
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
        f"🛍 <b>Детали:</b>\n{details}"
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
            "Здесь ты можешь отслеживать свой заказ.\n\n"
            "📌 <b>Заказ пока не оформлен.</b>\n"
            "Если ты хочешь оформить заказ, свяжись с нами.",
            reply_markup=main_menu(),
        )

    # =========================
    # ID
    # =========================

    @dp.message(Command("id"))
    async def get_id_command(message: Message):

        await message.answer(
            "🆔 Твой Telegram ID:\n\n"
            f"<code>{message.from_user.id}</code>"
        )

    # =========================
    # ORDER COMMAND
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
            await message.answer(text)

    # =========================
    # RETURN COMMAND
    # =========================

    @dp.message(Command("return"))
    async def return_command(message: Message):

        return_requests[
            message.from_user.id
        ] = {
            "photos": []
        }

        await message.answer(
            "↩️ <b>Заявка на возврат / обмен</b>\n\n"
            "Возврат возможен в течение <b>7 дней</b> "
            "с момента получения заказа.\n\n"
            "<b>Условия возврата:</b>\n"
            "• вещь не должна быть ношена;\n"
            "• вещь не должна иметь следов стирки или использования;\n"
            "• желательно сохранить бирки и упаковку;\n"
            "• при обнаружении брака обязательно приложите "
            "фотографии дефекта.\n\n"
            "Напиши <b>причину возврата или обмена</b> "
            "одним сообщением."
        )

    # =========================
    # ADMIN COMMAND
    # =========================

    @dp.message(Command("admin"))
    async def admin(message: Message):

        if message.from_user.id not in ADMIN_IDS:
            await message.answer("⛔ Доступ запрещён.")
            return

        await message.answer(
            "⚙️ <b>Панель администратора</b>",
            reply_markup=admin_menu(),
        )

    # =========================
    # MY ORDER
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
            await callback.message.answer(text)

        await callback.answer()

    # =========================
    # RETURN BUTTON
    # =========================

    @dp.callback_query(F.data == "return_start")
    async def return_start(callback: CallbackQuery):

        return_requests[
            callback.from_user.id
        ] = {
            "photos": []
        }

        await callback.message.answer(
            "↩️ <b>Заявка на возврат / обмен</b>\n\n"
            "Возврат возможен в течение <b>7 дней</b> "
            "с момента получения заказа.\n\n"
            "<b>Условия возврата:</b>\n"
            "• вещь не должна быть ношена;\n"
            "• вещь не должна иметь следов стирки или использования;\n"
            "• желательно сохранить бирки и упаковку;\n"
            "• при обнаружении брака обязательно приложите "
            "фотографии дефекта.\n\n"
            "Напиши <b>причину возврата или обмена</b> "
            "одним сообщением."
        )

        await callback.answer()

    # =========================
    # RETURN REASON
    # =========================

    @dp.message(
        F.text,
        lambda message:
        message.from_user.id in return_requests
        and "reason" not in return_requests[
            message.from_user.id
        ]
    )
    async def return_reason(message: Message):

        data = return_requests.get(
            message.from_user.id
        )

        if not data:
            return

        data["reason"] = message.text

        await message.answer(
            "📸 <b>Теперь отправь фотографии товара.</b>\n\n"
            "Если есть дефект, обязательно сфотографируй "
            "его крупным планом.\n\n"
            "Можно отправить до <b>5 фотографий</b>.\n\n"
            "Когда закончишь, отправь <b>/done</b>."
        )

    # =========================
    # RETURN PHOTO
    # =========================

    @dp.message(
        F.photo,
        lambda message:
        message.from_user.id in return_requests
    )
    async def return_photo(message: Message):

        data = return_requests.get(
            message.from_user.id
        )

        if not data:
            return

        if "reason" not in data:

            await message.answer(
                "Сначала напиши причину возврата."
            )

            return

        photos = data["photos"]

        if len(photos) >= 5:

            await message.answer(
                "Можно прикрепить максимум 5 фотографий."
            )

            return

        photos.append(
            message.photo[-1].file_id
        )

        await message.answer(
            f"📸 Фото добавлено: {len(photos)}/5\n\n"
            "Можешь отправить ещё фото или написать /done."
        )

    # =========================
    # RETURN DONE
    # =========================

    @dp.message(
        Command("done"),
        lambda message:
        message.from_user.id in return_requests
    )
    async def return_done(message: Message):

        data = return_requests.get(
            message.from_user.id
        )

        if not data:
            return

        if "reason" not in data:

            await message.answer(
                "Сначала напиши причину возврата."
            )

            return

        reason = data["reason"]
        photos = data["photos"]

        return_id = create_return(
            message.from_user.id,
            message.from_user.username,
            reason,
            photos,
        )

        del return_requests[
            message.from_user.id
        ]

        await message.answer(
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"Номер заявки: <b>#{return_id}</b>\n\n"
            "Мы рассмотрим заявку и сообщим решение."
        )

        for admin_id in ADMIN_IDS:

            try:

                await bot.send_message(
                    admin_id,
                    "↩️ <b>Новая заявка на возврат!</b>\n\n"
                    f"Заявка: <b>#{return_id}</b>\n"
                    f"Клиент: <code>{message.from_user.id}</code>\n"
                    f"Причина: {reason}\n"
                    f"Фотографий: {len(photos)}",
                    reply_markup=return_status_menu(return_id),
                )

                for photo_id in photos:

                    await bot.send_photo(
                        admin_id,
                        photo=photo_id,
                    )

            except Exception:
                pass

    # =========================
    # ADMIN CLIENTS
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
    # ADMIN CLIENT
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
    # CHANGE STATUS MENU
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
    # CHANGE STATUS
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

    # =========================
    # EDIT ORDER
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
    # EDIT DETAILS
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
    # EDIT PHOTO
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
    # ADMIN TEXT
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
    # ADMIN PHOTO
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
    # ADMIN RETURNS
    # =========================

    @dp.callback_query(F.data == "admin_returns")
    async def admin_returns(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return

        returns = get_returns()

        if not returns:

            await callback.message.answer(
                "↩️ Заявок на возврат пока нет."
            )

            await callback.answer()
            return

        builder = InlineKeyboardBuilder()

        for (
            return_id,
            user_id,
            username,
            reason,
            photos,
            status,
            created_at,
        ) in returns:

            builder.button(
                text=(
                    f"#{return_id} — "
                    f"{RETURN_STATUSES.get(status, status)}"
                ),
                callback_data=f"return_view:{return_id}",
            )

        builder.adjust(1)

        await callback.message.answer(
            "↩️ <b>Заявки на возврат:</b>",
            reply_markup=builder.as_markup(),
        )

        await callback.answer()

    # =========================
    # VIEW RETURN
    # =========================

    @dp.callback_query(F.data.startswith("return_view:"))
    async def return_view(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return

        return_id = int(
            callback.data.split(":")[1]
        )

        request = get_return(return_id)

        if not request:

            await callback.answer(
                "Заявка не найдена",
                show_alert=True,
            )
            return

        (
            rid,
            user_id,
            username,
            reason,
            photos,
            status,
            created_at,
        ) = request

        photo_list = (
            photos.split(",")
            if photos
            else []
        )

        text = (
            f"↩️ <b>Заявка #{rid}</b>\n\n"
            f"👤 Клиент: <code>{user_id}</code>\n"
            f"Статус: <b>{RETURN_STATUSES.get(status, status)}</b>\n\n"
            f"📝 <b>Причина:</b>\n"
            f"{reason}\n\n"
            f"📸 Фотографий: {len(photo_list)}\n"
            f"🕐 Создана: {created_at}"
        )

        await callback.message.answer(
            text,
            reply_markup=return_status_menu(return_id),
        )

        for photo_id in photo_list:

            if photo_id:

                try:
                    await callback.message.answer_photo(
                        photo=photo_id
                    )
                except Exception:
                    pass

        await callback.answer()

    # =========================
    # RETURN STATUS
    # =========================

    @dp.callback_query(F.data.startswith("return_status:"))
    async def change_return_status(callback: CallbackQuery):

        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer(
                "⛔ Нет доступа",
                show_alert=True,
            )
            return

        parts = callback.data.split(":")

        return_id = int(parts[1])
        status = parts[2]

        if status not in RETURN_STATUSES:

            await callback.answer(
                "Неизвестный статус",
                show_alert=True,
            )
            return

        request = get_return(return_id)

        if not request:

            await callback.answer(
                "Заявка не найдена",
                show_alert=True,
            )
            return

        update_return_status(
            return_id,
            status
        )

        user_id = request[1]

        await callback.answer(
            "Статус заявки изменён ✅",
            show_alert=True,
        )

        try:

            await bot.send_message(
                user_id,
                "↩️ <b>Обновление по заявке на возврат</b>\n\n"
                f"Заявка: <b>#{return_id}</b>\n"
                f"Статус: <b>{RETURN_STATUSES[status]}</b>",
            )

        except Exception:
            pass

        await callback.message.answer(
            "✅ <b>Статус заявки изменён</b>\n\n"
            f"{RETURN_STATUSES[status]}"
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
                command="return",
                description="↩️ Возврат / обмен",
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
