"""
db.py
=====
All SQLite (save file) code.  Two tables:

  state  - exactly ONE row: your wallet, unopened rolls, game clock, stats
  coins  - one row per coin you are looking at (pending) or have kept

Returned coins are deleted (they went back to the bank) and only counted.

"In book" is never chosen by hand: rearrange() recalculates it after every
change.  For each slot (base type, variety, special) the BEST coin you own
goes in the book; everything else is in the jar.
"""
import os
import sqlite3

from flask import g

import config

DB_PATH = os.path.join(os.path.dirname(__file__), config.DATABASE_FILE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    balance_cents      INTEGER NOT NULL,
    unopened_rolls     INTEGER NOT NULL DEFAULT 0,
    business_day       INTEGER NOT NULL DEFAULT 0,   -- game clock for PCGS turnaround
    rolls_opened       INTEGER NOT NULL DEFAULT 0,
    coins_searched     INTEGER NOT NULL DEFAULT 0,
    coins_returned     INTEGER NOT NULL DEFAULT 0,
    total_spent_cents  INTEGER NOT NULL DEFAULT 0,
    grading_fees_cents INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS coins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_key     TEXT NOT NULL,      -- B123 / S:xxx
    variety_key     TEXT,               -- V:xxx or NULL
    is_proof        INTEGER NOT NULL DEFAULT 0,
    true_grade      INTEGER NOT NULL,   -- HIDDEN until PCGS returns it
    est_grade       INTEGER NOT NULL,   -- your fuzzy guess
    official_grade  INTEGER,            -- set when PCGS returns the coin
    status          TEXT NOT NULL,      -- 'pending' (in an open roll) or 'kept'
    roll_no         INTEGER,
    found_day       INTEGER,
    grading_tier    TEXT,               -- key into config.PCGS_TIERS while submitted
    grading_due_day INTEGER,
    in_book         INTEGER NOT NULL DEFAULT 0
);
"""


# ---------------- connection handling (one connection per web request) ----------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    """Create tables and the starting state row the first time the app runs."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        conn = get_db()
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM state").fetchone()[0] == 0:
            conn.execute("INSERT INTO state (id, balance_cents) VALUES (1, ?)",
                         (config.STARTING_BALANCE_CENTS,))
        conn.commit()


def _dicts(rows):
    return [dict(r) for r in rows]


# ---------------- state ----------------
def get_state():
    return dict(get_db().execute("SELECT * FROM state WHERE id = 1").fetchone())


def update_state(**changes):
    """update_state(balance_cents=123, rolls_opened=4) -> sets those columns."""
    cols = ", ".join(f"{k} = ?" for k in changes)
    get_db().execute(f"UPDATE state SET {cols} WHERE id = 1", list(changes.values()))
    get_db().commit()


def add_to_state(**deltas):
    """add_to_state(balance_cents=-50) -> adds/subtracts from current values."""
    cols = ", ".join(f"{k} = {k} + ?" for k in deltas)
    get_db().execute(f"UPDATE state SET {cols} WHERE id = 1", list(deltas.values()))
    get_db().commit()


# ---------------- coins ----------------
def insert_pending(coins, roll_no, day):
    get_db().executemany(
        """INSERT INTO coins (catalog_key, variety_key, is_proof, true_grade, est_grade,
                              status, roll_no, found_day)
           VALUES (:catalog_key, :variety_key, :is_proof, :true_grade, :est_grade,
                   'pending', ?, ?)""".replace("?, ?", f"{roll_no}, {day}"),
        coins)
    get_db().commit()


def pending_coins():
    return _dicts(get_db().execute("SELECT * FROM coins WHERE status='pending' ORDER BY id"))


def get_coin(coin_id):
    row = get_db().execute("SELECT * FROM coins WHERE id = ?", (coin_id,)).fetchone()
    return dict(row) if row else None


def keep_coin(coin_id):
    get_db().execute("UPDATE coins SET status='kept' WHERE id = ?", (coin_id,))
    get_db().commit()
    add_to_state(coins_searched=1)


def return_coin(coin_id):
    """Back to the bank: delete it and refund face value."""
    get_db().execute("DELETE FROM coins WHERE id = ? AND status='pending'", (coin_id,))
    get_db().commit()
    add_to_state(balance_cents=config.RETURN_VALUE_CENTS, coins_searched=1, coins_returned=1)


def kept_coins():
    return _dicts(get_db().execute("SELECT * FROM coins WHERE status='kept' ORDER BY id"))


# ---------------- book vs jar ----------------
def best_sort_key(coin):
    """Higher = better. Official grade beats estimate; ties go to the older find."""
    grade = coin["official_grade"] if coin["official_grade"] is not None else coin["est_grade"]
    return (grade, 1 if coin["official_grade"] is not None else 0, -coin["id"])


def compute_slots(coins):
    """{slot_key: best coin}.  A coin can fill its base slot AND its variety slot."""
    slots = {}
    for c in coins:
        for slot in (c["catalog_key"], c["variety_key"]):
            if slot and (slot not in slots or best_sort_key(c) > best_sort_key(slots[slot])):
                slots[slot] = c
    return slots


def rearrange():
    slots = compute_slots(kept_coins())
    book_ids = {c["id"] for c in slots.values()}
    conn = get_db()
    conn.execute("UPDATE coins SET in_book = 0 WHERE status='kept'")
    conn.executemany("UPDATE coins SET in_book = 1 WHERE id = ?", [(i,) for i in book_ids])
    conn.commit()


def jar_coins():
    return _dicts(get_db().execute(
        "SELECT * FROM coins WHERE status='kept' AND in_book=0 ORDER BY catalog_key, id"))


# ---------------- grading ----------------
def submit_for_grading(coin_id, tier_key, due_day):
    get_db().execute("UPDATE coins SET grading_tier=?, grading_due_day=? WHERE id=?",
                     (tier_key, due_day, coin_id))
    get_db().commit()


def complete_due_grading(today):
    """Reveal the true grade on every submission whose due day has arrived."""
    conn = get_db()
    due = _dicts(conn.execute(
        """SELECT * FROM coins WHERE grading_tier IS NOT NULL
           AND official_grade IS NULL AND grading_due_day <= ?""", (today,)))
    for c in due:
        conn.execute("UPDATE coins SET official_grade = true_grade WHERE id = ?", (c["id"],))
    conn.commit()
    return due


def grading_lists():
    conn = get_db()
    eligible = _dicts(conn.execute(
        "SELECT * FROM coins WHERE status='kept' AND grading_tier IS NULL ORDER BY in_book DESC, catalog_key"))
    in_progress = _dicts(conn.execute(
        "SELECT * FROM coins WHERE grading_tier IS NOT NULL AND official_grade IS NULL ORDER BY grading_due_day"))
    graded = _dicts(conn.execute(
        "SELECT * FROM coins WHERE official_grade IS NOT NULL ORDER BY official_grade DESC"))
    return eligible, in_progress, graded
