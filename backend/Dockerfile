FROM python:3.11-slim

# Установка системных зависимостей для Pillow и qrcode
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libopenjp2-7-dev \
    libimagequant-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование requirements.txt первым (для кэширования слоя Docker)
COPY backend/requirements.txt .

# Установка Python зависимостей
# Сначала устанавливаем Pillow (требует системные библиотеки, которые уже установлены)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir Pillow==10.1.0 && \
    pip install --no-cache-dir qrcode==7.4.2

# Установка остальных зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Проверка установки qrcode (отдельным шагом для лучшей диагностики)
RUN python -c "import qrcode; from PIL import Image; print('✅ QR code dependencies OK')" || (echo "❌ QR code dependencies NOT installed" && pip list | grep -E "(qrcode|Pillow)" && exit 1)

# Копирование картинки приветствия
# Создаём директорию и копируем файл (пробелы в пути требуют специального синтаксиса)
RUN mkdir -p "/app/BEST logos"
COPY ["BEST logos/best_welcome.jpg", "/app/BEST logos/best_welcome.jpg"]

# Копирование остальных файлов бэкенда
COPY backend/ .

# Команда запуска (миграции выполняются в run_with_bot.py при запуске)
# Используем абсолютный путь для надежности
CMD ["python", "/app/run_with_bot.py"]
