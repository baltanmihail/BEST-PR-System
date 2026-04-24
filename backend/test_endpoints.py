"""
Скрипт для быстрого тестирования API endpoints
"""
import httpx
import asyncio
from datetime import datetime, timedelta

API_URL = "https://best-pr-system.ru/api/v1"

async def test_basic_endpoints():
    """Тестирование базовых endpoints"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("🧪 Тестирование базовых endpoints")
        print("=" * 60)
        
        # 1. Health check
        print("\n1️⃣  Health check...")
        try:
            response = await client.get(f"{API_URL.replace('/api/v1', '')}/health")
            print(f"   ✅ Status: {response.status_code}")
            print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 2. Test endpoint
        print("\n2️⃣  Test endpoint...")
        try:
            response = await client.get(f"{API_URL.replace('/api/v1', '')}/test")
            print(f"   ✅ Status: {response.status_code}")
            print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 3. Root endpoint
        print("\n3️⃣  Root endpoint...")
        try:
            response = await client.get(f"{API_URL.replace('/api/v1', '')}/")
            print(f"   ✅ Status: {response.status_code}")
            print(f"   📄 Response: {response.json()}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def test_auth():
    """Тестирование авторизации"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "=" * 60)
        print("🔐 Тестирование авторизации")
        print("=" * 60)
        
        # Тестовые данные для авторизации
        auth_data = {
            "id": 5079636941,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "auth_date": int(datetime.now().timestamp()),
            "hash": "test_hash"  # В production нужен реальный hash
        }
        
        print("\n1️⃣  Авторизация через Telegram...")
        try:
            response = await client.post(f"{API_URL}/auth/telegram", json=auth_data)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успешно! Токен получен: {data.get('access_token', 'N/A')[:20]}...")
                return data.get('access_token')
            else:
                print(f"   ⚠️  Response: {response.text}")
                return None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None


async def test_calendar(token: str = None):
    """Тестирование календаря"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "=" * 60)
        print("📅 Тестирование календаря")
        print("=" * 60)
        
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        # Месячный вид
        print("\n1️⃣  Календарь (месячный вид)...")
        try:
            response = await client.get(
                f"{API_URL}/calendar",
                params={"view": "month", "start_date": "2026-01-01"},
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успешно!")
                print(f"   📊 Месяц: {data.get('month')}, Год: {data.get('year')}")
                print(f"   📅 Дней: {len(data.get('days', []))}")
                print(f"   🎉 Мероприятий: {len(data.get('events', []))}")
            else:
                print(f"   ⚠️  Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Недельный вид
        print("\n2️⃣  Календарь (недельный вид)...")
        try:
            response = await client.get(
                f"{API_URL}/calendar",
                params={"view": "week", "start_date": "2026-01-15"},
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успешно!")
                print(f"   📅 Неделя с {data.get('start_date')} по {data.get('end_date')}")
                print(f"   📊 Дней: {len(data.get('days', []))}")
            else:
                print(f"   ⚠️  Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Таймлайн
        print("\n3️⃣  Календарь (таймлайн)...")
        try:
            response = await client.get(
                f"{API_URL}/calendar",
                params={
                    "view": "timeline",
                    "start_date": "2026-01-01",
                    "end_date": "2026-07-01"
                },
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успешно!")
                print(f"   📅 Период: {data.get('start_date')} - {data.get('end_date')}")
                print(f"   📊 Элементов: {len(data.get('items', []))}")
            else:
                print(f"   ⚠️  Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def test_tasks(token: str = None):
    """Тестирование задач"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "=" * 60)
        print("📋 Тестирование задач")
        print("=" * 60)
        
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        # Получение списка задач
        print("\n1️⃣  Получение списка задач...")
        try:
            response = await client.get(f"{API_URL}/tasks", headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успешно!")
                print(f"   📊 Всего задач: {data.get('total', 0)}")
                print(f"   📋 В списке: {len(data.get('items', []))}")
            else:
                print(f"   ⚠️  Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def main():
    """Главная функция тестирования"""
    print("🚀 Начинаем тестирование API...")
    print(f"📍 API URL: {API_URL}\n")
    
    # Тестируем базовые endpoints
    await test_basic_endpoints()
    
    # Тестируем авторизацию (может не сработать без реального hash)
    token = await test_auth()
    
    # Тестируем календарь (может работать без токена для некоторых endpoints)
    await test_calendar(token)
    
    # Тестируем задачи (требует токен)
    if token:
        await test_tasks(token)
    else:
        print("\n⚠️  Пропускаем тесты задач (нужна авторизация)")
    
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
    print("=" * 60)
    print("\n💡 Совет: Откройте Swagger UI для интерактивного тестирования:")
    print(f"   https://best-pr-system.ru/docs")


if __name__ == "__main__":
    asyncio.run(main())
