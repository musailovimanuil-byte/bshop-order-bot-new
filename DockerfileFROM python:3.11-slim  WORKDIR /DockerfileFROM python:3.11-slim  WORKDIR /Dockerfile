FROM python:3.11-slim

WORKDIR /app

COPY bot.py .

RUN pip install --no-cache-dir aiogram

CMD ["python", "bot.py"]
