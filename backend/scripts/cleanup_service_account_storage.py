"""
Скрипт для очистки хранилища сервисных аккаунтов Google Drive.
Удаляет все файлы, которые занимают квоту сервисного аккаунта.

Запуск: python scripts/cleanup_service_account_storage.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

def get_credentials_from_env():
    """Получить все credentials из переменных окружения"""
    credentials_list = []
    for i in range(1, 6):
        env_var = f"GOOGLE_CREDENTIALS_{i}_JSON"
        creds_json = os.getenv(env_var)
        if creds_json:
            try:
                creds_data = json.loads(creds_json)
                credentials_list.append((i, creds_data))
            except json.JSONDecodeError:
                print(f"⚠️ Ошибка парсинга {env_var}")
    return credentials_list

def cleanup_storage(creds_data, account_num):
    """Очистить хранилище одного сервисного аккаунта"""
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    credentials = service_account.Credentials.from_service_account_info(
        creds_data, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=credentials)
    
    email = creds_data.get('client_email', 'unknown')
    print(f"\n{'='*60}")
    print(f"🔍 Аккаунт #{account_num}: {email}")
    print(f"{'='*60}")
    
    # Получить информацию о квоте
    about = service.about().get(fields="storageQuota").execute()
    quota = about.get('storageQuota', {})
    used = int(quota.get('usageInDrive', 0))
    limit = int(quota.get('limit', 0))
    
    print(f"📊 Использовано: {used / 1024 / 1024:.2f} МБ")
    if limit > 0:
        print(f"📊 Лимит: {limit / 1024 / 1024 / 1024:.2f} ГБ")
    
    # Найти все файлы, принадлежащие этому аккаунту
    files_deleted = 0
    bytes_freed = 0
    page_token = None
    
    while True:
        results = service.files().list(
            q="'me' in owners",
            spaces='drive',
            fields="nextPageToken, files(id, name, size, mimeType)",
            pageToken=page_token,
            pageSize=100
        ).execute()
        
        files = results.get('files', [])
        
        for file in files:
            file_id = file['id']
            file_name = file.get('name', 'Без имени')
            file_size = int(file.get('size', 0))
            
            try:
                service.files().delete(fileId=file_id).execute()
                files_deleted += 1
                bytes_freed += file_size
                print(f"  🗑️ Удалён: {file_name} ({file_size / 1024:.1f} КБ)")
            except Exception as e:
                print(f"  ❌ Ошибка удаления {file_name}: {e}")
        
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    
    # Очистить корзину
    try:
        service.files().emptyTrash().execute()
        print(f"  🗑️ Корзина очищена")
    except Exception as e:
        print(f"  ⚠️ Ошибка очистки корзины: {e}")
    
    print(f"\n✅ Удалено файлов: {files_deleted}")
    print(f"✅ Освобождено: {bytes_freed / 1024 / 1024:.2f} МБ")
    
    return files_deleted, bytes_freed

def main():
    print("🧹 Очистка хранилища сервисных аккаунтов Google Drive")
    print("=" * 60)
    
    credentials_list = get_credentials_from_env()
    
    if not credentials_list:
        print("❌ Не найдены credentials в переменных окружения!")
        print("💡 Установите GOOGLE_CREDENTIALS_1_JSON, GOOGLE_CREDENTIALS_2_JSON, и т.д.")
        return
    
    print(f"📋 Найдено аккаунтов: {len(credentials_list)}")
    
    total_files = 0
    total_bytes = 0
    
    for account_num, creds_data in credentials_list:
        try:
            files, bytes_freed = cleanup_storage(creds_data, account_num)
            total_files += files
            total_bytes += bytes_freed
        except Exception as e:
            print(f"❌ Ошибка обработки аккаунта #{account_num}: {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 ИТОГО:")
    print(f"   Удалено файлов: {total_files}")
    print(f"   Освобождено: {total_bytes / 1024 / 1024:.2f} МБ")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
