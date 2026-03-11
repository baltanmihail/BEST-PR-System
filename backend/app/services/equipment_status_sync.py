"""
Сервис автоматического обновления статусов оборудования по датам.
Логика из BEST Channel Bot: На складе -> Занят, съёмка предстоит -> Занят, съёмка окончена -> На складе
"""
import logging
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, cast, String

from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus, EquipmentStatus
from app.models.user import User
from app.services.google_service import GoogleService

logger = logging.getLogger(__name__)


class EquipmentStatusSync:
    """Автоматическое обновление статусов оборудования по датам"""

    def __init__(self, google_service: GoogleService):
        self.google_service = google_service

    def _get_equipment_sheets_id(self) -> str:
        from app.services.equipment_sheets_sync import EquipmentSheetsSync
        sync_service = EquipmentSheetsSync(self.google_service)
        return sync_service._get_equipment_sheets_id()

    async def update_equipment_statuses_by_date(self, db: AsyncSession) -> dict:
        """
        Обновляет статусы оборудования в листе "Вся оборудка" по текущим одобренным заявкам.
        Заполняет даты выдачи/возврата и "У кого сейчас?" из ближайших заявок.
        """
        try:
            sheets_id = self._get_equipment_sheets_id()

            approved_query = select(EquipmentRequest).where(
                cast(EquipmentRequest.status, String).in_([
                    EquipmentRequestStatus.APPROVED.value,
                    EquipmentRequestStatus.ACTIVE.value,
                ])
            )
            result = await db.execute(approved_query)
            requests = result.scalars().all()

            for req in requests:
                eq_r = await db.execute(select(Equipment).where(Equipment.id == req.equipment_id))
                req.equipment = eq_r.scalar_one_or_none()
                usr_r = await db.execute(select(User).where(User.id == req.user_id))
                req.user = usr_r.scalar_one_or_none()
                if req.task_id:
                    from app.models.task import Task
                    t_r = await db.execute(select(Task).where(Task.id == req.task_id))
                    req.task = t_r.scalar_one_or_none()
                else:
                    req.task = None

            logger.info(f"Получено {len(requests)} одобренных заявок для обновления статусов")

            equipment_apps: Dict[str, List[dict]] = {}
            for req in requests:
                if not req.equipment:
                    continue
                eq_number = req.equipment.specs.get("number") if req.equipment.specs else None
                if not eq_number:
                    eq_number = await self._find_equipment_number(req.equipment.name)
                if not eq_number:
                    continue

                shooting_date = None
                if hasattr(req, "task") and req.task and hasattr(req.task, "due_date") and req.task.due_date:
                    shooting_date = req.task.due_date.date() if hasattr(req.task.due_date, "date") else req.task.due_date

                who_takes = ""
                if req.user:
                    username = req.user.username or ""
                    full_name = req.user.full_name or ""
                    who_takes = f"https://t.me/{username.lstrip('@')} - {full_name}" if username else full_name

                equipment_apps.setdefault(eq_number, []).append({
                    "issue": req.start_date,
                    "return": req.end_date,
                    "shooting": shooting_date,
                    "who_takes": who_takes,
                })

            for eq_num in equipment_apps:
                equipment_apps[eq_num].sort(key=lambda x: x["issue"])

            values = self.google_service.read_sheet(
                "Вся оборудка!A:J",
                sheet_id=sheets_id,
                background=True,
            )
            if not values or len(values) < 2:
                return {"status": "skipped", "reason": "no_equipment"}

            headers = values[0]
            try:
                status_col = headers.index("Статус")
            except ValueError:
                return {"status": "error", "error": "Колонка 'Статус' не найдена"}

            equipment_num_col = headers.index("Номер") if "Номер" in headers else 0
            date_issue_col = headers.index("Дата выдачи") if "Дата выдачи" in headers else -1
            date_return_col = headers.index("Дата возврата") if "Дата возврата" in headers else -1
            who_now_col = headers.index("У кого сейчас?") if "У кого сейчас?" in headers else -1

            sheet_id_num = await self._get_sheet_id(sheets_id, "Вся оборудка")
            today = date.today()
            batch_updates: List[dict] = []
            updated_count = 0
            dates_updated_count = 0
            who_updated_count = 0

            for i, row in enumerate(values[1:], start=2):
                if len(row) <= max(status_col, equipment_num_col):
                    continue

                eq_num = row[equipment_num_col].strip() if equipment_num_col < len(row) else ""
                if not eq_num:
                    continue

                current_status = row[status_col].strip() if status_col < len(row) else ""
                date_issue = row[date_issue_col].strip() if date_issue_col >= 0 and date_issue_col < len(row) else ""
                date_return = row[date_return_col].strip() if date_return_col >= 0 and date_return_col < len(row) else ""
                who_now = row[who_now_col].strip() if who_now_col >= 0 and who_now_col < len(row) else ""

                row_updates: List[dict] = []

                if eq_num in equipment_apps:
                    nearest_app = self._find_nearest_active_app(equipment_apps[eq_num], today)

                    if nearest_app:
                        new_issue = nearest_app["issue"].strftime("%d.%m.%Y")
                        new_return = nearest_app["return"].strftime("%d.%m.%Y")
                        new_who = nearest_app.get("who_takes", "")

                        if date_issue_col >= 0 and date_issue != new_issue:
                            row_updates.append(self._cell_update(sheet_id_num, i, date_issue_col, new_issue))
                            date_issue = new_issue
                            dates_updated_count += 1

                        if date_return_col >= 0 and date_return != new_return:
                            row_updates.append(self._cell_update(sheet_id_num, i, date_return_col, new_return))
                            date_return = new_return
                            dates_updated_count += 1

                        if who_now_col >= 0 and new_who and who_now != new_who:
                            row_updates.append(self._cell_update(sheet_id_num, i, who_now_col, new_who))
                            who_updated_count += 1
                    else:
                        if current_status != "На складе":
                            for col, val in [(date_issue_col, date_issue), (date_return_col, date_return), (who_now_col, who_now)]:
                                if col >= 0 and val:
                                    row_updates.append(self._cell_update(sheet_id_num, i, col, ""))
                elif current_status != "На складе":
                    for col, val in [(date_issue_col, date_issue), (date_return_col, date_return), (who_now_col, who_now)]:
                        if col >= 0 and val:
                            row_updates.append(self._cell_update(sheet_id_num, i, col, ""))

                issue_date = _parse_date(date_issue)
                return_date = _parse_date(date_return)

                if issue_date and return_date:
                    shooting_date = None
                    if eq_num in equipment_apps:
                        for app in equipment_apps[eq_num]:
                            if app["issue"] == issue_date and app["return"] == return_date:
                                shooting_date = app.get("shooting")
                                break

                    new_status = self._determine_status(today, issue_date, return_date, shooting_date)

                    if new_status and new_status != current_status:
                        row_updates.append(self._cell_update(sheet_id_num, i, status_col, new_status))
                        updated_count += 1
                        logger.debug(f"Оборудование #{eq_num}: {current_status} -> {new_status}")

                        if new_status == "На складе":
                            for col in [date_issue_col, date_return_col, who_now_col]:
                                if col >= 0:
                                    row_updates.append(self._cell_update(sheet_id_num, i, col, ""))

                batch_updates.extend(row_updates)

            if batch_updates:
                batch_size = 50
                for start in range(0, len(batch_updates), batch_size):
                    self.google_service.batch_update_sheet(
                        sheets_id,
                        batch_updates[start : start + batch_size],
                        background=True,
                    )

            logger.info(
                f"✅ Статусы: обновлено {updated_count}, "
                f"дат: {dates_updated_count}, 'У кого?': {who_updated_count}"
            )
            return {
                "status": "success",
                "updated_statuses": updated_count,
                "updated_dates": dates_updated_count,
                "updated_who": who_updated_count,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка обновления статусов оборудования: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_update(sheet_id: int, row_1based: int, col_0based: int, value: str) -> dict:
        return {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_1based - 1,
                    "endRowIndex": row_1based,
                    "startColumnIndex": col_0based,
                    "endColumnIndex": col_0based + 1,
                },
                "rows": [{"values": [{"userEnteredValue": {"stringValue": value}}]}],
                "fields": "userEnteredValue",
            }
        }

    @staticmethod
    def _find_nearest_active_app(apps: List[dict], today: date) -> Optional[dict]:
        for app in apps:
            if app["return"] >= today and app["issue"] <= today:
                return app
        future = [a for a in apps if a["issue"] > today]
        return min(future, key=lambda x: x["issue"]) if future else None

    @staticmethod
    def _determine_status(
        today: date,
        issue_date: date,
        return_date: date,
        shooting_date: Optional[date],
    ) -> Optional[str]:
        if today > return_date:
            return "На складе"
        if today >= issue_date:
            shoot = shooting_date or (issue_date + timedelta(days=1))
            return "Занят, съёмка окончена" if today > shoot else "Занят, съёмка предстоит"
        return "На складе"

    async def _get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        try:
            svc = self.google_service._get_sheets_service(background=False)
            sp = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            for sheet in sp.get("sheets", []):
                if sheet["properties"]["title"] == sheet_name:
                    return sheet["properties"]["sheetId"]
            return 0
        except Exception as e:
            logger.warning(f"Ошибка получения ID листа {sheet_name}: {e}")
            return 0

    async def _find_equipment_number(self, equipment_name: str) -> Optional[str]:
        try:
            sheets_id = self._get_equipment_sheets_id()
            values = self.google_service.read_sheet(
                "Вся оборудка!A:D", sheet_id=sheets_id, background=True
            )
            if not values or len(values) < 2:
                return None
            for row in values[1:]:
                if len(row) > 1 and row[1].strip() == equipment_name.strip():
                    return row[0].strip()
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска номера оборудования: {e}")
            return None


def _parse_date(s: str) -> Optional[date]:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None
