"""
Tracks support notification messages so VP4PR can reply directly.

Maps: (admin_telegram_id, bot_message_id) -> (user_telegram_id, user_name)
"""
from typing import Dict, Tuple, Optional

_support_messages: Dict[Tuple[int, int], Tuple[int, str]] = {}


def track_support_message(admin_tg_id: int, bot_msg_id: int, user_tg_id: int, user_name: str):
    _support_messages[(admin_tg_id, bot_msg_id)] = (user_tg_id, user_name)
    _cleanup_old_entries()


def get_support_target(admin_tg_id: int, reply_to_msg_id: int) -> Optional[Tuple[int, str]]:
    return _support_messages.get((admin_tg_id, reply_to_msg_id))


def _cleanup_old_entries():
    if len(_support_messages) > 500:
        keys = list(_support_messages.keys())
        for k in keys[:250]:
            _support_messages.pop(k, None)
