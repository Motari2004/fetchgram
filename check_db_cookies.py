# check_db_cookies.py
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def check_cookies():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check user_cookies table
    cur.execute("SELECT user_id, username, created_at, updated_at FROM user_cookies")
    users = cur.fetchall()
    
    print("📊 Users in database:")
    for user in users:
        print(f"  User ID: {user['user_id']}")
        print(f"  Username: {user['username']}")
        print(f"  Created: {user['created_at']}")
        print(f"  Updated: {user['updated_at']}")
        print()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_cookies()