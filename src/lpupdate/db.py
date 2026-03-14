from __future__ import annotations

import json
from typing import Any

import psycopg

from .schema import SCHEMA_SQL


def connect(database_url: str):
    return psycopg.connect(database_url)


def apply_schema(database_url: str) -> None:
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()


def upsert_company(cur, canonical_name: str) -> int:
    cur.execute(
        """
        INSERT INTO companies (canonical_name)
        VALUES (%s)
        ON CONFLICT (canonical_name)
        DO UPDATE SET canonical_name = EXCLUDED.canonical_name
        RETURNING id
        """,
        (canonical_name,),
    )
    return cur.fetchone()[0]


def upsert_email_message(cur, record: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO email_messages (
          gmail_message_id, gmail_thread_id, subject, from_address, to_addresses,
          label_names, received_at, snippet, body_text, body_html, raw_payload
        ) VALUES (
          %(gmail_message_id)s, %(gmail_thread_id)s, %(subject)s, %(from_address)s, %(to_addresses)s::jsonb,
          %(label_names)s::jsonb, %(received_at)s, %(snippet)s, %(body_text)s, %(body_html)s, %(raw_payload)s::jsonb
        )
        ON CONFLICT (gmail_message_id)
        DO UPDATE SET
          gmail_thread_id = EXCLUDED.gmail_thread_id,
          subject = EXCLUDED.subject,
          from_address = EXCLUDED.from_address,
          to_addresses = EXCLUDED.to_addresses,
          label_names = EXCLUDED.label_names,
          received_at = EXCLUDED.received_at,
          snippet = EXCLUDED.snippet,
          body_text = EXCLUDED.body_text,
          body_html = EXCLUDED.body_html,
          raw_payload = EXCLUDED.raw_payload
        RETURNING id
        """,
        {
            'gmail_message_id': record['gmail_message_id'],
            'gmail_thread_id': record.get('gmail_thread_id'),
            'subject': record.get('subject'),
            'from_address': record.get('from_address'),
            'to_addresses': json.dumps(record.get('to_addresses', [])),
            'label_names': json.dumps(record.get('label_names', [])),
            'received_at': record.get('received_at'),
            'snippet': record.get('snippet'),
            'body_text': record.get('body_text'),
            'body_html': record.get('body_html'),
            'raw_payload': json.dumps(record.get('raw_payload', {})),
        },
    )
    return cur.fetchone()[0]


def list_updates(database_url: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect(database_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                  q.id,
                  c.canonical_name AS company_name,
                  q.report_period_label,
                  q.received_at,
                  q.summary,
                  q.metrics_json
                FROM quarterly_updates q
                LEFT JOIN companies c ON c.id = q.company_id
                ORDER BY q.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())


def get_update(database_url: str, update_id: int) -> dict[str, Any] | None:
    with connect(database_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                  q.id,
                  c.canonical_name AS company_name,
                  q.report_period_label,
                  q.report_quarter,
                  q.report_year,
                  q.received_at,
                  q.summary,
                  q.metrics_json,
                  q.highlights_json,
                  q.risks_json,
                  q.asks_json,
                  q.people_json,
                  e.subject,
                  e.from_address,
                  e.gmail_message_id
                FROM quarterly_updates q
                LEFT JOIN companies c ON c.id = q.company_id
                LEFT JOIN email_messages e ON e.id = q.email_message_id
                WHERE q.id = %s
                """,
                (update_id,),
            )
            return cur.fetchone()


def list_companies(database_url: str) -> list[dict[str, Any]]:
    with connect(database_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                  c.id,
                  c.canonical_name,
                  COUNT(q.id) AS update_count,
                  MAX(q.received_at) AS latest_received_at
                FROM companies c
                LEFT JOIN quarterly_updates q ON q.company_id = c.id
                GROUP BY c.id, c.canonical_name
                ORDER BY c.canonical_name ASC
                """
            )
            return list(cur.fetchall())


def get_company_updates(database_url: str, company_name: str) -> list[dict[str, Any]]:
    with connect(database_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                  q.id,
                  c.canonical_name AS company_name,
                  q.report_period_label,
                  q.report_quarter,
                  q.report_year,
                  q.received_at,
                  q.summary,
                  q.metrics_json,
                  q.highlights_json,
                  q.asks_json,
                  e.subject,
                  e.gmail_message_id
                FROM quarterly_updates q
                JOIN companies c ON c.id = q.company_id
                LEFT JOIN email_messages e ON e.id = q.email_message_id
                WHERE lower(c.canonical_name) = lower(%s)
                ORDER BY q.received_at DESC, q.id DESC
                """,
                (company_name,),
            )
            return list(cur.fetchall())


def get_company_metrics(database_url: str, company_name: str) -> list[dict[str, Any]]:
    with connect(database_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                  c.canonical_name AS company_name,
                  q.id AS update_id,
                  q.report_period_label,
                  q.report_quarter,
                  q.report_year,
                  q.received_at,
                  q.metrics_json
                FROM quarterly_updates q
                JOIN companies c ON c.id = q.company_id
                WHERE lower(c.canonical_name) = lower(%s)
                ORDER BY q.received_at DESC, q.id DESC
                """,
                (company_name,),
            )
            return list(cur.fetchall())


def upsert_quarterly_update(cur, email_message_id: int, company_id: int | None, record: dict[str, Any]) -> int:
    cur.execute(
        """
        INSERT INTO quarterly_updates (
          company_id, email_message_id, report_period_label, report_quarter, report_year,
          received_at, summary, metrics_json, highlights_json, risks_json,
          asks_json, people_json, confidence_json, parser_version
        ) VALUES (
          %(company_id)s, %(email_message_id)s, %(report_period_label)s, %(report_quarter)s, %(report_year)s,
          %(received_at)s, %(summary)s, %(metrics_json)s::jsonb, %(highlights_json)s::jsonb, %(risks_json)s::jsonb,
          %(asks_json)s::jsonb, %(people_json)s::jsonb, %(confidence_json)s::jsonb, %(parser_version)s
        )
        ON CONFLICT (email_message_id)
        DO UPDATE SET
          company_id = EXCLUDED.company_id,
          report_period_label = EXCLUDED.report_period_label,
          report_quarter = EXCLUDED.report_quarter,
          report_year = EXCLUDED.report_year,
          received_at = EXCLUDED.received_at,
          summary = EXCLUDED.summary,
          metrics_json = EXCLUDED.metrics_json,
          highlights_json = EXCLUDED.highlights_json,
          risks_json = EXCLUDED.risks_json,
          asks_json = EXCLUDED.asks_json,
          people_json = EXCLUDED.people_json,
          confidence_json = EXCLUDED.confidence_json,
          parser_version = EXCLUDED.parser_version
        RETURNING id
        """,
        {
            'company_id': company_id,
            'email_message_id': email_message_id,
            'report_period_label': record.get('report_period_label'),
            'report_quarter': record.get('report_quarter'),
            'report_year': record.get('report_year'),
            'received_at': record.get('received_at'),
            'summary': record.get('summary'),
            'metrics_json': json.dumps(record.get('metrics_json', {})),
            'highlights_json': json.dumps(record.get('highlights_json', [])),
            'risks_json': json.dumps(record.get('risks_json', [])),
            'asks_json': json.dumps(record.get('asks_json', [])),
            'people_json': json.dumps(record.get('people_json', [])),
            'confidence_json': json.dumps(record.get('confidence_json', {})),
            'parser_version': record.get('parser_version', 'v0'),
        },
    )
    return cur.fetchone()[0]
