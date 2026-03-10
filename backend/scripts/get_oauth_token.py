"""
Скрипт для получения OAuth refresh_token для Google Drive.
Запустите один раз локально, чтобы получить токен.

Запуск: python scripts/get_oauth_token.py
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

import os

# OAuth credentials — из Google Cloud Console → APIs & Services → Credentials
# Set env vars GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET before running
CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

# Scopes для Google Drive и Sheets
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/documents'
]

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set env vars GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET")
        print("Example (PowerShell):")
        print('  $env:GOOGLE_OAUTH_CLIENT_ID = "YOUR_ID.apps.googleusercontent.com"')
        print('  $env:GOOGLE_OAUTH_CLIENT_SECRET = "GOCSPX-..."')
        return

    print("=" * 60)
    print("OAuth token for Google Drive")
    print("=" * 60)
    print()
    print("Browser will open for authorization.")
    print()
    print("If you see 'Google hasn't verified this app',")
    print("click 'Advanced' -> 'Go to ... (unsafe)'")
    print()
    input("Press Enter to continue...")
    
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
    print("SUCCESS!")
    print("=" * 60)
    print()
    print("Add these env vars to Railway:")
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
    
    print("Token saved to: oauth_token.json")
    print("DELETE this file after copying values to Railway!")
    print()

if __name__ == "__main__":
    main()
