# PostgreSQL ingest control plane

RobinGraph keeps source-of-record ingestion metadata in PostgreSQL. Neo4j stores query-oriented domain nodes, but does not duplicate `SourceRecord`, `SourceDataset`, `SourceRelease`, `IngestionRun`, quarantine, or Korean pipeline activation state.

## Database isolation

Production and test use different databases and login roles on the same PostgreSQL server:

| Environment | Database | Login role | Schema |
|---|---|---|---|
| production | `robingraph` | `robingraph_app` | `ingest` |
| test | `robingraph_test` | `robingraph_test_app` | `ingest` |

Each login must have access only to its own database. Do not reuse a production connection file when running test migrations.

## Configuration

The commands read these environment variables:

- `ROBINGRAPH_PG_HOST`
- `ROBINGRAPH_PG_PORT` (defaults to `5432`)
- `ROBINGRAPH_PG_DATABASE`
- `ROBINGRAPH_PG_SCHEMA` (defaults to `ingest`)
- `ROBINGRAPH_PG_USERNAME`
- `ROBINGRAPH_PG_PASSWORD`
- `ROBINGRAPH_PG_SSLMODE` (defaults to `prefer`)

Credentials remain outside the repository. For the current hosts they are stored in mode-`0600` files under `~/.config/robingraph/`.

## Apply and verify

Apply to test first:

```bash
set -a
source /Users/kimdove/.config/robingraph/test-postgres.env
set +a
uv run --locked robingraph migrate-postgres
uv run --locked robingraph verify-postgres
```

The migration runner takes a transaction-scoped advisory lock, records SHA-256 checksums in `ingest._schema_migration`, and rejects edits to an already-applied migration. Schema changes are forward-only.

The schema retains a generic transactional outbox for future domain events. Source records do not create outbox events and there is no SourceRecord-to-Neo4j projector command.

## Ownership boundary

- PostgreSQL owns source datasets and releases, immutable source records, ingestion runs, quarantine history, active release pointers, and the transactional outbox.
- Neo4j owns query-optimized domain nodes. Domain nodes carry `dataset_id`, `source_record_ids`, and `policy_status` provenance identifiers, while their full source/control records stay in PostgreSQL.
- n8n orchestrates collection and retries, calls the internal PostgreSQL ingest API for source/control facts, and writes validated domain projections to Neo4j.
- Korean lineage reads obtain the active allowed dataset ID from PostgreSQL and bind it into parameterized Neo4j queries. A missing or revoked active dataset fails closed.
