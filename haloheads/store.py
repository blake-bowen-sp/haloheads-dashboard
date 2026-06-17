import json
import os
import sqlite3
from typing import Protocol


class Store(Protocol):
    def match_exists(self, image_hash: str) -> bool: ...
    def game_exists(self, game_hash: str) -> bool: ...
    def add_match(self, match: dict, players: list[dict]) -> None: ...
    def all_player_stats(self) -> list[dict]: ...
    def all_matches(self) -> list[dict]: ...
    def get_match(self, match_id: str) -> dict | None: ...
    def recent_matches(self, limit: int = 50) -> list[dict]: ...


def _decode_match(row: dict) -> dict:
    """Parse the sqlite ``tabs`` TEXT column back into a list (no-op for Firestore)."""
    tabs = row.get("tabs")
    if isinstance(tabs, str):
        row["tabs"] = json.loads(tabs) if tabs else None
    return row


class SqliteStore:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                gametype TEXT,
                map TEXT,
                winning_team TEXT,
                source_image TEXT,
                uploaded_at TEXT,
                analyzed_at TEXT,
                image_hash TEXT UNIQUE,
                game_hash TEXT,
                tabs TEXT
            );
            CREATE TABLE IF NOT EXISTS player_stats (
                row_hash TEXT PRIMARY KEY,
                match_id TEXT,
                gamertag TEXT,
                clan_tag TEXT,
                team TEXT,
                result TEXT,
                score INTEGER,
                kills INTEGER,
                assists INTEGER,
                deaths INTEGER,
                kd REAL,
                gametype TEXT,
                map TEXT,
                created_at TEXT
            );
        """)
        # Additive migration for databases created before the tabs column existed.
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(matches)")}
        if "tabs" not in cols:
            self._conn.execute("ALTER TABLE matches ADD COLUMN tabs TEXT")
        self._conn.commit()

    def match_exists(self, image_hash: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM matches WHERE image_hash = ?", (image_hash,)
        )
        return cur.fetchone() is not None

    def game_exists(self, game_hash: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM matches WHERE game_hash = ? LIMIT 1", (game_hash,)
        )
        return cur.fetchone() is not None

    def add_match(self, match: dict, players: list[dict]) -> None:
        tabs = match.get("tabs")
        row = {**match, "tabs": json.dumps(tabs) if tabs is not None else None}
        with self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO matches
                   (match_id, gametype, map, winning_team, source_image,
                    uploaded_at, analyzed_at, image_hash, game_hash, tabs)
                   VALUES (:match_id, :gametype, :map, :winning_team, :source_image,
                           :uploaded_at, :analyzed_at, :image_hash, :game_hash, :tabs)""",
                row,
            )
            self._conn.executemany(
                """INSERT OR IGNORE INTO player_stats
                   (row_hash, match_id, gamertag, clan_tag, team, result,
                    score, kills, assists, deaths, kd, gametype, map, created_at)
                   VALUES (:row_hash, :match_id, :gamertag, :clan_tag, :team, :result,
                           :score, :kills, :assists, :deaths, :kd, :gametype, :map, :created_at)""",
                players,
            )

    def all_player_stats(self) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM player_stats")
        return [dict(row) for row in cur.fetchall()]

    def all_matches(self) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM matches")
        return [dict(row) for row in cur.fetchall()]

    def get_match(self, match_id: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _decode_match(dict(row))

    def recent_matches(self, limit: int = 50) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM matches ORDER BY uploaded_at DESC LIMIT ?", (limit,)
        )
        return [_decode_match(dict(row)) for row in cur.fetchall()]


class FirestoreStore:
    def __init__(self, project: str | None = None) -> None:
        import google.cloud.firestore as firestore
        self.db = firestore.Client(project=project)

    def match_exists(self, image_hash: str) -> bool:
        results = (
            self.db.collection("matches")
            .where("image_hash", "==", image_hash)
            .limit(1)
            .get()
        )
        return len(results) > 0

    def game_exists(self, game_hash: str) -> bool:
        results = (
            self.db.collection("matches")
            .where("game_hash", "==", game_hash)
            .limit(1)
            .get()
        )
        return len(results) > 0

    def add_match(self, match: dict, players: list[dict]) -> None:
        self.db.collection("matches").document(match["match_id"]).set(match)
        for player in players:
            self.db.collection("player_stats").document(player["row_hash"]).set(player)

    def all_player_stats(self) -> list[dict]:
        return [doc.to_dict() for doc in self.db.collection("player_stats").stream()]

    def all_matches(self) -> list[dict]:
        return [doc.to_dict() for doc in self.db.collection("matches").stream()]

    def get_match(self, match_id: str) -> dict | None:
        doc = self.db.collection("matches").document(match_id).get()
        return doc.to_dict() if doc.exists else None

    def recent_matches(self, limit: int = 50) -> list[dict]:
        import google.cloud.firestore as firestore
        docs = (
            self.db.collection("matches")
            .order_by("uploaded_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]


def get_store() -> Store:
    backend = os.environ.get("STORE_BACKEND", "sqlite")
    if backend == "sqlite":
        path = os.environ.get("SQLITE_PATH", "./.localdata/stats.db")
        return SqliteStore(path)
    if backend == "firestore":
        project = os.environ.get("GCP_PROJECT")
        return FirestoreStore(project=project)
    raise ValueError(f"Unknown STORE_BACKEND: {backend!r}")
