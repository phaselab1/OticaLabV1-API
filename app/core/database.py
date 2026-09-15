import asyncio

from supabase import AsyncClient, acreate_client

from app.core.config import get_settings

_client: AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_supabase() -> AsyncClient:
    global _client

    if _client is None:
        async with _client_lock:
            if _client is None:
                settings = get_settings()
                _client = await acreate_client(settings.supabase_url, settings.supabase_key)

    return _client
