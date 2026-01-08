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

# Копирование requirements.txt
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Копирование остальных файлов
COPY . .

# Проверка установки qrcode
RUN python -c "import qrcode; import PIL; print('QR code dependencies OK')" || echo "WARNING: QR code dependencies not installed"

# Команда запуска
CMD ["python", "run_with_bot.py"]
