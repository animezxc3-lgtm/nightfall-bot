from bot.core import database as db
from bot.core.config import settings

class AdminService:
    def get_level(self, user_id: int, peer_id: int | None = None) -> int:
        if user_id == settings.creator_id: return 100
        g = db.get_global_role(user_id)
        l = db.get_admin_level_for_chat(peer_id, user_id) if peer_id and peer_id > 2000000000 else 0
        return max(g, l)
    
    def is_admin(self, user_id: int, peer_id: int | None = None, min_level: int = 1) -> bool:
        return self.get_level(user_id, peer_id) >= min_level
    
    def is_creator(self, user_id: int) -> bool:
        return user_id == settings.creator_id

    def remove_rights(self, target_id: int) -> tuple[bool, str]:
        if target_id == settings.creator_id: return False, "Нельзя снять права с создателя."
        if db.get_global_role(target_id) > 0:
            db.set_global_role(target_id, 0)
            return True, "Глобальная роль снята."
        with db.db_cursor() as (_, cur):
            cur.execute("SELECT peer_id FROM admin_chat_rights WHERE user_id=? AND level>0", (target_id,))
            rows = cur.fetchall()
        if not rows: return False, "Нет прав."
        for row in rows: db.set_admin_level(row["peer_id"], target_id, 0)
        return True, f"Сняты права в {len(rows)} беседах."