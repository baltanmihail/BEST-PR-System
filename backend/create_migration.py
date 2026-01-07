"""
Скрипт для создания начальной миграции Alembic
"""
import os
import sys
import subprocess
from pathlib import Path

# Получаем путь к backend
backend_path = Path(__file__).parent.resolve()
os.chdir(backend_path)

print("🔧 Создаю начальную миграцию...")
print(f"📁 Рабочая директория: {backend_path}")
print()

# Проверяем наличие alembic
try:
    import alembic
    print("✅ Alembic установлен")
except ImportError:
    print("❌ Alembic не установлен!")
    print("\n📦 Установите зависимости:")
    print("   pip install -r requirements.txt")
    sys.exit(1)

# Создаём миграцию через subprocess (более надёжный способ)
try:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", "Initial migration: create all tables"],
        cwd=str(backend_path),
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode == 0:
        print("✅ Миграция создана успешно!")
        print()
        print("📝 Вывод команды:")
        print(result.stdout)
        if result.stderr:
            print("⚠️ Предупреждения:")
            print(result.stderr)
        print("\n📝 Теперь выполните миграцию:")
        print(f"   cd {backend_path}")
        print("   python -m alembic upgrade head")
    else:
        print("❌ Ошибка при создании миграции:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
