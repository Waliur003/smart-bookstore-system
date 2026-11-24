import copy
import json
import os
import tempfile
from pathlib import Path
from filelock import FileLock

COLLECTIONS = ('accounts', 'sessions', 'books', 'orders', 'reviews', 'audit', 'taboo_words', 'policies')

class Repository:
    def __init__(self, filename):
        self.path = Path(filename)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + '.lock', timeout=10)
        if not self.path.exists():
            self.commit(lambda db: None)

    def _load(self):
        if not self.path.exists():
            return {k: [] for k in COLLECTIONS}
        with self.path.open(encoding='utf-8') as f:
            data = json.load(f)
        for key in COLLECTIONS:
            data.setdefault(key, [])
        return data

    def read(self, collection=None):
        with self.lock:
            data = self._load()
            return copy.deepcopy(data if collection is None else data[collection])

    def commit(self, change):
        with self.lock:
            data = copy.deepcopy(self._load())
            result = change(data)
            self._validate(data)
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent,
                                                 prefix='.snapshot-', suffix='.tmp', delete=False) as f:
                    temp_path = f.name
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, self.path)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
            return result

    @staticmethod
    def _validate(db):
        for group in ('accounts', 'books', 'orders', 'reviews'):
            ids = [x['id'] for x in db[group]]
            if len(ids) != len(set(ids)):
                raise ValueError(f'Duplicate IDs in {group}')
        accounts = {a['id'] for a in db['accounts']}
        books = {b['id'] for b in db['books']}
        for a in db['accounts']:
            if a['role'] not in ('RC', 'VC', 'SU') or a['status'] not in ('active', 'suspended'):
                raise ValueError('Invalid account role/status')
            if not isinstance(a['balance_cents'], int):
                raise ValueError('Balance must be stored as integer cents')
        for b in db['books']:
            if b['stock'] < 0 or b['price_cents'] < 0:
                raise ValueError('Invalid book price/stock')
        for order in db['orders']:
            if order['account_id'] not in accounts:
                raise ValueError('Orphaned order')
            for line in order['lines']:
                if line['book_id'] not in books:
                    raise ValueError('Orphaned order line')
        for r in db['reviews']:
            if r['account_id'] not in accounts or r['book_id'] not in books:
                raise ValueError('Orphaned review')
