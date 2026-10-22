"""SQLite access. The app opens the built DB read-only."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE shops (
    shop_id TEXT PRIMARY KEY,
    name TEXT,
    name_is_real INTEGER NOT NULL,     -- 1 only for the 112 shops with Instagram or website
    address TEXT,
    area TEXT,                         -- location_label: neighbourhood derived from coordinates
    lat REAL,
    lon REAL,
    categories TEXT NOT NULL,          -- JSON list of activity categories
    phone TEXT,                        -- ASCII digits; all phones in the dataset are fake
    instagram TEXT,
    website TEXT,
    weekly_hours TEXT,                 -- raw JSON; NULL when not registered
    fast_delivery INTEGER,             -- 1 / 0 / NULL (unknown)
    payment TEXT NOT NULL,             -- JSON list of {provider, channel}
    n_offers INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE products (
    rowid INTEGER PRIMARY KEY,
    product_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    title_redacted INTEGER NOT NULL,
    brand TEXT,
    category TEXT,
    model TEXT,
    images TEXT NOT NULL,              -- JSON list of URLs
    specs TEXT NOT NULL,               -- JSON list of {section, key, value}
    n_shops INTEGER NOT NULL DEFAULT 0,
    min_price INTEGER,                 -- over offers with price_status ok
    median_price INTEGER
);

CREATE TABLE offers (
    offer_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    shop_id TEXT NOT NULL,
    seller_title TEXT,
    description TEXT,
    price_raw INTEGER,                 -- as recorded, Toman
    price INTEGER,                     -- usable price, NULL unless status ok or suspicious
    price_status TEXT NOT NULL,        -- ok | suspicious | call | invalid
    price_changed_at TEXT,             -- ISO UTC; last recorded price change, not stock
    warranty_kind TEXT,                -- yes | none | NULL (unknown)
    warranty_months INTEGER,
    warranty_text TEXT
);
CREATE INDEX offers_product ON offers(product_id);
CREATE INDEX offers_shop ON offers(shop_id);
"""


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
