import threading
import time
import logging

logger = logging.getLogger(__name__)


def _cleanup_job(interval_seconds: int):
    """Wątek działający w tle – zwalnia wygasłe rezerwacje co `interval_seconds`."""
    # import tutaj żeby uniknąć circular import
    from db import get_db

    while True:
        time.sleep(interval_seconds)
        try:
            with get_db() as (conn, cur):
                cur.execute('''
                    UPDATE tickets
                    SET status = 'available', reserved_until = NULL, booking_id = NULL
                    WHERE status = 'reserved' AND reserved_until < NOW()
                ''')
                freed = cur.rowcount
                conn.commit()
                if freed:
                    logger.info(f"Cleanup: zwolniono {freed} wygasłych rezerwacji")
        except Exception as e:
            logger.error(f"Cleanup błąd: {e}")


def start_cleanup(interval_seconds: int = 60):
    """
    Uruchom wątek cleanup przy starcie aplikacji.
    Wywołaj raz w app.py, przed app.run() lub poza blokiem if __name__=='__main__'.

    Przykład:
        from cleanup import start_cleanup
        start_cleanup(interval_seconds=60)
    """
    t = threading.Thread(
        target=_cleanup_job,
        args=(interval_seconds,),
        daemon=True,         # ginie razem z procesem głównym
        name="cleanup-thread"
    )
    t.start()
    logger.info(f"Cleanup thread uruchomiony (co {interval_seconds}s)")
