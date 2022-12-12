import redis

REDIS_CLIENT = redis.Redis(host="news_crawler_redis", port=6379, db=5)


def only_one_concurrency(function=None, key="", timeout=None):
    def _dec(run_func):
        def wrapper(*args, **kwargs):
            have_lock = False
            lock = REDIS_CLIENT.lock(key, timeout=timeout)
            try:
                have_lock = lock.acquire(blocking=False)
                if have_lock:
                    run_func(*args, **kwargs)
            finally:
                if have_lock:
                    lock.release()

        return wrapper

    return _dec(function) if function is not None else _dec


class ReadOnlyAdminDateFields:
    readonly_fields = (
        "created_at",
        "updated_at",
        "deleted_at",
    )
