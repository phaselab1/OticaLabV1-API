from datetime import UTC, datetime, timedelta

from postgrest.types import CountMethod
from supabase import AsyncClient

TABLE = "login_attempts"


class LoginAttemptRepository:
    def __init__(self, db: AsyncClient) -> None:
        self.db = db

    async def count_recent_failures(self, email: str, *, window: timedelta) -> int:
        since = (datetime.now(UTC) - window).isoformat()
        response = (
            await self.db.table(TABLE)
            .select("id", count=CountMethod.exact)
            .eq("email", email)
            .eq("success", False)
            .gte("attempted_at", since)
            .execute()
        )
        return response.count or 0

    async def record(self, email: str, *, success: bool) -> None:
        await self.db.table(TABLE).insert({"email": email, "success": success}).execute()
