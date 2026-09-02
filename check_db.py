import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Your corrected Neon PostgreSQL connection string
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def check_database():
    """Simple script to check what's in the scraped_reels table."""
    
    try:
        # Connect to the database
        print("🔌 Connecting to Neon PostgreSQL...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("=" * 70)
        print("🔍 CHECKING NEON POSTGRESQL DATABASE")
        print("=" * 70)
        
        # 1. Check if table exists
        print("\n📋 1. CHECKING TABLES...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        print(f"Tables found: {tables}")
        
        if 'scraped_reels' not in tables:
            print("❌ scraped_reels table does NOT exist!")
            print("   Creating scraped_reels table...")
            
            # Create the table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scraped_reels (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    usernames TEXT[] NOT NULL,
                    results JSONB NOT NULL,
                    status TEXT DEFAULT 'completed',
                    total_profiles INTEGER DEFAULT 0,
                    total_reels INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, job_id)
                );
            """)
            
            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_reels_user_id 
                ON scraped_reels(user_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_reels_created_at 
                ON scraped_reels(created_at DESC);
            """)
            
            conn.commit()
            print("✅ scraped_reels table created successfully!")
            print("   Table is empty. You need to scrape data or insert test data.")
            conn.close()
            return
        
        print("✅ scraped_reels table exists!")
        
        # 2. Count total rows
        print("\n📊 2. COUNTING ROWS...")
        cur.execute("SELECT COUNT(*) as count FROM scraped_reels")
        total_count = cur.fetchone()['count']
        print(f"Total rows in scraped_reels: {total_count}")
        
        if total_count == 0:
            print("❌ Table is EMPTY! No data found.")
            print("   You need to scrape data first or insert test data.")
            
            # Option: Insert test data
            print("\n💡 Want to insert test data? (y/n)")
            response = input().strip().lower()
            if response == 'y':
                print("Inserting test data...")
                cur.execute("""
                    INSERT INTO scraped_reels (user_id, job_id, usernames, results, total_profiles, total_reels)
                    VALUES (
                        'test-user-' || gen_random_uuid()::text,
                        'test-job-' || gen_random_uuid()::text,
                        ARRAY['nasa', 'natgeo'],
                        '[
                            {"username": "nasa", "status": "ok", "reels": ["https://www.instagram.com/reel/test1/", "https://www.instagram.com/reel/test2/"]},
                            {"username": "natgeo", "status": "ok", "reels": ["https://www.instagram.com/reel/test3/"]}
                        ]'::jsonb,
                        2,
                        3
                    )
                """)
                conn.commit()
                print("✅ Test data inserted!")
                # Re-count
                cur.execute("SELECT COUNT(*) as count FROM scraped_reels")
                total_count = cur.fetchone()['count']
                print(f"Total rows now: {total_count}")
        
        # 3. Get all user_ids
        print("\n👤 3. CHECKING USERS...")
        cur.execute("""
            SELECT DISTINCT user_id, COUNT(*) as count 
            FROM scraped_reels 
            GROUP BY user_id
        """)
        users = cur.fetchall()
        print(f"Users with data:")
        for user in users:
            print(f"  - {user['user_id']}: {user['count']} entries")
        
        # 4. Get latest entries (with full details)
        print("\n📝 4. LATEST ENTRIES (5 most recent)...")
        cur.execute("""
            SELECT 
                id,
                user_id,
                job_id,
                usernames,
                status,
                total_profiles,
                total_reels,
                created_at,
                updated_at
            FROM scraped_reels 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        latest_entries = cur.fetchall()
        
        if latest_entries:
            for i, entry in enumerate(latest_entries, 1):
                print(f"\n  Entry #{i}:")
                print(f"    ID: {entry['id']}")
                print(f"    User ID: {entry['user_id']}")
                print(f"    Job ID: {entry['job_id']}")
                print(f"    Usernames: {entry['usernames']}")
                print(f"    Status: {entry['status']}")
                print(f"    Profiles: {entry['total_profiles']}")
                print(f"    Reels: {entry['total_reels']}")
                print(f"    Created: {entry['created_at']}")
        else:
            print("  No entries found")
        
        # 5. Check if there's data with results
        print("\n📦 5. CHECKING RESULTS JSON...")
        cur.execute("""
            SELECT 
                job_id,
                results,
                total_profiles,
                total_reels
            FROM scraped_reels 
            WHERE results IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result_entry = cur.fetchone()
        
        if result_entry:
            print(f"  Job: {result_entry['job_id']}")
            print(f"  Profiles: {result_entry['total_profiles']}")
            print(f"  Reels: {result_entry['total_reels']}")
            print(f"\n  Sample Results (first 2 profiles):")
            results = result_entry['results']
            if results and len(results) > 0:
                for i, profile in enumerate(results[:2], 1):
                    username = profile.get('username', 'unknown')
                    reels = profile.get('reels', [])
                    print(f"    Profile {i}: {username} - {len(reels)} reels")
                    for reel in reels[:2]:
                        print(f"      - {reel}")
        
        # 6. Count total reels across all profiles
        print("\n📈 6. SUMMARY STATS...")
        cur.execute("""
            SELECT 
                COUNT(*) as total_jobs,
                COALESCE(SUM(total_profiles), 0) as all_profiles,
                COALESCE(SUM(total_reels), 0) as all_reels
            FROM scraped_reels
        """)
        stats = cur.fetchone()
        print(f"  Total Jobs: {stats['total_jobs']}")
        print(f"  Total Profiles: {stats['all_profiles']}")
        print(f"  Total Reels: {stats['all_reels']}")
        
        print("\n" + "=" * 70)
        print("✅ Database check complete!")
        
        conn.close()
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ CONNECTION ERROR: {e}")
        print("   Please check your DATABASE_URL and make sure the database is accessible.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()