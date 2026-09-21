```python
import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message


TOKEN = os.getenv("8934853359:AAFKMtizHzt25fr9DKg7F-MqB_xC8T4sYsc

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не указан")


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message):
        await message.answer(
            "👋 Добро пожаловать в BSHOP!\n\n"
            "Бот работает ✅"
        )

    print("BSHOP BOT STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```
