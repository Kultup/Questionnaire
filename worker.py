import os
import time
from datetime import datetime

from app import app, notification_service

LOCK_KEY = 'notification_worker_lock'

def main():
    interval = int(os.getenv('NOTIFICATION_QUEUE_CHECK_INTERVAL', 30))
    print(f"[Worker] Starting notification worker, interval={interval}s")
    with app.app_context():
        while True:
            try:
                if notification_service.acquire_distributed_lock(LOCK_KEY, ttl_seconds=interval * 2):
                    try:
                        stats = notification_service.process_pending_notifications()
                        if stats.get('processed'):
                            print(f"[Worker] {datetime.utcnow().isoformat()} processed={stats['processed']} sent={stats['sent']} failed={stats['failed']} retried={stats['retried']}")
                    finally:
                        notification_service.release_distributed_lock(LOCK_KEY)
                else:
                    # Another worker is running
                    pass
            except Exception as e:
                print(f"[Worker] Error: {e}")
            time.sleep(interval)

if __name__ == '__main__':
    main()


