"""
debug_all.py — Full diagnostic for the Fetchgram / Buffer integration.
Run:  python debug_all.py
"""

import os
import sys
import traceback
from datetime import datetime
from urllib.parse import urlparse

# ---------- load .env ----------
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k] = v
except FileNotFoundError:
    pass

import psycopg2
from psycopg2.extras import RealDictCursor


def sep(title):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def sub(title):
    print("\n--- " + title + " ---")


# ============================================================
print(f"Debug report generated at {datetime.utcnow().isoformat()}Z")

DATABASE_URL = os.environ.get('DATABASE_URL')

# ============================================================
sep("ENVIRONMENT")
print(f"Python:            {sys.version.split()[0]}")
print(f"Working directory: {os.getcwd()}")
print(f"DATABASE_URL set:  {bool(DATABASE_URL)}")
if DATABASE_URL:
    try:
        u = urlparse(DATABASE_URL)
        print(f"  host: {u.hostname}")
        print(f"  port: {u.port}")
        print(f"  db:   {u.path.lstrip('/')}")
        print(f"  user: {u.username}")
    except Exception as e:
        print(f"  (parse failed: {e})")

# ============================================================
if not DATABASE_URL:
    print("\n❌ DATABASE_URL is not set. Cannot continue.")
    sys.exit(1)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print("\n" + "=" * 78)
    print("  DATABASE CONNECTION")
    print("=" * 78)
    print("Postgres:", cur.fetchone()[0][:80])
    cur.execute("SELECT current_database(), current_user;")
    db, user = cur.fetchone()
    print(f"Database: {db}")
    print(f"User:     {user}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"\n❌ DB connection failed: {e}")
    traceback.print_exc()
    sys.exit(1)


def run_query(sql, params=None, label=""):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


# ============================================================
sep("TABLES PRESENT")
rows = run_query("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = [r['table_name'] for r in rows]
for t in tables:
    print(f"  • {t}")

expected = [
    'user_cookies', 'scraped_reels', 'pipelines', 'posted_reels',
    'pipeline_runs', 'reel_cache', 'sync_status', 'scheduled_posts',
    'pending_posts', 'zernio_keys', 'app_settings',
    'buffer_keys', 'buffer_channels'
]
missing = [t for t in expected if t not in tables]
print("\nMissing: " + (", ".join(missing) if missing else "none ✅"))


# ============================================================
for tbl in ('buffer_keys', 'buffer_channels', 'pipelines', 'posted_reels'):
    sub(f"columns of {tbl}")
    try:
        rows = run_query("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (tbl,))
        if not rows:
            print(f"❌ {tbl} does not exist")
        else:
            for r in rows:
                print(f"  {r['column_name']:30s} {r['data_type']:25s} "
                      f"null={r['is_nullable']:3s}")
    except Exception as e:
        print(f"❌ {tbl} columns failed: {e}")


# ============================================================
sep("BUFFER KEYS")
try:
    rows = run_query("""
        SELECT id, name, api_key, organization_id, organization_name,
               daily_limit, usage_count, is_active, created_at
        FROM buffer_keys
        ORDER BY created_at DESC
    """)
    print(f"Count: {len(rows)}")
    for r in rows:
        k = r['api_key'] or ''
        masked = (k[:8] + '...' + k[-4:]) if len(k) > 12 else '***'
        print(f"\n  id:          {r['id']}")
        print(f"  name:        {r['name']}")
        print(f"  api_key:     {masked}")
        print(f"  org_id:      {r['organization_id']}")
        print(f"  org_name:    {r['organization_name']}")
        print(f"  is_active:   {r['is_active']}")
        print(f"  created_at:  {r['created_at']}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("BUFFER CHANNELS")
try:
    rows = run_query("""
        SELECT id, buffer_key_id, channel_id, name, display_name,
               service, is_disconnected
        FROM buffer_channels
        ORDER BY buffer_key_id, service, display_name
    """)
    print(f"Count: {len(rows)}")
    for r in rows:
        print(f"\n  id:              {r['id']}")
        print(f"  buffer_key_id:   {r['buffer_key_id']}")
        print(f"  channel_id:      {r['channel_id']}")
        print(f"  name:            {r['name']}")
        print(f"  display_name:    {r['display_name']}")
        print(f"  service:         {r['service']}")
        print(f"  is_disconnected: {r['is_disconnected']}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("PIPELINES")
try:
    rows = run_query("""
        SELECT id, name, profile_username, platform,
               facebook_account_id, zernio_key_id,
               buffer_key_id, buffer_channel_id, buffer_channel_name,
               daily_limit, is_active, total_posted, created_at
        FROM pipelines
        ORDER BY created_at DESC
    """)
    print(f"Count: {len(rows)}")
    for r in rows:
        print(f"\n  id:                  {r['id']}")
        print(f"  name:                {r['name']}")
        print(f"  profile_username:    {r['profile_username']}")
        print(f"  platform:            {r['platform']!r}")
        print(f"  facebook_account_id: {r['facebook_account_id']!r}")
        print(f"  zernio_key_id:       {r['zernio_key_id']}")
        print(f"  buffer_key_id:       {r['buffer_key_id']}")
        print(f"  buffer_channel_id:   {r['buffer_channel_id']}")
        print(f"  buffer_channel_name: {r['buffer_channel_name']!r}")
        print(f"  is_active:           {r['is_active']}")
        print(f"  total_posted:        {r['total_posted']}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("PIPELINE ↔ BUFFER INTEGRITY")
try:
    rows = run_query("""
        SELECT
            p.id, p.name, p.platform,
            p.buffer_key_id, p.buffer_channel_id,
            bk.id AS key_exists, bk.is_active AS key_active,
            bc.channel_id AS channel_exists,
            bc.service AS channel_service,
            bc.is_disconnected AS channel_disconnected
        FROM pipelines p
        LEFT JOIN buffer_keys bk ON bk.id = p.buffer_key_id
        LEFT JOIN buffer_channels bc
               ON bc.buffer_key_id = p.buffer_key_id
              AND bc.channel_id = p.buffer_channel_id
        WHERE p.platform IN ('twitter', 'tiktok')
        ORDER BY p.created_at DESC
    """)
    if not rows:
        print("(no twitter/tiktok pipelines)")
    else:
        problems = 0
        for p in rows:
            issues = []
            if not p['buffer_key_id']:
                issues.append("buffer_key_id is NULL")
            elif not p['key_exists']:
                issues.append(f"key {p['buffer_key_id']} does NOT exist")
            elif not p['key_active']:
                issues.append(f"key {p['buffer_key_id']} exists but INACTIVE")

            if not p['buffer_channel_id']:
                issues.append("buffer_channel_id is NULL")
            elif not p['channel_exists']:
                issues.append(f"channel {p['buffer_channel_id']} not found on key")
            elif p['channel_disconnected']:
                issues.append(f"channel {p['buffer_channel_id']} DISCONNECTED")
            elif p['channel_service'] != p['platform']:
                issues.append(
                    f"channel service={p['channel_service']!r} "
                    f"but platform={p['platform']!r}"
                )

            mark = "✅" if not issues else "❌"
            print(f"\n  {mark} {p['name']} ({p['id']})")
            print(f"     platform:          {p['platform']}")
            print(f"     buffer_key_id:     {p['buffer_key_id']}")
            print(f"     buffer_channel_id: {p['buffer_channel_id']}")
            for i in issues:
                print(f"       ❌ {i}")
            if issues:
                problems += 1

        print(f"\nSummary: {problems} problem pipeline(s) out of {len(rows)}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("RECENT SCHEDULED FAILURES (last 10)")
try:
    rows = run_query("""
        SELECT sp.id, sp.reel_url, sp.status, sp.scheduled_time,
               sp.error_message, p.name AS pipeline_name, p.platform
        FROM scheduled_posts sp
        JOIN pipelines p ON sp.pipeline_id = p.id
        WHERE sp.status = 'failed'
        ORDER BY sp.scheduled_time DESC
        LIMIT 10
    """)
    if not rows:
        print("(none)")
    for r in rows:
        err = (r['error_message'] or '')[:160]
        print(f"\n  {r['scheduled_time']} | {r['platform']} | {r['pipeline_name']}")
        print(f"     id:   {r['id']}")
        print(f"     reel: {(r['reel_url'] or '')[:80]}")
        print(f"     err:  {err}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("PENDING / PROCESSING SCHEDULED POSTS")
try:
    rows = run_query("""
        SELECT sp.id, sp.status, sp.scheduled_time, sp.caption,
               p.name AS pipeline_name, p.platform
        FROM scheduled_posts sp
        JOIN pipelines p ON sp.pipeline_id = p.id
        WHERE sp.status IN ('pending', 'processing')
        ORDER BY sp.scheduled_time ASC
        LIMIT 30
    """)
    print(f"Count: {len(rows)}")
    for r in rows:
        cap = (r['caption'] or '')[:50]
        print(f"  {r['scheduled_time']} | {r['status']:10s} | "
              f"{r['platform']:8s} | {r['pipeline_name']:30s} | {cap}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("CONSTRAINTS on buffer_channels (needed for ON CONFLICT)")
try:
    rows = run_query("""
        SELECT conname, pg_get_constraintdef(oid) AS defn
        FROM pg_constraint
        WHERE conrelid = 'buffer_channels'::regclass
    """)
    if not rows:
        print("❌ buffer_channels has NO constraints")
    for r in rows:
        print(f"  {r['conname']}")
        print(f"     {r['defn']}")
except Exception as e:
    print(f"❌ {e}")


# ============================================================
sep("LIVE BUFFER API PROBE")
import requests

try:
    keys = run_query("""
        SELECT id, name, api_key, is_active FROM buffer_keys
    """)
except Exception as e:
    keys = []
    print(f"❌ could not load keys: {e}")

if not keys:
    print("(no stored buffer keys)")
else:
    for k in keys:
        print(f"\n  Key: {k['name']} ({k['id']})  active={k['is_active']}")
        if not k['api_key']:
            print("    ❌ api_key empty")
            continue
        try:
            r = requests.post(
                "https://api.buffer.com",
                json={"query": "query { account { id organizations { id name } } }"},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {k['api_key']}",
                },
                timeout=15,
            )
            print(f"    [account] HTTP {r.status_code}")
            body = r.json()
            if "errors" in body:
                print(f"      ❌ errors: {body['errors']}")
                continue
            orgs = (body.get("data", {}).get("account") or {}).get("organizations") or []
            print(f"      orgs: {[(o.get('id'), o.get('name')) for o in orgs]}")
            for o in orgs:
                r2 = requests.post(
                    "https://api.buffer.com",
                    json={
                        "query": """
                            query GetChannels($input: ChannelsInput!) {
                              channels(input: $input) {
                                id name displayName service isDisconnected
                              }
                            }
                        """,
                        "variables": {"input": {"organizationId": o["id"]}},
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {k['api_key']}",
                    },
                    timeout=15,
                )
                print(f"    [channels org={o['id']}] HTTP {r2.status_code}")
                body2 = r2.json()
                if "errors" in body2:
                    print(f"      ❌ errors: {body2['errors']}")
                    continue
                for c in body2.get("data", {}).get("channels") or []:
                    print(f"      • {c.get('service'):8s} | "
                          f"{(c.get('displayName') or c.get('name') or ''):30s} | "
                          f"id={c.get('id')} | disconnected={c.get('isDisconnected')}")
        except Exception as e:
            print(f"    ❌ probe failed: {e}")


# ============================================================
sep("DONE")
print("Copy everything above and send it.")