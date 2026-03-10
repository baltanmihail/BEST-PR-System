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
            created_count = 0
            status_changes: List[Dict] = []

            for sr in sheets_rows:
                match = self._find_matching_db_request(sr, db_requests)

                if match:
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
                else:
                    if not sr.get("start_date") or not sr.get("end_date"):
                        continue
                    equipment = await self._find_equipment_by_name(db, sr.get("equipment_name", ""))
                    if not equipment:
                        logger.warning(f"Sheets row #{sr['app_num']}: equipment '{sr.get('equipment_name')}' not found in DB, skipping")
                        continue
                    user = await self._find_user_by_identifier(db, sr.get("who_raw", ""))
                    if not user:
                        logger.warning(f"Sheets row #{sr['app_num']}: user '{sr.get('who_raw')}' not found in DB, skipping")
                        continue
                    new_enum = STATUS_RU_TO_ENUM.get(sr["status"], EquipmentRequestStatus.PENDING)
                    purpose_parts = [sr.get("purpose", ""), sr.get("comment", "")]
                    purpose = " | ".join(p for p in purpose_parts if p)

                    new_req = EquipmentRequest(
                        equipment_id=equipment.id,
                        user_id=user.id if user else None,
                        start_date=sr["start_date"],
                        end_date=sr["end_date"],
                        status=new_enum.value,
                        purpose=purpose or None,
                    )
                    db.add(new_req)
                    created_count += 1
                    logger.info(
                        f"Sync: создана заявка из Sheets #{sr['app_num']} "
                        f"на '{sr.get('equipment_name')}' статус='{new_enum.value}'"
                    )

            if updated_count or created_count:
                await db.commit()

            logger.info(
                f"✅ Bidirectional sync: обновлено {updated_count}, создано {created_count}, "
                f"изменений статуса: {len(status_changes)}"
            )

            return {
                "status": "success",
                "updated": updated_count,
                "created": created_count,
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
    async def _find_equipment_by_name(db: AsyncSession, name: str) -> Optional[Equipment]:
        """Find equipment by name (fuzzy)."""
        if not name:
            return None
        result = await db.execute(select(Equipment))
        all_eq = result.scalars().all()
        name_lower = name.lower().strip()
        for eq in all_eq:
            if eq.name.lower().strip() == name_lower:
                return eq
        for eq in all_eq:
            if name_lower in eq.name.lower() or eq.name.lower() in name_lower:
                return eq
        return None

    @staticmethod
    async def _find_user_by_identifier(db: AsyncSession, who: str) -> Optional[User]:
        """Find user by username or name from 'Кто берёт' cell."""
        if not who:
            return None
        result = await db.execute(select(User))
        users = result.scalars().all()
        who_lower = who.lower().strip()
        for u in users:
            if u.telegram_username and u.telegram_username.lstrip("@").lower() in who_lower:
                return u
            if u.full_name and u.full_name.lower() in who_lower:
                return u
            name = f"{u.first_name or ''} {u.last_name or ''}".strip().lower()
            if name and name in who_lower:
                return u
        return None

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
                "who_raw": who,
                "start_date": start_date,
                "end_date": end_date,
                "equipment_name": _cell("Что берёт"),
                "purpose": _cell("Название мероприятия"),
                "comment": _cell("Комментарий"),
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
