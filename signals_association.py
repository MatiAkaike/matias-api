"""Asociación explícita entre la sesión de chat y el contexto de Signals.

La autoridad del contexto analítico es el SDK de Signals. El chat conserva su
propio ``session_id`` funcional. La asociación registra, SOLO con consentimiento,
la correspondencia entre ambos. La IP NO se usa como identificador de persona:
la vinculación se hace por identificadores seudónimos explícitos.
"""

from __future__ import annotations

from typing import Any

import database


async def init_signals_associations() -> None:
    pool = await database._get_pg_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals_associations (
                chat_session_id TEXT PRIMARY KEY,
                signals_tenant_id TEXT DEFAULT '',
                signals_visitor_id TEXT DEFAULT '',
                signals_session_id TEXT DEFAULT '',
                consent_version TEXT DEFAULT '',
                associated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )


async def record_signals_association(
    chat_session_id: str,
    signals_tenant_id: str,
    signals_visitor_id: str,
    signals_session_id: str,
    consent_version: str = "",
) -> None:
    """Registra la asociación de forma idempotente (última asociación gana)."""
    pool = await database._get_pg_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO signals_associations
                (chat_session_id, signals_tenant_id, signals_visitor_id,
                 signals_session_id, consent_version, associated_at)
            VALUES ($1,$2,$3,$4,$5,NOW())
            ON CONFLICT (chat_session_id) DO UPDATE SET
                signals_tenant_id = EXCLUDED.signals_tenant_id,
                signals_visitor_id = EXCLUDED.signals_visitor_id,
                signals_session_id = EXCLUDED.signals_session_id,
                consent_version = EXCLUDED.consent_version,
                associated_at = NOW()
            """,
            chat_session_id, signals_tenant_id, signals_visitor_id,
            signals_session_id, consent_version,
        )


async def get_signals_association(chat_session_id: str) -> dict[str, Any] | None:
    pool = await database._get_pg_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM signals_associations WHERE chat_session_id=$1",
            chat_session_id,
        )
        return dict(row) if row else None
