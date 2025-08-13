from __future__ import annotations

import threading
import uuid
from typing import Dict, Optional, Tuple, List

import psycopg

from app.schemas.reading import ReadingResponse, DrawnCard, Card, GroupOrder, InterpretResponse


class ReadingRepository:
    """In-memory repository for readings. Thread-safe for simple use cases."""

    def __init__(self) -> None:
        self._store: Dict[str, ReadingResponse] = {}
        self._lock = threading.Lock()
        self._interpretations: Dict[Tuple[str, str, str, bool], InterpretResponse] = {}
        self._details: Dict[Tuple[str, str, bool], List[str]] = {}

    def create(self, reading: ReadingResponse) -> str:
        reading_id = str(uuid.uuid4())
        reading.id = reading_id
        with self._lock:
            self._store[reading_id] = reading
        return reading_id

    def get(self, reading_id: str) -> Optional[ReadingResponse]:
        with self._lock:
            return self._store.get(reading_id)

    # --- interpretations cache ---
    def get_interpretation(self, reading_id: str, lang: str, style: str, use_llm: bool) -> Optional[InterpretResponse]:
        key = (reading_id, lang, style, use_llm)
        with self._lock:
            return self._interpretations.get(key)

    def save_interpretation(self, data: InterpretResponse, lang: str, style: str, use_llm: bool) -> None:
        key = (data.id, lang, style, use_llm)
        with self._lock:
            self._interpretations[key] = data

    # --- per-card details cache (LLM) ---
    def get_details(self, reading_id: str, lang: str, use_llm: bool) -> Optional[List[str]]:
        key = (reading_id, lang, use_llm)
        with self._lock:
            return self._details.get(key)

    def save_details(self, reading_id: str, lang: str, use_llm: bool, details: List[str]) -> None:
        key = (reading_id, lang, use_llm)
        with self._lock:
            self._details[key] = list(details)


class PostgresReadingRepository:
    def __init__(self, db_url: str) -> None:
        self._db_url = db_url
        self._init_schema()

    def _init_schema(self) -> None:
        ddl_readings = """
        CREATE TABLE IF NOT EXISTS readings (
            id UUID PRIMARY KEY,
            question TEXT NOT NULL,
            ord_a TEXT NOT NULL,
            ord_b TEXT NOT NULL,
            ord_c TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        ddl_cards = """
        CREATE TABLE IF NOT EXISTS reading_cards (
            id BIGSERIAL PRIMARY KEY,
            reading_id UUID REFERENCES readings(id) ON DELETE CASCADE,
            position INT NOT NULL,
            is_reversed BOOLEAN NOT NULL,
            card_id INT NOT NULL
        );
        """
        ddl_interp = """
        CREATE TABLE IF NOT EXISTS interpretations (
            id BIGSERIAL PRIMARY KEY,
            reading_id UUID REFERENCES readings(id) ON DELETE CASCADE,
            lang TEXT NOT NULL,
            style TEXT NOT NULL,
            use_llm BOOLEAN NOT NULL,
            summary TEXT NOT NULL,
            advices JSONB NOT NULL,
            llm_used BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (reading_id, lang, style, use_llm)
        );
        """
        ddl_details = """
        CREATE TABLE IF NOT EXISTS interpretation_details (
            id BIGSERIAL PRIMARY KEY,
            reading_id UUID REFERENCES readings(id) ON DELETE CASCADE,
            lang TEXT NOT NULL,
            use_llm BOOLEAN NOT NULL,
            details JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (reading_id, lang, use_llm)
        );
        """
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(ddl_readings)
                cur.execute(ddl_cards)
                cur.execute(ddl_interp)
                cur.execute(ddl_details)
            conn.commit()

    def create(self, reading: ReadingResponse) -> str:
        rid = str(uuid.uuid4())
        order_vals = [g.value if isinstance(g, GroupOrder) else str(g) for g in reading.order]
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO readings (id, question, ord_a, ord_b, ord_c) VALUES (%s, %s, %s, %s, %s)",
                    (rid, reading.question, order_vals[0], order_vals[1], order_vals[2]),
                )
                for item in reading.items:
                    cur.execute(
                        "INSERT INTO reading_cards (reading_id, position, is_reversed, card_id) VALUES (%s, %s, %s, %s)",
                        (rid, item.position, item.is_reversed, item.card.id),
                    )
            conn.commit()
        reading.id = rid
        return rid

    def get(self, reading_id: str) -> Optional[ReadingResponse]:
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, question, ord_a, ord_b, ord_c FROM readings WHERE id=%s",
                    (reading_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                rid, question, a, b, c = row
                order = [GroupOrder(a), GroupOrder(b), GroupOrder(c)]
                cur.execute(
                    "SELECT position, is_reversed, card_id FROM reading_cards WHERE reading_id=%s ORDER BY position",
                    (reading_id,),
                )
                items_rows = cur.fetchall()
        items = [
            DrawnCard(position=pos, is_reversed=is_rev, card=Card(id=card_id, name="", arcana=""))
            for (pos, is_rev, card_id) in items_rows
        ]
        return ReadingResponse(id=str(rid), question=question, order=order, count=len(items), items=items)

    # --- interpretations cache ---
    def get_interpretation(self, reading_id: str, lang: str, style: str, use_llm: bool) -> Optional[InterpretResponse]:
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT summary, advices, llm_used FROM interpretations WHERE reading_id=%s AND lang=%s AND style=%s AND use_llm=%s",
                    (reading_id, lang, style, use_llm),
                )
                row = cur.fetchone()
                if not row:
                    return None
                summary, advices, llm_used = row
        return InterpretResponse(id=reading_id, lang=lang, summary=summary, positions=[], advices=list(advices), llm_used=llm_used)

    def save_interpretation(self, data: InterpretResponse, lang: str, style: str, use_llm: bool) -> None:
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO interpretations (reading_id, lang, style, use_llm, summary, advices, llm_used)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (reading_id, lang, style, use_llm)
                    DO UPDATE SET summary=EXCLUDED.summary, advices=EXCLUDED.advices, llm_used=EXCLUDED.llm_used
                    """,
                    (data.id, lang, style, use_llm, data.summary, data.advices, data.llm_used),
                )
            conn.commit()

    # --- per-card details cache (LLM) ---
    def get_details(self, reading_id: str, lang: str, use_llm: bool) -> Optional[List[str]]:
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT details FROM interpretation_details WHERE reading_id=%s AND lang=%s AND use_llm=%s",
                    (reading_id, lang, use_llm),
                )
                row = cur.fetchone()
                if not row:
                    return None
                details = row[0]
        return list(details) if isinstance(details, list) else None

    def save_details(self, reading_id: str, lang: str, use_llm: bool, details: List[str]) -> None:
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO interpretation_details (reading_id, lang, use_llm, details)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (reading_id, lang, use_llm)
                    DO UPDATE SET details=EXCLUDED.details
                    """,
                    (reading_id, lang, use_llm, details),
                )
            conn.commit()


