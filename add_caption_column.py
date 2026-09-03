#!/usr/bin/env python3
"""
Script to add caption column to database tables
Usage: python add_caption_column.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# Your Neon PostgreSQL database URL
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def add_caption_columns():
    """Add caption column to posted_reels and reel_cache tables."""
    
    try:
        print("🔌 Connecting to Neon PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("=" * 60)
        print("🔍 ADDING CAPTION COLUMNS")
        print("=" * 60)
        
        # 1. Add caption column to posted_reels
        print("\n📋 1. Adding caption to posted_reels...")
        try:
            cur.execute("""
                ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS caption TEXT;
            """)
            conn.commit()
            print("   ✅ caption column added to posted_reels")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 2. Add caption column to reel_cache
        print("\n📋 2. Adding caption to reel_cache...")
        try:
            cur.execute("""
                ALTER TABLE reel_cache ADD COLUMN IF NOT EXISTS caption TEXT;
            """)
            conn.commit()
            print("   ✅ caption column added to reel_cache")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 3. Verify columns were added
        print("\n📋 3. Verifying columns...")
        
        # Check posted_reels
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'posted_reels' 
            AND column_name = 'caption';
        """)
        result = cur.fetchone()
        if result:
            print(f"   ✅ posted_reels.caption: {result[1]}")
        else:
            print("   ❌ posted_reels.caption not found")
        
        # Check reel_cache
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'reel_cache' 
            AND column_name = 'caption';
        """)
        result = cur.fetchone()
        if result:
            print(f"   ✅ reel_cache.caption: {result[1]}")
        else:
            print("   ❌ reel_cache.caption not found")
        
        # 4. Show current state of tables
        print("\n📊 4. Current table structure:")
        
        # posted_reels columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'posted_reels' 
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        print("\n   posted_reels columns:")
        for col in columns:
            print(f"     - {col[0]}: {col[1]}")
        
        # reel_cache columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'reel_cache' 
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        print("\n   reel_cache columns:")
        for col in columns:
            print(f"     - {col[0]}: {col[1]}")
        
        print("\n" + "=" * 60)
        print("✅ Database update complete!")
        
        cur.close()
        conn.close()
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ CONNECTION ERROR: {e}")
        print("   Please check your DATABASE_URL")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def check_caption_column():
    """Check if caption columns exist."""
    
    try:
        print("🔌 Connecting to Neon PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("=" * 60)
        print("🔍 CHECKING CAPTION COLUMNS")
        print("=" * 60)
        
        tables = ['posted_reels', 'reel_cache']
        
        for table in tables:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND column_name = 'caption';
            """, (table,))
            result = cur.fetchone()
            
            if result:
                print(f"✅ {table}.caption: {result[1]} (EXISTS)")
            else:
                print(f"❌ {table}.caption: MISSING")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        check_caption_column()
    else:
        add_caption_columns()