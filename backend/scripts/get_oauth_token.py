"""
Скрипт для получения OAuth refresh_token для Google Drive.
Запустите один раз локально, чтобы получить токен.

Запуск: python scripts/get_oauth_token.py
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth credentials - ЗАМЕНИ НА СВОИ из Google Cloud Console
# https://console.cloud.google.com/apis/credentials
CLIENT_ID = "YOUR_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"

# Scopes для Google Drive и Sheets
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/documents'
]

def main():
    print("=" * 60)
    print("🔐 Получение OAuth токена для Google Drive")
    print("=" * 60)
    print()
    print("📋 После запуска откроется браузер.")
    print("   Войдите аккаунтом: mikhail.baltyan@bmstu-best.ru")
    print("   (или другим, который хотите использовать)")
    print()
    print("⚠️  Если появится предупреждение 'Google hasn't verified this app',")
    print("   нажмите 'Advanced' → 'Go to BEST PR System OAuth (unsafe)'")
    print()
    input("Нажмите Enter для продолжения...")
    
    # Создаём client config
    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }
    
    # Запускаем OAuth flow
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    # Открываем браузер для авторизации
    credentials = flow.run_local_server(port=8888)
    
    print()
    print("=" * 60)
    print("✅ АВТОРИЗАЦИЯ УСПЕШНА!")
    print("=" * 60)
    print()
    print("📋 Добавь эти переменные в Railway:")
    print()
    print(f"GOOGLE_OAUTH_CLIENT_ID={CLIENT_ID}")
    print()
    print(f"GOOGLE_OAUTH_CLIENT_SECRET={CLIENT_SECRET}")
    print()
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={credentials.refresh_token}")
    print()
    print("=" * 60)
    
    # Сохраняем в файл для удобства
    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": credentials.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    
    with open("oauth_token.json", "w") as f:
        json.dump(token_data, f, indent=2)
    
    print("💾 Токен также сохранён в файл: oauth_token.json")
    print("   (Удали этот файл после копирования в Railway!)")
    print()

if __name__ == "__main__":
    main()
