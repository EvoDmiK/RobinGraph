"""Audio review/control records use the existing PostgreSQL ingest connection."""
from contextlib import contextmanager
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .store import IngestionStore


class AudioStore(IngestionStore):
    @contextmanager
    def session(self, *, collect=False):
        with self._connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
            # A single bounded download holds this lock; concurrent n8n runs never duplicate provider requests.
            if collect:
                cursor.execute("SELECT pg_try_advisory_xact_lock(hashtext('robingraph-audio-collection')) AS acquired")
                if not cursor.fetchone()['acquired']:
                    raise BlockingIOError('Audio collection is already running')
            yield cursor

    @staticmethod
    def get(cursor, candidate_id):
        cursor.execute('SELECT * FROM audio_recording_candidate WHERE id=%s FOR UPDATE', (candidate_id,))
        return cursor.fetchone()

    @staticmethod
    def save(cursor, candidate_id, science, title, status, data):
        cursor.execute('''INSERT INTO audio_recording_candidate (id,scientific_name,file_title,status,data)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET
            status=EXCLUDED.status,data=EXCLUDED.data,updated_at=now()''',
            (candidate_id,science,title,status,Jsonb(data)))

    @staticmethod
    def cooldown(cursor):
        cursor.execute("SELECT max((data->>'retry_at')::timestamptz) AS until FROM audio_recording_candidate WHERE status='deferred'")
        return cursor.fetchone()['until']

    def pending_species(self):
        with self.session() as cursor:
            cursor.execute("SELECT DISTINCT scientific_name FROM audio_recording_candidate WHERE status IN ('awaiting_review','approved','published')")
            return {row['scientific_name'] for row in cursor.fetchall()}

    def published(self, *, scientific_name=None, file_name=None):
        with self.session() as cursor:
            cursor.execute('''SELECT * FROM audio_recording_candidate WHERE status='published'
                AND (%s::text IS NULL OR scientific_name=%s)
                AND (%s::text IS NULL OR data->>'file_name'=%s) ORDER BY id LIMIT 3''',
                (scientific_name,scientific_name,file_name,file_name))
            return cursor.fetchall()
