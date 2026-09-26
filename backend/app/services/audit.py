from datetime import datetime, timezone
from app.db.mongo import get_database

async def record_audit(
    action: str,
    user_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
):
    await get_database().audit_logs.insert_one({
        "action": action,
        "user_id": user_id,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc),
    })
