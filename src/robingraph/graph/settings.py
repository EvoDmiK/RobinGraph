"""Environment-only configuration for the Neo4j graph repository."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Neo4jSettings:
    uri: str
    username: str
    password: str
    database: str

    @classmethod
    def from_environment(cls) -> "Neo4jSettings":
        values = {
            "uri": os.getenv("NEO4J_URI", "").strip(),
            "username": os.getenv("NEO4J_USERNAME", "").strip(),
            "password": os.getenv("NEO4J_PASSWORD", ""),
            "database": os.getenv("NEO4J_DATABASE", "neo4j").strip(),
        }
        missing = [name.upper() for name in ("uri", "username", "password") if not values[name]]
        if missing:
            variables = ", ".join(f"NEO4J_{name}" for name in missing)
            raise ValueError(f"Missing required Neo4j environment variables: {variables}")
        if not values["uri"].startswith(("bolt://", "neo4j://", "bolt+s://", "neo4j+s://", "bolt+ssc://", "neo4j+ssc://")):
            raise ValueError("NEO4J_URI must use a Neo4j Bolt URI scheme")
        if not values["database"]:
            raise ValueError("NEO4J_DATABASE must not be empty")
        return cls(**values)
