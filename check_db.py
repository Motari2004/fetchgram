#!/usr/bin/env python3
"""
Check if the database is connected and has data
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Your Neon Database URL
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def check_database():
    print("=" * 60)
    print("🔍 CHECKING DATABASE CONNECTION")
    print("=" * 60)
    
    try:
        # Try to connect
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Database connection successful!")
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        print(f"\n📊 Tables found: {len(tables)}")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Check scraped_reels data
        cur.execute("""
            SELECT COUNT(*) as count FROM scraped_reels
        """)
        scraped_count = cur.fetchone()
        print(f"\n📹 Scraped reels entries: {scraped_count['count']}")
        
        # Check sync_status data
        cur.execute("""
            SELECT COUNT(*) as count FROM sync_status
        """)
        sync_count = cur.fetchone()
        print(f"🔄 Sync status entries: {sync_count['count']}")
        
        # Show recent data
        cur.execute("""
            SELECT 
                usernames,
                total_profiles,
                total_reels,
                created_at
            FROM scraped_reels 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        recent = cur.fetchall()
        
        if recent:
            print("\n📋 Recent scraped data:")
            for item in recent:
                print(f"  - Usernames: {item['usernames']}")
                print(f"    Profiles: {item['total_profiles']}, Reels: {item['total_reels']}")
                print(f"    Created: {item['created_at']}")
                print()
        else:
            print("\n📭 No scraped data found in database")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()