#!/bin/bash
# Скрипт для проверки TypeScript ошибок перед коммитом

echo "🔍 Проверка TypeScript ошибок..."

cd "$(dirname "$0")"

# Проверяем TypeScript
npm run build 2>&1 | grep -E "error TS|ERROR" | head -20

if [ $? -eq 0 ]; then
    echo "❌ Найдены TypeScript ошибки! Исправьте их перед коммитом."
    exit 1
else
    echo "✅ TypeScript ошибок не найдено!"
    exit 0
fi
