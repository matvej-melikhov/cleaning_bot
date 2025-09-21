FROM python:3.9-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . .

# Инициализация базы данных и запуск бота
CMD ["sh", "-c", "python init_schedule.py && python main.py"]
