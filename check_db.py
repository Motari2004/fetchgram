"""
Check every place a Facebook/Zernio account ID could be stored in the DB.
Run: python check_accounts.py
Requires DATABASE_URL env var.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

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
    print("❌ DATABASE_URL not set.")
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

# 1. zernio_keys - already confirmed empty, but re-check facebook_account_id column specifically
section("zernio_keys.facebook_account_id (should be empty)")
cur.execute("SELECT id, name, facebook_account_id, facebook_page_name FROM zernio_keys;")
rows = cur.fetchall()
print(f"Rows: {len(rows)}")
for r in rows:
    print(json.dumps(r, indent=2, default=str))

# 2. pipelines - stores its OWN facebook_account_id, independent of zernio_keys
section("pipelines.facebook_account_id / facebook_page_name")
cur.execute("SELECT id, name, profile_username, facebook_account_id, facebook_page_name, zernio_key_id, is_active FROM pipelines;")
rows = cur.fetchall()
print(f"Rows: {len(rows)}")
for r in rows:
    print(json.dumps(r, indent=2, default=str))

# 3. posted_reels - historical posts reference an account indirectly via pipeline_id, but check facebook_post_id/url for evidence of real past posts
section("posted_reels sample (facebook_post_id / facebook_post_url)")
cur.execute("SELECT pipeline_id, reel_url, facebook_post_id, facebook_post_url, status, posted_at FROM posted_reels ORDER BY posted_at DESC LIMIT 10;")
rows = cur.fetchall()
print(f"Rows shown: {len(rows)} (most recent 10)")
for r in rows:
    print(json.dumps(r, indent=2, default=str))

# 4. app_settings - in case zernio_base_url or a default account is stored there
section("app_settings related to zernio")
cur.execute("SELECT setting_key, setting_value FROM app_settings WHERE setting_key ILIKE '%%zernio%%' OR setting_key ILIKE '%%facebook%%' OR setting_key ILIKE '%%account%%';")
rows = cur.fetchall()
print(f"Rows: {len(rows)}")
for r in rows:
    print(json.dumps(r, indent=2, default=str))

cur.close()
conn.close()

print("\nDone. If pipelines still show a facebook_account_id/zernio_key_id,")
print("those pipelines will fail on next run since they point at a key/account")
print("that no longer resolves to anything valid.")