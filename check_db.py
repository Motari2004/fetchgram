"""
Quick DB inspection script.
Run: python check_db.py
Requires DATABASE_URL env var (same one your Flask app uses).
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# Load .env if present (same pattern as your app)
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)
except FileNotFoundError:
    pass

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not set. Set it in your shell or .env file.")
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

# 1. Zernio keys - the main thing we care about
section("ZERNIO_KEYS TABLE (raw rows)")
cur.execute("SELECT id, name, api_key, facebook_account_id, facebook_page_name, daily_limit, usage_count, is_active, created_at, updated_at FROM zernio_keys ORDER BY created_at DESC;")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    masked_key = (r['api_key'][:8] + '...' + r['api_key'][-4:]) if r['api_key'] and len(r['api_key']) > 12 else '***'
    print(json.dumps({**r, 'api_key': masked_key}, indent=2, default=str))

# 2. Pipelines referencing zernio keys (in case of orphaned FK references)
section("PIPELINES referencing zernio_key_id")
cur.execute("SELECT id, name, profile_username, zernio_key_id, is_active FROM pipelines WHERE zernio_key_id IS NOT NULL;")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")
for r in rows:
    print(json.dumps(r, indent=2, default=str))

# 3. Sanity check: does Postgres itself still have any zernio_keys at all?
section("COUNT CHECK")
cur.execute("SELECT COUNT(*) as total FROM zernio_keys;")
print("Total zernio_keys rows in DB:", cur.fetchone()['total'])

cur.execute("SELECT COUNT(*) as total FROM zernio_keys WHERE is_active = TRUE;")
print("Active zernio_keys rows in DB:", cur.fetchone()['total'])

cur.close()
conn.close()

print("\nDone. If ZERNIO_KEYS table shows 0 rows here but /api/zernio/accounts")
print("still returns accounts, that CONFIRMS the accounts are coming from stale")
print("in-memory cache on a Vercel lambda instance, not the database.")
