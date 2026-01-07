"""
Сервис для работы с Google APIs (Sheets, Drive, Docs)
"""
import json
import random
from typing import List, Dict, Optional, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
import io

from app.config import settings


class GoogleService:
    """Сервис для работы с Google APIs с ротацией credentials"""
    
    def __init__(self):
        self._credentials_list: List[Dict] = []
        self._current_credential_index = 0
        self._load_credentials()
    
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
                except json.JSONDecodeError:
                    continue
        
        if not self._credentials_list:
            raise ValueError("No valid Google credentials found in environment variables")
    
    def _get_credentials(self) -> service_account.Credentials:
        """Получить credentials с ротацией"""
        if not self._credentials_list:
            raise ValueError("No Google credentials available")
        
        # Ротация: берём следующий credentials
        cred_dict = self._credentials_list[self._current_credential_index]
        self._current_credential_index = (self._current_credential_index + 1) % len(self._credentials_list)
        
        return service_account.Credentials.from_service_account_info(
            cred_dict,
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/documents',
            ]
        )
    
    def _get_sheets_service(self):
        """Получить сервис для работы с Google Sheets"""
        creds = self._get_credentials()
        return build('sheets', 'v4', credentials=creds)
    
    def _get_drive_service(self):
        """Получить сервис для работы с Google Drive"""
        creds = self._get_credentials()
        return build('drive', 'v3', credentials=creds)
    
    def _get_docs_service(self):
        """Получить сервис для работы с Google Docs"""
        creds = self._get_credentials()
        return build('docs', 'v1', credentials=creds)
    
    # ========== Google Sheets ==========
    
    def read_sheet(self, range_name: str, sheet_id: Optional[str] = None) -> List[List[Any]]:
        """
        Читать данные из Google Sheets
        
        Args:
            range_name: Диапазон ячеек (например, 'Sheet1!A1:D10')
            sheet_id: ID таблицы (если не указан, используется из настроек)
        
        Returns:
            Список строк с данными
        """
        sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        if not sheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        return result.get('values', [])
    
    def write_sheet(self, range_name: str, values: List[List[Any]], sheet_id: Optional[str] = None):
        """
        Записать данные в Google Sheets
        
        Args:
            range_name: Диапазон ячеек
            values: Данные для записи (список строк)
            sheet_id: ID таблицы
        """
        sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        if not sheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service()
        body = {'values': values}
        
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
    
    def append_to_sheet(self, range_name: str, values: List[List[Any]], sheet_id: Optional[str] = None):
        """Добавить данные в конец таблицы"""
        sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        if not sheet_id:
            raise ValueError("Google Sheets ID not configured")
        
        service = self._get_sheets_service()
        body = {'values': values}
        
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    
    # ========== Google Drive ==========
    
    def create_folder(self, name: str, parent_folder_id: Optional[str] = None) -> str:
        """
        Создать папку в Google Drive
        
        Args:
            name: Название папки
            parent_folder_id: ID родительской папки (если не указан, используется из настроек)
        
        Returns:
            ID созданной папки
        """
        parent_folder_id = parent_folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        service = self._get_drive_service()
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]
        
        folder = service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        return folder.get('id')
    
    def upload_file(self, file_content: bytes, filename: str, mime_type: str, 
                   folder_id: Optional[str] = None) -> str:
        """
        Загрузить файл в Google Drive
        
        Args:
            file_content: Содержимое файла (bytes)
            filename: Имя файла
            mime_type: MIME тип файла
            folder_id: ID папки для загрузки
        
        Returns:
            ID загруженного файла
        """
        folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        service = self._get_drive_service()
        file_metadata = {'name': filename}
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id')
    
    def create_doc(self, title: str, content: str, folder_id: Optional[str] = None) -> str:
        """
        Создать Google Doc
        
        Args:
            title: Название документа
            content: Содержимое документа
            folder_id: ID папки
        
        Returns:
            ID созданного документа
        """
        folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        
        service = self._get_docs_service()
        
        # Создаём документ
        doc = service.documents().create(body={'title': title}).execute()
        doc_id = doc.get('documentId')
        
        # Добавляем содержимое
        requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': content
            }
        }]
        
        service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        # Перемещаем в нужную папку
        if folder_id:
            drive_service = self._get_drive_service()
            drive_service.files().update(
                fileId=doc_id,
                addParents=folder_id,
                removeParents='',
                fields='id, parents'
            ).execute()
        
        return doc_id
    
    def get_file_url(self, file_id: str) -> str:
        """Получить URL файла в Google Drive"""
        return f"https://drive.google.com/file/d/{file_id}/view"
    
    def get_shareable_link(self, file_id: str) -> str:
        """Получить публичную ссылку на файл"""
        service = self._get_drive_service()
        
        # Делаем файл доступным для всех с ссылкой
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
