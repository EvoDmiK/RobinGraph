"""Optional, bounded-age disk cache for public species source metadata."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
import time


@lru_cache(maxsize=256)
def _lock(key):
    return Lock()


def _path(key):
    root = os.getenv('ROBINGRAPH_SPECIES_CACHE_ROOT', '').strip()
    return Path(root) / (hashlib.sha256(key.encode()).hexdigest() + '.json') if root else None


def read_cached(key):
    path = _path(key)
    if path is None:
        return None
    try:
        if path.stat().st_size > 2_000_000:
            return None
        record = json.loads(path.read_text())
        if (record['key'] == key and isinstance(record['data'], dict)
                and 0 <= time.time() - record['saved_at'] < 86400):
            return record['data']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def remember(key, load):
    with _lock(key):
        value = read_cached(key)
        if value is not None:
            return value
        value = load()
        path = _path(key)
        if path is not None:
            temporary = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    json.dump({'key': key, 'saved_at': time.time(), 'data': value}, stream, ensure_ascii=False)
                os.replace(temporary, path)
            except (OSError, ValueError, TypeError):
                pass  # A cache failure must not hide an otherwise valid source response.
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
        return value
