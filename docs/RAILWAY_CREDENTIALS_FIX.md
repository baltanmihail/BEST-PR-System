# 🔧 Исправление ошибки Google Credentials

## Проблема

При запуске приложения на Railway возникает ошибка:
```
ValueError: No valid Google credentials found in environment variables
```

Приложение не может запуститься.

## Причина

`GoogleService` создавался при импорте модулей, что вызывало ошибку при отсутствии credentials.

## Решение

Исправлена ленивая инициализация:
- `GoogleService` теперь создаётся только при использовании функций Google Drive
- Приложение может запуститься без credentials (Google Drive функции будут недоступны)
- Credentials проверяются только при попытке использовать Google Drive

## Что нужно сделать

### 1. Добавить credentials на Railway

**Railway** → `best-pr-api` → **Variables** → **New Variable**

Добавь 5 переменных:

#### GOOGLE_CREDENTIALS_1_JSON
```
{"type":"service_account","project_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",...}
```

**Важно:**
- Скопируй весь JSON из `credentials-1.json`
- Вставь как одну строку (без переносов)
- Или используй многострочный формат, если Railway поддерживает

#### Повтори для всех 5 credentials:
- `GOOGLE_CREDENTIALS_1_JSON`
- `GOOGLE_CREDENTIALS_2_JSON`
- `GOOGLE_CREDENTIALS_3_JSON`
- `GOOGLE_CREDENTIALS_4_JSON`
- `GOOGLE_CREDENTIALS_5_JSON`

### 2. Конвертация JSON в одну строку

Если нужна одна строка, используй PowerShell:
```powershell
$json = Get-Content credentials-1.json -Raw | ConvertFrom-Json | ConvertTo-Json -Compress
$json
```

Или Python:
```python
import json
with open('credentials-1.json', 'r') as f:
    data = json.load(f)
    print(json.dumps(data))
```

### 3. Дать доступ service accounts к Google Drive

1. Открой: https://drive.google.com/drive/folders/10A2GVTrYq8_Rm6pBDvQUEQxibHFdWxBd
2. Нажми **Share** (Поделиться)
3. Добавь email каждого service account:
   - Из `credentials-1.json` → `client_email` (типа `xxx@yyy.iam.gserviceaccount.com`)
   - Права: **Editor** (Редактор)
   - Повтори для всех 5 service accounts
4. Нажми **Send**

## Проверка

После добавления credentials:

1. **Перезапусти деплой:**
   - Railway Dashboard → `best-pr-api` → **Deployments** → **Redeploy**

2. **Проверь логи:**
   - Должно быть:
     ```
     ✅ Google Drive структура инициализирована: {'bot_folder_id': '...'}
     ```
   - Или (если credentials нет):
     ```
     ℹ️ Google credentials не найдены, Google Drive функции будут недоступны
     ```

## Если не добавишь credentials

- ✅ Приложение запустится
- ❌ Google Drive функции будут недоступны (загрузка файлов, синхронизация с Sheets)
- ✅ Остальные функции будут работать нормально

---

Всё готово! 🎉
