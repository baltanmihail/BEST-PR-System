"""
Сервис двусторонней синхронизации оборудования между БД и Google Sheets.
Архитектура аналогична sync_with_sheets() + periodic_sync() из BEST Channel Bot.

Ключевая логика:
- Читает все заявки из листа "Заявки на оборудку"
- Сопоставляет со заявками в БД по датам + пользователю + оборудованию
- При расхождении статуса: обновляет БД и возвращает status_changes для уведомлений
- При изменениях: обновляет календарь и статусы оборудования
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus, Equipment
from app.models.user import User
from app.services.google_service import GoogleService
from app.services.equipment_sheets_sync import EquipmentSheetsSync

logger = logging.getLogger(__name__)

STATUS_RU_TO_ENUM = {
    "На рассмотрении": EquipmentRequestStatus.PENDING,
    "Одобрено": EquipmentRequestStatus.APPROVED,
    "Отклонено": EquipmentRequestStatus.REJECTED,
    "Выдано": EquipmentRequestStatus.ACTIVE,
    "Возвращено": EquipmentRequestStatus.COMPLETED,
    "Отменено": EquipmentRequestStatus.CANCELLED,
}


class EquipmentBidirectionalSync:
    """Двусторонняя синхронизация заявок Sheets <-> PostgreSQL"""

    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.sheets_sync = EquipmentSheetsSync(google_service)

    async def sync_from_sheets(self, db: AsyncSession) -> dict:
        """
        Синхронизирует изменения статусов заявок из Google Sheets -> БД.
        Возвращает status_changes для рассылки уведомлений.
        """
        try:
            sheets_id = self.sheets_sync._get_equipment_sheets_id()

            values = self.google_service.read_sheet(
                "Заявки на оборудку!A:K",
                sheet_id=sheets_id,
                background=True,
            )

            if not values or len(values) < 2:
                return {"status": "skipped", "reason": "no_requests_in_sheet"}

            headers = values[0]
            col_idx = self._resolve_columns(headers)
            if col_idx is None:
                return {"status": "error", "error": "missing_columns"}

            sheets_rows = self._parse_sheet_rows(values[1:], col_idx)
            if not sheets_rows:
                return {"status": "skipped", "reason": "no_valid_rows"}

            db_requests = await self._load_db_requests(db)

            updated_count = 0
            status_changes: List[Dict] = []

            for sr in sheets_rows:
                match = self._find_matching_db_request(sr, db_requests)
                if not match:
                    continue

                req, old_enum = match
                new_enum = STATUS_RU_TO_ENUM.get(sr["status"])
                if not new_enum:
                    continue

                old_value = old_enum.value if isinstance(old_enum, EquipmentRequestStatus) else str(old_enum)
                if old_value == new_enum.value:
                    continue

                req.status = new_enum.value
                if new_enum == EquipmentRequestStatus.REJECTED and sr.get("rejection_reason"):
                    req.rejection_reason = sr["rejection_reason"]

                updated_count += 1
                status_changes.append({
                    "request_id": req.id,
                    "old_status": old_value,
                    "new_status": new_enum.value,
                    "user_id": req.user_id,
                })
                logger.info(
                    f"Sync: заявка {str(req.id)[:8]} статус '{old_value}' -> '{new_enum.value}'"
                )

            if updated_count:
                await db.commit()

            logger.info(
                f"✅ Bidirectional sync: обновлено {updated_count}, "
                f"изменений статуса: {len(status_changes)}"
            )

            return {
                "status": "success",
                "updated": updated_count,
                "status_changes": status_changes,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка двусторонней синхронизации: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_columns(headers: List[str]) -> Optional[Dict[str, int]]:
        required = {"Номер", "Статус", "Дата выдачи", "Дата возврата", "Кто берёт"}
        idx: Dict[str, int] = {}
        for i, h in enumerate(headers):
            h_stripped = h.strip()
            idx[h_stripped] = i
        if not required.issubset(idx.keys()):
            missing = required - set(idx.keys())
            logger.error(f"Не найдены колонки: {missing}, заголовки: {headers}")
            return None
        return idx

    @staticmethod
    def _parse_sheet_rows(
        rows: List[list], col_idx: Dict[str, int]
    ) -> List[Dict]:
        parsed = []
        for row in rows:
            def _cell(name: str) -> str:
                i = col_idx.get(name, -1)
                if i < 0 or i >= len(row):
                    return ""
                return str(row[i]).strip()

            app_num = _cell("Номер")
            status = _cell("Статус")
            who = _cell("Кто берёт")
            start_str = _cell("Дата выдачи")
            end_str = _cell("Дата возврата")

            if not app_num or not status:
                continue

            start_date = _parse_date(start_str)
            end_date = _parse_date(end_str)

            parsed.append({
                "app_num": app_num,
                "status": status,
                "who": who.lower(),
                "start_date": start_date,
                "end_date": end_date,
                "rejection_reason": _cell("Причина отказа") if "Причина отказа" in col_idx else None,
            })
        return parsed

    @staticmethod
    async def _load_db_requests(db: AsyncSession) -> List[dict]:
        result = await db.execute(select(EquipmentRequest))
        requests = result.scalars().all()

        enriched = []
        for req in requests:
            eq_r = await db.execute(select(Equipment).where(Equipment.id == req.equipment_id))
            equipment = eq_r.scalar_one_or_none()

            usr_r = await db.execute(select(User).where(User.id == req.user_id))
            user = usr_r.scalar_one_or_none()

            enriched.append({
                "request": req,
                "equipment": equipment,
                "user": user,
            })
        return enriched

    @staticmethod
    def _find_matching_db_request(
        sheet_row: dict, db_requests: List[dict]
    ) -> Optional[tuple]:
        """
        Сопоставляет строку из Sheets с заявкой в БД.
        Критерии совпадения: даты выдачи/возврата + имя пользователя (fuzzy).
        """
        sr_start = sheet_row.get("start_date")
        sr_end = sheet_row.get("end_date")
        sr_who = sheet_row.get("who", "")

        for item in db_requests:
            req = item["request"]
            user = item["user"]

            if sr_start and sr_end:
                if req.start_date != sr_start or req.end_date != sr_end:
                    continue
            elif sr_start:
                if req.start_date != sr_start:
                    continue

            if user and sr_who:
                identifiers = []
                if user.telegram_username:
                    identifiers.append(user.telegram_username.lstrip("@").lower())
                if user.full_name:
                    identifiers.append(user.full_name.lower())
                name = f"{user.first_name or ''} {user.last_name or ''}".strip().lower()
                if name:
                    identifiers.append(name)

                if not any(ident and ident in sr_who for ident in identifiers):
                    continue

            old_status = req.status
            if isinstance(old_status, str):
                try:
                    old_status = EquipmentRequestStatus(old_status)
                except ValueError:
                    pass
            return (req, old_status)

        return None


def _parse_date(s: str) -> Optional[date]:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None
