"""
Сервис двусторонней синхронизации оборудования между БД и Google Sheets.
Архитектура аналогична sync_with_sheets() + periodic_sync() из BEST Channel Bot.

Ключевая логика:
- Читает все заявки из листа "Заявки на оборудку"
- Сопоставляет со заявками в БД по датам + пользователю + оборудованию
- При расхождении статуса: обновляет БД и возвращает status_changes для уведомлений
- Новые заявки из Sheets создаются в БД
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus, Equipment
from app.models.user import User
from app.services.google_service import GoogleService
from app.services.equipment_sheets_sync import EquipmentSheetsSync

logger = logging.getLogger(__name__)

STATUS_RU_TO_ENUM = {
    "на рассмотрении": EquipmentRequestStatus.PENDING,
    "одобрено": EquipmentRequestStatus.APPROVED,
    "отклонено": EquipmentRequestStatus.REJECTED,
    "выдано": EquipmentRequestStatus.ACTIVE,
    "возвращено": EquipmentRequestStatus.COMPLETED,
    "отменено": EquipmentRequestStatus.CANCELLED,
    "занят, съёмка предстоит": EquipmentRequestStatus.ACTIVE,
    "занят, съёмка окончена": EquipmentRequestStatus.COMPLETED,
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
            eq_sheet_name = self.sheets_sync.EQUIPMENT_SHEET  # "Вся оборудка"
            logger.info(f"Bidirectional sync: sheets_id={sheets_id}, eq_sheet='{eq_sheet_name}'")

            # 1) Read equipment names from "Вся оборудка" (same API as equipment_sheets_sync)
            eq_name_map = self._load_equipment_name_map(sheets_id, eq_sheet_name)

            # 2) Read requests data (displayed values)
            values = self.google_service.read_sheet(
                "Заявки на оборудку!A:K",
                sheet_id=sheets_id,
                background=True,
            )

            if not values:
                logger.warning("Bidirectional sync: sheet returned None/empty")
                return {"status": "skipped", "reason": "no_data"}

            logger.info(f"Bidirectional sync: got {len(values)} rows from 'Заявки на оборудку'")

            if len(values) < 2:
                logger.info("Bidirectional sync: only header row, no requests")
                return {"status": "skipped", "reason": "no_requests_in_sheet"}

            headers = values[0]
            logger.info(f"Bidirectional sync: headers = {headers}")

            col_idx = self._resolve_columns(headers)
            if col_idx is None:
                return {"status": "error", "error": "missing_columns"}

            # 3) Read formulas to resolve equipment references like ='Вся оборудка'!C2
            formulas = None
            try:
                formulas = self.google_service.read_sheet_formulas(
                    "Заявки на оборудку!A:K",
                    sheet_id=sheets_id,
                    background=True,
                )
                logger.info(f"Bidirectional sync: read {len(formulas) if formulas else 0} formula rows")
                if formulas and len(formulas) > 1:
                    eq_col = col_idx.get("Что берёт", -1)
                    if eq_col >= 0:
                        for fi, frow in enumerate(formulas[1:]):
                            if eq_col < len(frow):
                                logger.info(f"  Formula row {fi}: col[{eq_col}] = '{frow[eq_col]}'")
            except Exception as e:
                logger.warning(f"Could not read formulas: {e}", exc_info=True)

            # 4) Also log raw data rows for debugging
            for di, drow in enumerate(values[1:]):
                eq_col = col_idx.get("Что берёт", -1)
                eq_val = drow[eq_col] if eq_col >= 0 and eq_col < len(drow) else "N/A"
                logger.info(f"  Data row {di}: col[{eq_col}]='Что берёт' = '{eq_val}' (len={len(drow)})")

            sheets_rows = self._parse_sheet_rows(
                values[1:], col_idx, eq_name_map,
                formulas[1:] if formulas and len(formulas) > 1 else None,
            )
            logger.info(f"Bidirectional sync: parsed {len(sheets_rows)} valid rows from sheets")

            if not sheets_rows:
                return {"status": "skipped", "reason": "no_valid_rows"}

            for sr in sheets_rows:
                logger.info(
                    f"  Row #{sr['app_num']}: who='{sr.get('who_raw','')}', "
                    f"eq='{sr.get('equipment_name','')}', "
                    f"dates={sr.get('start_date')}->{sr.get('end_date')}, "
                    f"status='{sr.get('status','')}'"
                )

            db_requests = await self._load_db_requests(db)
            logger.info(f"Bidirectional sync: {len(db_requests)} requests in DB")

            updated_count = 0
            created_count = 0
            status_changes: List[Dict] = []

            for sr in sheets_rows:
                match = self._find_matching_db_request(sr, db_requests)

                if match:
                    req, old_enum = match
                    new_enum = STATUS_RU_TO_ENUM.get(sr["status"].lower())
                    if not new_enum:
                        logger.warning(f"Unknown status '{sr['status']}' for row #{sr['app_num']}")
                        continue

                    old_value = old_enum.value if isinstance(old_enum, EquipmentRequestStatus) else str(old_enum)
                    if old_value == new_enum.value:
                        continue

                    req.status = new_enum.value
                    if new_enum == EquipmentRequestStatus.REJECTED and sr.get("rejection_reason"):
                        req.rejection_reason = sr["rejection_reason"]

                    updated_count += 1
                    eq_item = next((d for d in db_requests if d["request"] is req), None)
                    eq_name = eq_item["equipment"].name if eq_item and eq_item.get("equipment") else ""
                    status_changes.append({
                        "request_id": req.id,
                        "old_status": old_value,
                        "new_status": new_enum.value,
                        "user_id": req.user_id,
                        "equipment_name": eq_name,
                    })
                    logger.info(
                        f"Sync: request {str(req.id)[:8]} status '{old_value}' -> '{new_enum.value}'"
                    )
                else:
                    if not sr.get("start_date") or not sr.get("end_date"):
                        logger.info(f"Row #{sr['app_num']}: no dates, skipping creation")
                        continue
                    eq_name = sr.get("equipment_name", "")
                    equipment = await self._find_equipment_by_name(db, eq_name) if eq_name else None
                    if not equipment and not eq_name:
                        # Fallback: if eq name is empty and eq_name_map has it by row index
                        # try reading from name_map using request row position
                        logger.info(f"Row #{sr['app_num']}: eq name empty, trying fallback from name_map")
                        # The request number often corresponds to the equipment row in "Вся оборудка"
                        # But this isn't reliable. Instead, just log and try all DB equipment.
                        all_eq = await db.execute(select(Equipment))
                        all_equipment = all_eq.scalars().all()
                        logger.info(f"Row #{sr['app_num']}: {len(all_equipment)} equipment in DB")
                        for eq in all_equipment:
                            logger.info(f"  DB equipment: '{eq.name}' (id={str(eq.id)[:8]})")
                    if not equipment:
                        logger.warning(
                            f"Row #{sr['app_num']}: equipment '{eq_name}' "
                            f"not found in DB, skipping"
                        )
                        continue
                    user = await self._find_user_by_identifier(db, sr.get("who_raw", ""))
                    if not user:
                        logger.warning(
                            f"Row #{sr['app_num']}: user '{sr.get('who_raw')}' "
                            f"not found in DB, skipping"
                        )
                        continue
                    new_enum = STATUS_RU_TO_ENUM.get(
                        sr["status"].lower(), EquipmentRequestStatus.PENDING
                    )
                    purpose_parts = [sr.get("purpose", ""), sr.get("comment", "")]
                    purpose = " | ".join(p for p in purpose_parts if p)

                    new_req = EquipmentRequest(
                        equipment_id=equipment.id,
                        user_id=user.id,
                        start_date=sr["start_date"],
                        end_date=sr["end_date"],
                        status=new_enum.value,
                        purpose=purpose or None,
                    )
                    db.add(new_req)
                    created_count += 1
                    logger.info(
                        f"Sync: created request from Sheets #{sr['app_num']} "
                        f"for '{sr.get('equipment_name')}' user='{sr.get('who_raw')}' "
                        f"status='{new_enum.value}'"
                    )

            if updated_count or created_count:
                await db.commit()

            logger.info(
                f"Bidirectional sync done: updated={updated_count}, created={created_count}, "
                f"status_changes={len(status_changes)}"
            )

            return {
                "status": "success",
                "updated": updated_count,
                "created": created_count,
                "status_changes": status_changes,
            }

        except Exception as e:
            logger.error(f"Bidirectional sync error: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_equipment_name_map(self, sheets_id: str, eq_sheet_name: str) -> Dict[int, str]:
        """
        Read equipment sheet and build row_number -> equipment_name map.
        Uses the SAME sheet name and range as equipment_sheets_sync (A:D).
        Column B (index 1) = equipment name (text).
        Row 1 = header, row 2+ = data.
        """
        name_map: Dict[int, str] = {}
        try:
            # Use exactly the same range as equipment_sheets_sync
            values = self.google_service.read_sheet(
                f"{eq_sheet_name}!A:D",
                sheet_id=sheets_id,
                background=True,
            )
            if not values:
                logger.warning(f"_load_equipment_name_map: '{eq_sheet_name}' returned empty")
                return name_map

            logger.info(f"_load_equipment_name_map: read {len(values)} rows from '{eq_sheet_name}'")
            if values:
                logger.info(f"  Header: {values[0]}")

            for i, row in enumerate(values):
                row_num = i + 1  # 1-based
                if row_num == 1:
                    continue  # skip header
                if len(row) < 2:
                    continue
                raw_name = str(row[1]).strip()
                name = " ".join(raw_name.replace("\r", " ").replace("\n", " ").split())
                if name and len(name) >= 3:
                    name_map[row_num] = name

            logger.info(f"Equipment name map: {len(name_map)} items")
            for rn, nm in name_map.items():
                logger.info(f"  row {rn} -> '{nm}'")
            return name_map

        except Exception as e:
            logger.error(f"_load_equipment_name_map error: {e}", exc_info=True)
            return name_map

    @staticmethod
    def _resolve_columns(headers: List[str]) -> Optional[Dict[str, int]]:
        """Build column name -> index mapping. Uses fuzzy matching for known columns."""
        idx: Dict[str, int] = {}
        for i, h in enumerate(headers):
            idx[h.strip()] = i

        ALIASES = {
            "Номер": ["Номер", "№", "No"],
            "Статус": ["Статус", "Status"],
            "Дата выдачи": ["Дата выдачи", "Дата начала", "Start"],
            "Дата возврата": ["Дата возврата", "Дата окончания", "End"],
            "Кто берёт": ["Кто берёт", "Кто берет", "Пользователь", "Who"],
            "Что берёт": ["Что берёт", "Что берет", "Оборудование", "What"],
            "Название мероприятия": ["Название мероприятия", "Мероприятие", "Event"],
            "Комментарий": ["Комментарий", "Comment"],
            "Дата съёмки": ["Дата съёмки", "Дата съемки"],
        }

        resolved: Dict[str, int] = {}
        for canonical, aliases in ALIASES.items():
            for alias in aliases:
                if alias in idx:
                    resolved[canonical] = idx[alias]
                    break

        required = {"Номер", "Статус"}
        missing = required - set(resolved.keys())
        if missing:
            logger.error(f"Missing required columns: {missing}, available headers: {list(idx.keys())}")
            return None

        if "Дата выдачи" not in resolved and "Дата съёмки" not in resolved:
            logger.error(f"No date column found, headers: {list(idx.keys())}")
            return None

        logger.info(f"Resolved columns: {resolved}")
        return resolved

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
            if u.telegram_username:
                uname = u.telegram_username.lstrip("@").lower()
                if uname and uname in who_lower:
                    return u
            if u.full_name and u.full_name.lower() in who_lower:
                return u
            name = f"{u.first_name or ''} {u.last_name or ''}".strip().lower()
            if name and name in who_lower:
                return u
        # Also try matching if a Telegram link is in the cell
        for u in users:
            if u.telegram_username:
                uname = u.telegram_username.lstrip("@").lower()
                if uname and f"t.me/{uname}" in who_lower.replace("https://", "").replace("http://", ""):
                    return u
        return None

    @staticmethod
    def _parse_sheet_rows(
        rows: List[list],
        col_idx: Dict[str, int],
        eq_name_map: Optional[Dict[int, str]] = None,
        formula_rows: Optional[List[list]] = None,
    ) -> List[Dict]:
        parsed = []
        eq_col = col_idx.get("Что берёт", -1)

        for row_i, row in enumerate(rows):
            def _cell(name: str) -> str:
                i = col_idx.get(name, -1)
                if i < 0 or i >= len(row):
                    return ""
                return str(row[i]).strip()

            app_num = _cell("Номер")
            status = _cell("Статус")

            if not app_num or not status:
                continue

            start_str = _cell("Дата выдачи")
            end_str = _cell("Дата возврата")
            shooting_str = _cell("Дата съёмки")

            start_date = _parse_date(start_str) if start_str else None
            end_date = _parse_date(end_str) if end_str else None

            if not start_date and shooting_str:
                start_date = _parse_date(shooting_str)
            if not end_date and start_date:
                end_date = start_date

            who_raw = _cell("Кто берёт")
            equipment_name = _cell("Что берёт")
            purpose = _cell("Название мероприятия")
            comment = _cell("Комментарий")

            # If equipment_name is empty, try to resolve from formula
            if not equipment_name and eq_name_map and formula_rows:
                equipment_name = _resolve_eq_from_formula(
                    formula_rows, row_i, eq_col, eq_name_map
                )
                if equipment_name:
                    logger.info(
                        f"Row #{app_num}: resolved equipment from formula -> '{equipment_name}'"
                    )

            parsed.append({
                "app_num": app_num,
                "status": status,
                "who": who_raw.lower(),
                "who_raw": who_raw,
                "start_date": start_date,
                "end_date": end_date,
                "equipment_name": equipment_name,
                "purpose": purpose,
                "comment": comment,
                "rejection_reason": None,
            })
        return parsed

    @staticmethod
    async def _load_db_requests(db: AsyncSession) -> List[dict]:
        result = await db.execute(select(EquipmentRequest))
        requests = result.scalars().all()

        eq_result = await db.execute(select(Equipment))
        all_equipment = {eq.id: eq for eq in eq_result.scalars().all()}

        usr_result = await db.execute(select(User))
        all_users = {u.id: u for u in usr_result.scalars().all()}

        enriched = []
        for req in requests:
            enriched.append({
                "request": req,
                "equipment": all_equipment.get(req.equipment_id),
                "user": all_users.get(req.user_id),
            })
        return enriched

    @staticmethod
    def _find_matching_db_request(
        sheet_row: dict, db_requests: List[dict]
    ) -> Optional[tuple]:
        """
        Сопоставляет строку из Sheets с заявкой в БД.
        Критерии: даты + пользователь (fuzzy) + оборудование (fuzzy).
        """
        sr_start = sheet_row.get("start_date")
        sr_end = sheet_row.get("end_date")
        sr_who = sheet_row.get("who", "")
        sr_eq = sheet_row.get("equipment_name", "").lower().strip()

        for item in db_requests:
            req = item["request"]
            user = item["user"]
            equipment = item["equipment"]

            # Match dates
            if sr_start and sr_end:
                if req.start_date != sr_start or req.end_date != sr_end:
                    continue
            elif sr_start:
                if req.start_date != sr_start:
                    continue

            # Match user
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

            # Match equipment name (fuzzy)
            if sr_eq and equipment:
                eq_name = equipment.name.lower().strip()
                if sr_eq not in eq_name and eq_name not in sr_eq:
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
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue


# Regex to extract row number from formulas like ='Вся оборудка'!C2 or ='Вся оборудку'!C15
_FORMULA_ROW_RE = re.compile(r"[!'\"]\s*!?\s*[A-Z]+(\d+)", re.IGNORECASE)
_FORMULA_ROW_RE2 = re.compile(r"![A-Z]+(\d+)", re.IGNORECASE)


def _resolve_eq_from_formula(
    formula_rows: List[list],
    row_i: int,
    eq_col: int,
    eq_name_map: Dict[int, str],
) -> str:
    """Extract equipment name from a formula like ='Вся оборудка'!C2."""
    if eq_col < 0:
        logger.info(f"_resolve_eq_from_formula: eq_col={eq_col}, skipping")
        return ""
    if row_i >= len(formula_rows):
        logger.info(f"_resolve_eq_from_formula: row_i={row_i} >= len(formula_rows)={len(formula_rows)}")
        return ""
    frow = formula_rows[row_i]
    if eq_col >= len(frow):
        logger.info(f"_resolve_eq_from_formula: eq_col={eq_col} >= len(frow)={len(frow)}, frow={frow}")
        return ""
    formula = str(frow[eq_col]).strip()
    logger.info(f"_resolve_eq_from_formula: formula='{formula}'")
    if not formula:
        return ""

    m = _FORMULA_ROW_RE2.search(formula)
    if not m:
        m = _FORMULA_ROW_RE.search(formula)
    if m:
        ref_row = int(m.group(1))
        name = eq_name_map.get(ref_row, "")
        logger.info(f"_resolve_eq_from_formula: '{formula}' -> row {ref_row} -> '{name}' (map keys: {list(eq_name_map.keys())[:5]})")
        return name
    else:
        logger.warning(f"_resolve_eq_from_formula: could not parse formula '{formula}'")
    return ""
