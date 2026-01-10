"""
Сервис для работы с Google APIs (Sheets, Drive, Docs)
Улучшенная версия с ротацией credentials, rate limiting, кэшированием и батчингом
"""
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable, Tuple
from app.config import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
import io
from collections import deque

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleService:
    """
    Улучшенный сервис для работы с Google APIs с ротацией credentials
    
    Особенности:
    - Ротация между 5 credentials для увеличения квоты API (60 запросов/мин на каждый = 300/мин всего)
    - Разделение на пользовательские и фоновые запросы
    - Rate limiting на каждый credential отдельно (60 запросов в минуту на каждый)
    - Умное кэширование с инвалидацией при изменениях
    - Батчинг запросов для избежания превышения лимитов
    """
    
    # API Limits (на ОДИН credential)
    MAX_REQUESTS_PER_MINUTE_PER_CREDENTIAL = 60  # Лимит Google API на один service account
    MIN_REQUEST_INTERVAL = 1.0  # Минимальный интервал между запросами (секунды)
    
    # Cache TTL (секунды)
    CACHE_TTL = {
        'folder_list': 300,      # 5 минут для списка папок
        'file_list': 180,        # 3 минуты для списка файлов
        'file_metadata': 300,    # 5 минут для метаданных файлов
        'folder_metadata': 300,  # 5 минут для метаданных папок
    }
    
    def __init__(self):
        self._credentials_list: List[Dict] = []
        self._clients: List[Dict] = []  # Кэшированные клиенты для каждого credentials
        self._user_client_index = 0
        self._background_client_index = 0
        self._load_credentials()
        self._initialize_clients()
        
        # Rate limiting - отдельно для каждого credential
        # Структура: {credential_index: deque([timestamps])}
        self._api_request_times_by_client: Dict[int, deque] = {
            i: deque(maxlen=self.MAX_REQUESTS_PER_MINUTE_PER_CREDENTIAL)
            for i in range(len(self._clients))
        }
        self._last_request_time_by_client: Dict[int, float] = {
            i: 0.0 for i in range(len(self._clients))
        }
        
        # Кэш с инвалидацией
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        # Батчинг запросов (для фоновых задач)
        self._batch_queue: List[Tuple[Callable, tuple, dict]] = []
        self._batch_last_execution = 0.0
        self._batch_interval = 5.0  # Батчинг каждые 5 секунд для фоновых задач
    
    def _load_credentials(self):
        """Загрузить все credentials из переменных окружения"""
        credentials_vars = [
            settings.GOOGLE_CREDENTIALS_1_JSON,
            settings.GOOGLE_CREDENTIALS_2_JSON,
            settings.GOOGLE_CREDENTIALS_3_JSON,
            settings.GOOGLE_CREDENTIALS_4_JSON,
            settings.GOOGLE_CREDENTIALS_5_JSON,
        ]
        
        for cred_json in credentials_vars:
            if cred_json and cred_json.strip():
                try:
                    cred_dict = json.loads(cred_json)
                    self._credentials_list.append(cred_dict)
                except json.JSONDecodeError as e:
                    logger.warning(f"Ошибка парсинга credentials JSON: {e}")
                    continue
        
        if not self._credentials_list:
            raise ValueError("No valid Google credentials found in environment variables")
        
        logger.info(f"✅ Загружено {len(self._credentials_list)} Google credentials")
    
    def _initialize_clients(self):
        """Инициализировать клиентов для каждого credentials"""
        self._clients = []
        
        # Разделение: первые 2-3 для пользовательских запросов, остальные для фоновых
        self._user_clients_count = max(1, len(self._credentials_list) // 2)
        
        for idx, cred_dict in enumerate(self._credentials_list, 1):
            try:
                creds = service_account.Credentials.from_service_account_info(
                    cred_dict,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets',
                        'https://www.googleapis.com/auth/drive',
                        'https://www.googleapis.com/auth/documents',
                    ]
                )
                
                client_info = {
                    'credentials': creds,
                    'sheets_service': build('sheets', 'v4', credentials=creds),
                    'drive_service': build('drive', 'v3', credentials=creds),
                    'docs_service': build('docs', 'v1', credentials=creds),
                    'index': idx - 1,
                }
                
                self._clients.append(client_info)
                logger.info(f"✅ Google API клиент #{idx} инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации клиента #{idx}: {e}")
                raise
        
        logger.info(f"📊 Клиенты разделены: {self._user_clients_count} пользовательских, {len(self._clients) - self._user_clients_count} фоновых")
    
    def _rate_limit_check(self, client_index: int):
        """
        Проверка и применение rate limiting для конкретного credential
        
        Args:
            client_index: Индекс клиента (credential) в списке
        """
        current_time = time.time()
        
        # Получаем очередь запросов для этого credential
        request_times = self._api_request_times_by_client.get(client_index, deque())
        last_request_time = self._last_request_time_by_client.get(client_index, 0.0)
        
        # Удаляем старые запросы (старше 1 минуты)
        while request_times and current_time - request_times[0] > 60:
            request_times.popleft()
        
        # Если достигнут лимит для этого credential, ждём
        if len(request_times) >= self.MAX_REQUESTS_PER_MINUTE_PER_CREDENTIAL:
            oldest_request = request_times[0]
            wait_time = 60 - (current_time - oldest_request) + 0.5  # +0.5 для запаса
            if wait_time > 0:
                logger.warning(f"⏳ Rate limit достигнут для credential #{client_index + 1}, ожидание {wait_time:.1f} секунд...")
                time.sleep(wait_time)
                current_time = time.time()
                # Обновляем очередь после ожидания
                while request_times and current_time - request_times[0] > 60:
                    request_times.popleft()
        
        # Проверяем минимальный интервал между запросами для этого credential
        time_since_last = current_time - last_request_time
        if time_since_last < self.MIN_REQUEST_INTERVAL:
            sleep_time = self.MIN_REQUEST_INTERVAL - time_since_last
            time.sleep(sleep_time)
            current_time = time.time()
        
        # Регистрируем новый запрос для этого credential
        request_times.append(current_time)
        self._last_request_time_by_client[client_index] = current_time
        
        # Обновляем словарь (на случай, если очередь была пустой)
        self._api_request_times_by_client[client_index] = request_times
    
    def _get_client(self, background: bool = False) -> Tuple[Dict, int]:
        """
        Получить клиент с учётом типа запроса (пользовательский/фоновый)
        
        Returns:
            Tuple[client_dict, client_index] - клиент и его индекс для rate limiting
        """
        if not self._clients:
            raise ValueError("No Google API clients available")
        
        if background:
            # Для фоновых задач используем фоновые клиенты (равномерное распределение)
            available_clients = len(self._clients) - self._user_clients_count
            client_index = (self._background_client_index % available_clients) + self._user_clients_count
            self._background_client_index += 1
        else:
            # Для пользовательских запросов используем пользовательские клиенты (равномерное распределение)
            client_index = self._user_client_index % self._user_clients_count
            self._user_client_index += 1
        
        return self._clients[client_index], client_index
    
    def _get_from_cache(self, key: str, cache_type: str = 'file_metadata') -> Optional[Any]:
        """Получить значение из кэша, если оно не устарело"""
        if key not in self._cache:
            return None
        
        ttl = self.CACHE_TTL.get(cache_type, 60)
        timestamp = self._cache_timestamps.get(key, 0)
        
        if time.time() - timestamp > ttl:
            # Кэш устарел
            del self._cache[key]
            if key in self._cache_timestamps:
                del self._cache_timestamps[key]
            logger.debug(f"Кэш устарел для ключа: {key}")
            return None
        
        logger.debug(f"✅ Кэш попадание: {key}")
        return self._cache[key]
    
    def _set_cache(self, key: str, value: Any):
        """Сохранить значение в кэш"""
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        logger.debug(f"💾 Значение сохранено в кэш: {key}")
    
    def invalidate_cache(self, pattern: Optional[str] = None):
        """
        Инвалидировать кэш (удалить все или по паттерну)
        
        Вызывать при изменениях на Google Drive, чтобы избежать устаревших данных
        """
        if pattern:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
            logger.info(f"🗑️ Кэш инвалидирован для паттерна: {pattern} ({len(keys_to_delete)} ключей)")
        else:
            count = len(self._cache)
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info(f"🗑️ Весь кэш инвалидирован ({count} ключей)")
    
    def _get_sheets_service(self, background: bool = False):
        """Получить сервис для работы с Google Sheets"""
        client, client_index = self._get_client(background=background)
        self._rate_limit_check(client_index)
        return client['sheets_service']
    
    def _get_drive_service(self, background: bool = False):
        """Получить сервис для работы с Google Drive"""
        client, client_index = self._get_client(background=background)
        self._rate_limit_check(client_index)
        return client['drive_service']
    
    def _get_docs_service(self, background: bool = False):
        """Получить сервис для работы с Google Docs"""
        client, client_index = self._get_client(background=background)
        self._rate_limit_check(client_index)
        return client['docs_service']
    
    # ========== Google Sheets ==========
    
    def read_sheet(self, range_name: str, sheet_id: Optional[str] = None, 
                   background: bool = False) -> List[List[Any]]:
        """
        Читать данные из Google Sheets
        
        Args:
            range_name: Диапазон ячеек (например, 'Sheet1!A1:D10')
            sheet_id: ID таблицы (если не указан, используется из настроек)
            background: Если True, использовать фоновый клиент
        
        Returns:
            Список строк с данными
        """
        sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        if not sheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service(background=background)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        return result.get('values', [])
    
    def write_sheet(self, range_name: str, values: List[List[Any]], 
                   sheet_id: Optional[str] = None, background: bool = False):
        """
        Записать данные в Google Sheets
        
        Args:
            range_name: Диапазон ячеек
            values: Данные для записи (список строк)
            sheet_id: ID таблицы
            background: Если True, использовать фоновый клиент
        """
        sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        if not sheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service(background=background)
        body = {'values': values}
        
        try:
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Инвалидируем кэш для этой таблицы
            self.invalidate_cache(pattern=f"sheet:{sheet_id}")
            
        except HttpError as e:
            logger.error(f"❌ Ошибка записи в Google Sheets: {e}")
            raise

    def clear_sheet_range(self, range_name: str, spreadsheet_id: Optional[str] = None, background: bool = False):
        """
        Очистить диапазон в Google Sheets
        
        Args:
            range_name: Диапазон ячеек для очистки (например, "Sheet1!A1:Z100")
            spreadsheet_id: ID таблицы (если не указан, используется из настроек)
            background: Если True, использовать фоновый клиент
        """
        spreadsheet_id = spreadsheet_id or settings.GOOGLE_SHEETS_ID
        if not spreadsheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service(background=background)
        
        try:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                body={}
            ).execute()
            
            # Инвалидируем кэш для этой таблицы
            self.invalidate_cache(pattern=f"sheet:{spreadsheet_id}")
            
        except HttpError as e:
            logger.error(f"❌ Ошибка очистки диапазона {range_name} в Google Sheets: {e}")
            raise
    
    def append_to_sheet(self, range_name: str, values: List[List[Any]], 
                       sheet_id: Optional[str] = None, background: bool = False):
        """
        Добавить данные в конец таблицы
        
        Args:
            range_name: Диапазон ячеек
            values: Данные для добавления (список строк)
            sheet_id: ID таблицы
            background: Если True, использовать фоновый клиент
        """
        sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        if not sheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service(background=background)
        body = {'values': values}
        
        try:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            # Инвалидируем кэш для этой таблицы
            self.invalidate_cache(pattern=f"sheet:{sheet_id}")
            
        except HttpError as e:
            logger.error(f"❌ Ошибка добавления в Google Sheets: {e}")
            raise
    
    # ========== Google Drive ==========
    
    def create_folder(self, name: str, parent_folder_id: Optional[str] = None, 
                     background: bool = False) -> str:
        """
        Создать папку в Google Drive
        
        Args:
            name: Название папки
            parent_folder_id: ID родительской папки (если не указан, используется из настроек)
            background: Если True, использовать фоновый клиент
        
        Returns:
            ID созданной папки
        """
        parent_folder_id = parent_folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        service = self._get_drive_service(background=background)
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]
        
        try:
            # Поддержка Shared Drive (Team Drive)
            create_params = {
                'body': file_metadata,
                'fields': 'id, name, parents',
                'supportsAllDrives': True,  # Обязательно для Shared Drive
            }
            
            folder = service.files().create(**create_params).execute()
            
            folder_id = folder.get('id')
            
            # Передаём ownership владельцу папки (если указан), чтобы папка использовала квоту пользователя
            if settings.GOOGLE_DRIVE_OWNER_EMAIL:
                ownership_transferred = self._transfer_file_ownership(folder_id, settings.GOOGLE_DRIVE_OWNER_EMAIL, service)
                if ownership_transferred:
                    logger.info(f"✅ Ownership папки '{name}' передан пользователю {settings.GOOGLE_DRIVE_OWNER_EMAIL}")
                else:
                    logger.info(f"ℹ️ Пользователю {settings.GOOGLE_DRIVE_OWNER_EMAIL} предоставлен доступ к папке '{name}' (ownership не передан)")
            
            # Инвалидируем кэш для родительской папки
            if parent_folder_id:
                self.invalidate_cache(pattern=f"folder_list:{parent_folder_id}")
            
            logger.info(f"✅ Создана папка '{name}' (ID: {folder_id})")
            return folder_id
            
        except HttpError as e:
            logger.error(f"❌ Ошибка создания папки '{name}': {e}")
            raise
    
    def get_folder_by_name(self, name: str, parent_folder_id: Optional[str] = None,
                          background: bool = False) -> Optional[str]:
        """
        Найти папку по имени в родительской папке
        
        Args:
            name: Название папки
            parent_folder_id: ID родительской папки
            background: Если True, использовать фоновый клиент
        
        Returns:
            ID папки или None, если не найдена
        """
        cache_key = f"folder:{name}:{parent_folder_id or 'root'}"
        cached = self._get_from_cache(cache_key, cache_type='folder_metadata')
        if cached is not None:
            return cached
        
        service = self._get_drive_service(background=background)
        
        # Формируем запрос
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"
        else:
            query += " and 'root' in parents"
        
        try:
            results = service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=1,
                supportsAllDrives=True,  # Поддержка Shared Drive
                includeItemsFromAllDrives=True  # Включать файлы из Shared Drive
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                folder_id = folders[0]['id']
                self._set_cache(cache_key, folder_id)
                return folder_id
            
            return None
            
        except HttpError as e:
            logger.error(f"❌ Ошибка поиска папки '{name}': {e}")
            return None
    
    def get_or_create_folder(self, name: str, parent_folder_id: Optional[str] = None,
                            background: bool = False) -> str:
        """
        Получить или создать папку
        
        Args:
            name: Название папки
            parent_folder_id: ID родительской папки
            background: Если True, использовать фоновый клиент
        
        Returns:
            ID папки
        """
        # Сначала ищем существующую папку
        folder_id = self.get_folder_by_name(name, parent_folder_id, background=background)
        if folder_id:
            return folder_id
        
        # Если не найдена, создаём новую
        return self.create_folder(name, parent_folder_id, background=background)
    
    def upload_file(self, file_content: bytes, filename: str, mime_type: str, 
                   folder_id: Optional[str] = None, background: bool = False) -> str:
        """
        Загрузить файл в Google Drive
        
        Args:
            file_content: Содержимое файла (bytes)
            filename: Имя файла
            mime_type: MIME тип файла
            folder_id: ID папки для загрузки
            background: Если True, использовать фоновый клиент
        
        Returns:
            ID загруженного файла
        """
        folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        service = self._get_drive_service(background=background)
        file_metadata = {'name': filename}
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=True
        )
        
        try:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, parents',
                supportsAllDrives=True  # Поддержка Shared Drive
            ).execute()
            
            file_id = file.get('id')
            
            # Передаём ownership владельцу папки (если указан), чтобы файл использовал квоту пользователя
            if settings.GOOGLE_DRIVE_OWNER_EMAIL:
                try:
                    self._transfer_file_ownership(file_id, settings.GOOGLE_DRIVE_OWNER_EMAIL, service)
                    logger.debug(f"✅ Ownership файла '{filename}' передан пользователю {settings.GOOGLE_DRIVE_OWNER_EMAIL}")
                except Exception as e:
                    logger.debug(f"⚠️ Не удалось передать ownership файла '{filename}': {e}")
            
            # Инвалидируем кэш для папки
            if folder_id:
                self.invalidate_cache(pattern=f"file_list:{folder_id}")
            
            logger.info(f"✅ Файл '{filename}' загружен (ID: {file_id})")
            return file_id
            
        except HttpError as e:
            logger.error(f"❌ Ошибка загрузки файла '{filename}': {e}")
            raise
    
    def list_files(self, folder_id: Optional[str] = None, 
                  background: bool = False) -> List[Dict[str, Any]]:
        """
        Получить список файлов в папке
        
        Args:
            folder_id: ID папки (если не указан, используется из настроек)
            background: Если True, использовать фоновый клиент
        
        Returns:
            Список файлов с метаданными
        """
        folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        cache_key = f"file_list:{folder_id}"
        cached = self._get_from_cache(cache_key, cache_type='file_list')
        if cached is not None:
            return cached
        
        service = self._get_drive_service(background=background)
        
        query = "trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        else:
            query += " and 'root' in parents"
        
        try:
            results = service.files().list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime, createdTime)",
                pageSize=1000
            ).execute()
            
            files = results.get('files', [])
            self._set_cache(cache_key, files)
            return files
            
        except HttpError as e:
            logger.error(f"❌ Ошибка получения списка файлов: {e}")
            return []
    
    def delete_file(self, file_id: str, background: bool = False) -> bool:
        """
        Удалить файл из Google Drive
        
        Args:
            file_id: ID файла
            background: Если True, использовать фоновый клиент
        
        Returns:
            True если успешно удалён
        """
        service = self._get_drive_service(background=background)
        
        try:
            service.files().delete(fileId=file_id).execute()
            
            # Инвалидируем весь кэш (так как не знаем, в какой папке был файл)
            self.invalidate_cache(pattern=f"file_list:")
            self.invalidate_cache(pattern=f"file_metadata:{file_id}")
            
            logger.info(f"✅ Файл удалён (ID: {file_id})")
            return True
            
        except HttpError as e:
            logger.error(f"❌ Ошибка удаления файла {file_id}: {e}")
            return False
    
    def create_doc(self, title: str, content: str, folder_id: Optional[str] = None,
                  background: bool = False) -> str:
        """
        Создать Google Doc
        
        Args:
            title: Название документа
            content: Содержимое документа
            folder_id: ID папки
            background: Если True, использовать фоновый клиент
        
        Returns:
            ID созданного документа
        """
        folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        docs_service = self._get_docs_service(background=background)
        
        try:
            # Создаём документ
            doc = docs_service.documents().create(body={'title': title}).execute()
            doc_id = doc.get('documentId')
            
            # Добавляем содержимое
            requests = [{
                'insertText': {
                    'location': {'index': 1},
                    'text': content
                }
            }]
            
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
            # Перемещаем в нужную папку
            if folder_id:
                drive_service = self._get_drive_service(background=background)
                drive_service.files().update(
                    fileId=doc_id,
                    addParents=folder_id,
                    removeParents='',
                    fields='id, parents'
                ).execute()
                
                # Инвалидируем кэш для папки
                self.invalidate_cache(pattern=f"file_list:{folder_id}")
            
            logger.info(f"✅ Создан Google Doc '{title}' (ID: {doc_id})")
            return doc_id
            
        except HttpError as e:
            logger.error(f"❌ Ошибка создания Google Doc '{title}': {e}")
            raise
    
    def get_file_metadata(self, file_id: str, background: bool = False) -> Optional[Dict[str, Any]]:
        """
        Получить метаданные файла
        
        Args:
            file_id: ID файла
            background: Если True, использовать фоновый клиент
        
        Returns:
            Метаданные файла или None
        """
        cache_key = f"file_metadata:{file_id}"
        cached = self._get_from_cache(cache_key, cache_type='file_metadata')
        if cached is not None:
            return cached
        
        service = self._get_drive_service(background=background)
        
        try:
            file_metadata = service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, modifiedTime, createdTime, parents, webViewLink, webContentLink',
                supportsAllDrives=True  # Поддержка Shared Drive
            ).execute()
            
            self._set_cache(cache_key, file_metadata)
            return file_metadata
            
        except HttpError as e:
            logger.error(f"❌ Ошибка получения метаданных файла {file_id}: {e}")
            return None
    
    def get_file_url(self, file_id: str) -> str:
        """Получить URL файла в Google Drive"""
        return f"https://drive.google.com/file/d/{file_id}/view"
    
    def get_shareable_link(self, file_id: str, background: bool = False) -> str:
        """
        Получить публичную ссылку на файл (делает файл доступным для всех с ссылкой)
        
        Args:
            file_id: ID файла
            background: Если True, использовать фоновый клиент
        
        Returns:
            Публичная ссылка на файл
        """
        service = self._get_drive_service(background=background)
        
        try:
            # Делаем файл доступным для всех с ссылкой
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            
            # Инвалидируем кэш метаданных файла
            self.invalidate_cache(pattern=f"file_metadata:{file_id}")
            
            return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            
        except HttpError as e:
            logger.error(f"❌ Ошибка создания публичной ссылки для {file_id}: {e}")
            # Возвращаем обычную ссылку даже при ошибке
            return self.get_file_url(file_id)
    
    def create_spreadsheet(
        self,
        title: str,
        folder_id: Optional[str] = None,
        background: bool = False
    ) -> Dict[str, Any]:
        """
        Создать Google Sheets документ
        
        Args:
            title: Название таблицы
            folder_id: ID папки для размещения (если не указан, используется из настроек)
            background: Если True, использовать фоновый клиент
        
        Returns:
            Словарь с информацией о созданной таблице: {"id": "...", "url": "..."}
        """
        folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        sheets_service = self._get_sheets_service(background=background)
        drive_service = self._get_drive_service(background=background)
        
        try:
            # Создаём таблицу через Drive API (так можно сразу указать папку)
            file_metadata = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            }
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            spreadsheet = drive_service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink',
                supportsAllDrives=True  # Поддержка Shared Drive
            ).execute()
            
            spreadsheet_id = spreadsheet.get('id')
            spreadsheet_url = spreadsheet.get('webViewLink', f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            
            # Передаём ownership владельцу папки (если указан), чтобы файл использовал квоту пользователя, а не сервисного аккаунта
            if settings.GOOGLE_DRIVE_OWNER_EMAIL:
                ownership_transferred = self._transfer_file_ownership(spreadsheet_id, settings.GOOGLE_DRIVE_OWNER_EMAIL, drive_service)
                if ownership_transferred:
                    logger.info(f"✅ Ownership таблицы '{title}' передан пользователю {settings.GOOGLE_DRIVE_OWNER_EMAIL}")
                else:
                    logger.info(f"ℹ️ Пользователю {settings.GOOGLE_DRIVE_OWNER_EMAIL} предоставлен доступ к таблице '{title}' (ownership не передан)")
            
            # Инвалидируем кэш для папки
            if folder_id:
                self.invalidate_cache(pattern=f"file_list:{folder_id}")
            
            logger.info(f"✅ Создана Google Sheets таблица '{title}' (ID: {spreadsheet_id})")
            
            return {
                "id": spreadsheet_id,
                "url": spreadsheet_url,
                "name": title
            }
            
        except HttpError as e:
            logger.error(f"❌ Ошибка создания Google Sheets таблицы '{title}': {e}")
            raise
    
    def _transfer_file_ownership(self, file_id: str, owner_email: str, drive_service) -> bool:
        """
        Передать ownership файла/папки указанному пользователю
        
        Это позволяет файлам использовать квоту пользователя/организации, а не сервисного аккаунта
        
        ВАЖНО:
        - В Shared Drive (Team Drive): ownership можно передать между аккаунтами одного домена организации
        - В обычном Drive: ownership можно передать только внутри одного домена
        - Если домены разные - пользователь получит только права "writer", файлы останутся в квоте сервисного аккаунта
        - В Shared Drive файлы используют общую квоту организации, ownership работает внутри организации
        
        Args:
            file_id: ID файла или папки
            owner_email: Email пользователя, которому передаётся ownership (должен быть в том же домене для Shared Drive)
            drive_service: Экземпляр Drive API service
        
        Returns:
            True если успешно передано ownership, False если только дали доступ
        """
        try:
            # Сначала даём пользователю доступ как редактору
            drive_service.permissions().create(
                fileId=file_id,
                body={
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': owner_email
                },
                fields='id',
                supportsAllDrives=True  # Поддержка Shared Drive
            ).execute()
            
            # Затем пытаемся передать ownership
            # В Shared Drive: ownership можно передать между аккаунтами одного домена организации
            # В обычном Drive: ownership можно передать только внутри одного домена
            try:
                drive_service.permissions().create(
                    fileId=file_id,
                    body={
                        'type': 'user',
                        'role': 'owner',
                        'emailAddress': owner_email
                    },
                    transferOwnership=True,
                    fields='id',
                    supportsAllDrives=True  # Поддержка Shared Drive
                ).execute()
                logger.info(f"✅ Ownership файла {file_id} передан пользователю {owner_email}")
                return True
            except HttpError as e:
                # Если передача ownership невозможна (разные домены или нет прав)
                error_str = str(e)
                if 'ownershipChangeAcrossDomainNotPermitted' in error_str:
                    logger.info(f"ℹ️ Ownership не может быть передан между доменами. Пользователю {owner_email} предоставлен полный доступ (writer)")
                    return False
                elif 'permissionDenied' in error_str or 'forbidden' in error_str.lower():
                    logger.warning(f"⚠️ Нет прав для передачи ownership файла {file_id} пользователю {owner_email}: {e}")
                    logger.info(f"💡 Убедитесь, что сервисный аккаунт имеет права 'Content Manager' или 'Manager' на Shared Drive")
                    return False
                else:
                    raise
            
        except HttpError as e:
            # Если передача ownership невозможна (разные домены), это нормально - уже обработано выше
            if 'ownershipChangeAcrossDomainNotPermitted' in str(e):
                logger.info(f"ℹ️ Ownership не может быть передан между доменами. Пользователю {owner_email} предоставлен полный доступ (writer)")
                return False
            # Если файл уже принадлежит пользователю или нет прав - игнорируем
            if 'permissionDenied' in str(e) or 'notFound' in str(e):
                logger.debug(f"Не удалось передать ownership файла {file_id}: {e}")
            else:
                logger.warning(f"Ошибка передачи ownership файла {file_id}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при передаче ownership файла {file_id}: {e}")
            return False
    
    def create_sheet_tab(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        background: bool = False
    ) -> int:
        """
        Создать новый лист в Google Sheets таблице
        
        Args:
            spreadsheet_id: ID таблицы
            sheet_name: Название листа
            background: Если True, использовать фоновый клиент
        
        Returns:
            ID созданного листа (sheetId)
        """
        sheets_service = self._get_sheets_service(background=background)
        
        try:
            request_body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            
            response = sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request_body
            ).execute()
            
            sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
            
            # Инвалидируем кэш для этой таблицы
            self.invalidate_cache(pattern=f"sheet:{spreadsheet_id}")
            
            logger.info(f"✅ Создан лист '{sheet_name}' (sheetId: {sheet_id}) в таблице {spreadsheet_id}")
            
            return sheet_id
            
        except HttpError as e:
            logger.error(f"❌ Ошибка создания листа '{sheet_name}': {e}")
            raise
    
    def batch_update_sheet(
        self,
        spreadsheet_id: str,
        requests: List[Dict[str, Any]],
        background: bool = False
    ) -> Dict[str, Any]:
        """
        Выполнить батч обновлений в Google Sheets
        
        Args:
            spreadsheet_id: ID таблицы
            requests: Список запросов для batchUpdate
            background: Если True, использовать фоновый клиент
        
        Returns:
            Результат batchUpdate
        """
        sheets_service = self._get_sheets_service(background=background)
        
        try:
            response = sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            # Инвалидируем кэш для этой таблицы
            self.invalidate_cache(pattern=f"sheet:{spreadsheet_id}")
            
            return response
            
        except HttpError as e:
            logger.error(f"❌ Ошибка batch update в таблице {spreadsheet_id}: {e}")
            raise
