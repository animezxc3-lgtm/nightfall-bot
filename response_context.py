from contextvars import ContextVar
CURRENT_USER_ID = ContextVar("current_user_id", default=None)
EXCLUDE_ACTOR = ContextVar("exclude_actor", default=False)
def set_user(user_id, exclude=False):
    CURRENT_USER_ID.set(user_id)
    EXCLUDE_ACTOR.set(exclude)
def get_user_id(): return CURRENT_USER_ID.get()
def get_exclude_actor(): return EXCLUDE_ACTOR.get()
