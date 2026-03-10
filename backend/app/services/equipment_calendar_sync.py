"""
Сервис синхронизации календаря занятости оборудования с Google Sheets.
Полная реализация с логикой цветов (красный/жёлтый/серый) как в BEST Channel Bot.
"""
import logging
from typing import List, Optional, Dict, Set
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
import calendar as cal_lib

from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus
from app.models.user import User
from app.services.google_service import GoogleService

logger = logging.getLogger(__name__)

EQUIPMENT_SHEET = "Вся оборудка"
CALENDAR_SHEET = "Календарь занятости оборудования"


class EquipmentCalendarSync:
    """Создание/обновление календаря занятости оборудования в Google Sheets"""

    def __init__(self, google_service: GoogleService):
        self.google_service = google_service

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def create_or_update_calendar_sheet(
        self,
        db: AsyncSession,
        calendar_sheet_name: str = CALENDAR_SHEET,
    ) -> bool:
        """
        Создаёт или обновляет лист календаря занятости.

        Цвета ячеек (как в BEST Channel Bot):
        - Жёлтый {1,1,0} — заявка «На рассмотрении»
        - Красный {1,0,0} — заявка «Одобрено» / «Выдано»
        - Серый  {0.8,0.8,0.8} — завершённые/история

        Номер заявки записывается в начале, конце и в дату съёмки.
        """
        try:
            sheets_id = self._get_equipment_sheets_id()

            requests = await self._load_active_requests(db)
            all_equipment = self._get_equipment_list_from_sheets()

            if not all_equipment:
                logger.warning("Нет оборудования для календаря")
                return False

            equipment_bookings = self._build_bookings(requests, all_equipment, db)
            logger.info(f"Собрано бронирований для {len(equipment_bookings)} единиц оборудования")

            all_dates, start_month, end_month = self._compute_date_range(equipment_bookings)
            sheet_id = self._get_or_create_calendar_sheet(sheets_id, calendar_sheet_name)

            self._write_headers(sheets_id, sheet_id, start_month, end_month, all_dates)

            sorted_equipment = sorted(
                all_equipment,
                key=lambda x: int(x["number"]) if x["number"].isdigit() else 999,
            )

            self._write_data(sheets_id, sheet_id, sorted_equipment, equipment_bookings, all_dates)

            self._clear_old_formatting(sheets_id, sheet_id, sorted_equipment, all_dates)

            self._apply_formatting(sheets_id, sheet_id, sorted_equipment, equipment_bookings, all_dates)

            self._freeze_panes(sheets_id, sheet_id)

            logger.info("Календарь занятости оборудования обновлён")
            return True

        except Exception as e:
            logger.error(f"Ошибка создания/обновления календаря: {e}", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_active_requests(self, db: AsyncSession) -> List[dict]:
        """Загружает заявки со статусами pending/approved/active/completed из БД."""
        query = select(EquipmentRequest).where(
            cast(EquipmentRequest.status, String).in_([
                EquipmentRequestStatus.PENDING.value,
                EquipmentRequestStatus.APPROVED.value,
                EquipmentRequestStatus.ACTIVE.value,
                EquipmentRequestStatus.COMPLETED.value,
            ])
        )
        result = await db.execute(query)
        rows = result.scalars().all()

        enriched = []
        for req in rows:
            eq_r = await db.execute(select(Equipment).where(Equipment.id == req.equipment_id))
            equipment = eq_r.scalar_one_or_none()
            if not equipment:
                continue

            usr_r = await db.execute(select(User).where(User.id == req.user_id))
            user = usr_r.scalar_one_or_none()

            status_val = req.status.value if isinstance(req.status, EquipmentRequestStatus) else str(req.status)
            try:
                status_enum = EquipmentRequestStatus(status_val)
            except ValueError:
                status_enum = EquipmentRequestStatus.PENDING

            enriched.append({
                "request": req,
                "equipment": equipment,
                "user": user,
                "status_enum": status_enum,
            })
        return enriched

    def _get_equipment_list_from_sheets(self) -> List[Dict]:
        try:
            sheets_id = self._get_equipment_sheets_id()
            values = self.google_service.read_sheet(
                f"{EQUIPMENT_SHEET}!A:D",
                sheet_id=sheets_id,
                background=True,
            )
            if not values or len(values) < 2:
                return []
            items = []
            for row in values[1:]:
                if len(row) < 2:
                    continue
                number = row[0].strip() if row[0] else ""
                name = row[1].strip() if row[1] else ""
                if number and name:
                    items.append({"number": number, "name": name})
            return items
        except Exception as e:
            logger.error(f"Ошибка получения списка оборудования: {e}")
            return []

    # ------------------------------------------------------------------
    # Bookings
    # ------------------------------------------------------------------

    def _build_bookings(
        self,
        requests: List[dict],
        all_equipment: List[Dict],
        db,
    ) -> Dict[str, Dict[date, Dict]]:
        """
        Строит структуру {equipment_number: {date: {app_num, status}}}.
        Номер заявки записывается в первую, последнюю дату и дату съёмки.
        """
        name_to_number = {eq["name"]: eq["number"] for eq in all_equipment}
        bookings: Dict[str, Dict[date, Dict]] = {}

        for item in requests:
            req = item["request"]
            equipment = item["equipment"]
            status_enum: EquipmentRequestStatus = item["status_enum"]

            eq_number = equipment.specs.get("number") if equipment.specs else None
            if not eq_number:
                eq_number = name_to_number.get(equipment.name)
            if not eq_number:
                continue

            status_map = {
                EquipmentRequestStatus.PENDING: "На рассмотрении",
                EquipmentRequestStatus.APPROVED: "Одобрено",
                EquipmentRequestStatus.ACTIVE: "Одобрено",
                EquipmentRequestStatus.COMPLETED: "История",
            }
            status_ru = status_map.get(status_enum, "На рассмотрении")

            app_num = str(req.id)[:8]
            bookings.setdefault(eq_number, {})

            current = req.start_date
            while current <= req.end_date:
                is_edge = current == req.start_date or current == req.end_date
                cell_num = app_num if is_edge else ""

                if current not in bookings[eq_number]:
                    bookings[eq_number][current] = {"app_num": cell_num, "status": status_ru}
                elif is_edge:
                    bookings[eq_number][current] = {"app_num": cell_num, "status": status_ru}

                current += timedelta(days=1)

        return bookings

    # ------------------------------------------------------------------
    # Date range
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_date_range(
        bookings: Dict[str, Dict[date, Dict]],
    ) -> tuple:
        all_dates_set: Set[date] = set()
        for eq_dates in bookings.values():
            all_dates_set.update(eq_dates.keys())

        today = date.today()
        if all_dates_set:
            min_d = min(all_dates_set)
            max_d = max(all_dates_set)
            start_month = min(min_d, today).replace(day=1)
            end_base = max(max_d, today)
        else:
            start_month = today.replace(day=1)
            end_base = today

        end_month_d = end_base.replace(day=1)
        for _ in range(5):
            if end_month_d.month == 12:
                end_month_d = end_month_d.replace(year=end_month_d.year + 1, month=1)
            else:
                end_month_d = end_month_d.replace(month=end_month_d.month + 1)

        last_day = cal_lib.monthrange(end_month_d.year, end_month_d.month)[1]
        end_month = end_month_d.replace(day=last_day)

        dates_list = []
        cur = start_month
        while cur <= end_month:
            dates_list.append(cur)
            cur += timedelta(days=1)

        return dates_list, start_month, end_month

    # ------------------------------------------------------------------
    # Sheet helpers
    # ------------------------------------------------------------------

    def _get_equipment_sheets_id(self) -> str:
        from app.config import settings

        if settings.GOOGLE_EQUIPMENT_SHEETS_ID:
            return settings.GOOGLE_EQUIPMENT_SHEETS_ID

        try:
            from app.services.drive_structure import DriveStructureService
            ds = DriveStructureService()
            folder_id = ds.get_equipment_folder_id()
            for name in ["Учёт оборудки", "Вся оборудка", "Оборудование"]:
                sid = self._find_sheets_in_folder(folder_id, name)
                if sid:
                    return sid
        except Exception:
            pass

        return "1gJ7muzAY00IK82QlMFRu4EaJdrwKw3nizjZ_I0nUe3s"

    def _find_sheets_in_folder(self, folder_id: str, name: str) -> Optional[str]:
        try:
            drive = self.google_service._get_drive_service(background=False)
            q = f"name='{name}' and mimeType='application/vnd.google-apps.spreadsheet' and '{folder_id}' in parents and trashed=false"
            files = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
            return files[0]["id"] if files else None
        except Exception:
            return None

    def _get_or_create_calendar_sheet(self, sheets_id: str, sheet_name: str) -> int:
        try:
            svc = self.google_service._get_sheets_service(background=False)
            sp = svc.spreadsheets().get(spreadsheetId=sheets_id).execute()
            for s in sp.get("sheets", []):
                if s["properties"]["title"] == sheet_name:
                    return s["properties"]["sheetId"]

            self.google_service.batch_update_sheet(
                spreadsheet_id=sheets_id,
                requests=[{"addSheet": {"properties": {"title": sheet_name}}}],
                background=False,
            )
            sp = svc.spreadsheets().get(spreadsheetId=sheets_id).execute()
            for s in sp.get("sheets", []):
                if s["properties"]["title"] == sheet_name:
                    return s["properties"]["sheetId"]
            return 0
        except Exception as e:
            logger.error(f"Ошибка получения/создания листа календаря: {e}")
            return 0

    # ------------------------------------------------------------------
    # Write headers & data
    # ------------------------------------------------------------------

    MONTH_NAMES_RU = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }
    WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def _write_headers(
        self,
        sheets_id: str,
        sheet_id: int,
        start_month: date,
        end_month: date,
        all_dates: List[date],
    ):
        period = (
            f"{self.MONTH_NAMES_RU.get(start_month.month, '')} {start_month.year}"
            f" - {self.MONTH_NAMES_RU.get(end_month.month, '')} {end_month.year}"
        )

        dates_row = [""] + [str(d.day) for d in all_dates]
        weekdays_row = [""] + [self.WEEKDAYS_RU[d.weekday()] for d in all_dates]
        empty_row = [""] * (len(all_dates) + 1)

        rows = [[period], dates_row, weekdays_row, empty_row]

        self.google_service.batch_update_sheet(
            spreadsheet_id=sheets_id,
            requests=[{
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 4,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(all_dates) + 1,
                    },
                    "rows": [
                        {"values": [{"userEnteredValue": {"stringValue": str(c)}} for c in r]}
                        for r in rows
                    ],
                    "fields": "userEnteredValue",
                }
            }],
            background=False,
        )

    def _write_data(
        self,
        sheets_id: str,
        sheet_id: int,
        sorted_equipment: List[Dict],
        bookings: Dict[str, Dict[date, Dict]],
        all_dates: List[date],
    ):
        eq_rows = []
        for eq in sorted_equipment:
            eq_num = eq["number"]
            row = [eq_num]
            eq_bookings = bookings.get(eq_num, {})
            for d in all_dates:
                info = eq_bookings.get(d)
                row.append(info["app_num"] if info else "")
            eq_rows.append(row)

        if not eq_rows:
            return

        start_row = 4  # 0-based: row index 4 = 5th row in sheet
        self.google_service.batch_update_sheet(
            spreadsheet_id=sheets_id,
            requests=[{
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": start_row + len(eq_rows),
                        "startColumnIndex": 0,
                        "endColumnIndex": len(all_dates) + 1,
                    },
                    "rows": [
                        {"values": [{"userEnteredValue": {"stringValue": str(c)}} for c in r]}
                        for r in eq_rows
                    ],
                    "fields": "userEnteredValue",
                }
            }],
            background=False,
        )

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    COLOR_YELLOW = {"red": 1.0, "green": 1.0, "blue": 0.0}
    COLOR_RED = {"red": 1.0, "green": 0.0, "blue": 0.0}
    COLOR_GREY = {"red": 0.8, "green": 0.8, "blue": 0.8}
    COLOR_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}

    def _clear_old_formatting(
        self,
        sheets_id: str,
        sheet_id: int,
        sorted_equipment: List[Dict],
        all_dates: List[date],
    ):
        """Сбрасывает фон ячеек данных на белый перед применением нового форматирования."""
        if not sorted_equipment or not all_dates:
            return

        self.google_service.batch_update_sheet(
            spreadsheet_id=sheets_id,
            requests=[{
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 4,
                        "endRowIndex": 4 + len(sorted_equipment),
                        "startColumnIndex": 1,
                        "endColumnIndex": len(all_dates) + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {"backgroundColor": self.COLOR_WHITE}
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }],
            background=False,
        )

    def _apply_formatting(
        self,
        sheets_id: str,
        sheet_id: int,
        sorted_equipment: List[Dict],
        bookings: Dict[str, Dict[date, Dict]],
        all_dates: List[date],
    ):
        """Красит ячейки: жёлтый для «На рассмотрении», красный для «Одобрено», серый для «История»."""
        requests_batch: List[dict] = []
        yellow_count = 0
        red_count = 0
        grey_count = 0

        for eq_idx, eq in enumerate(sorted_equipment):
            eq_num = eq["number"]
            eq_bookings = bookings.get(eq_num, {})
            row_0based = 4 + eq_idx

            for date_idx, d in enumerate(all_dates):
                info = eq_bookings.get(d)
                if not info:
                    continue

                status = info.get("status", "")
                if status == "На рассмотрении":
                    color = self.COLOR_YELLOW
                    yellow_count += 1
                elif status == "Одобрено":
                    color = self.COLOR_RED
                    red_count += 1
                elif status == "История":
                    color = self.COLOR_GREY
                    grey_count += 1
                else:
                    continue

                col_0based = 1 + date_idx

                requests_batch.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_0based,
                            "endRowIndex": row_0based + 1,
                            "startColumnIndex": col_0based,
                            "endColumnIndex": col_0based + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {"backgroundColor": color}
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                })

        if requests_batch:
            batch_size = 100
            for i in range(0, len(requests_batch), batch_size):
                self.google_service.batch_update_sheet(
                    spreadsheet_id=sheets_id,
                    requests=requests_batch[i : i + batch_size],
                    background=False,
                )

        logger.info(
            f"Форматирование: {yellow_count} жёлтых, {red_count} красных, {grey_count} серых ячеек"
        )

    def _freeze_panes(self, sheets_id: str, sheet_id: int):
        self.google_service.batch_update_sheet(
            spreadsheet_id=sheets_id,
            requests=[{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "frozenRowCount": 4,
                            "frozenColumnCount": 1,
                        },
                    },
                    "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
                }
            }],
            background=False,
        )
