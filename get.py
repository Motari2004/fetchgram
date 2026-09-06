import psycopg2
from datetime import datetime, timezone, timedelta
import pytz

# Your database URL
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def get_all_scheduled_posts():
    """Get all scheduled posts from the database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Get all scheduled posts
        cur.execute("""
            SELECT 
                id,
                reel_url,
                scheduled_time,
                status,
                caption,
                pipeline_id,
                created_at,
                posted_at,
                error_message
            FROM scheduled_posts
            ORDER BY scheduled_time ASC
        """)
        
        results = cur.fetchall()
        
        if not results:
            print("ℹ️ No scheduled posts found.")
            return
        
        print("=" * 80)
        print(f"📅 TOTAL SCHEDULED POSTS: {len(results)}")
        print("=" * 80)
        
        for row in results:
            post_id, reel_url, scheduled_time, status, caption, pipeline_id, created_at, posted_at, error_message = row
            
            # Format times
            if scheduled_time:
                # Convert to local time
                local_time = scheduled_time.astimezone()
                time_str = local_time.strftime('%Y-%m-%d %I:%M:%S %p')
                day = local_time.strftime('%A')
            else:
                time_str = "Unknown"
                day = "Unknown"
            
            # Status emoji
            status_map = {
                'pending': '⏳ PENDING',
                'posted': '✅ POSTED',
                'failed': '❌ FAILED'
            }
            status_display = status_map.get(status, status.upper())
            
            print(f"\n📌 Post ID: {post_id[:8]}...")
            print(f"   📹 URL: {reel_url[:80]}...")
            print(f"   📅 Scheduled: {time_str} ({day})")
            print(f"   📊 Status: {status_display}")
            if caption:
                print(f"   📝 Caption: {caption[:100]}...")
            if posted_at:
                posted_local = posted_at.astimezone()
                print(f"   ✅ Posted at: {posted_local.strftime('%Y-%m-%d %I:%M:%S %p')}")
            if error_message:
                print(f"   ❌ Error: {error_message[:100]}")
            print(f"   🏗️ Pipeline ID: {pipeline_id}")
            print("-" * 60)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def get_pipeline_scheduled_posts(pipeline_id):
    """Get scheduled posts for a specific pipeline."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                reel_url,
                scheduled_time,
                status,
                caption,
                posted_at
            FROM scheduled_posts
            WHERE pipeline_id = %s
            ORDER BY scheduled_time ASC
        """, (pipeline_id,))
        
        results = cur.fetchall()
        
        if not results:
            print(f"ℹ️ No scheduled posts found for pipeline {pipeline_id[:8]}...")
            return
        
        print(f"\n📅 Pipeline {pipeline_id[:8]}... - {len(results)} scheduled post(s):")
        print("=" * 70)
        
        for row in results:
            reel_url, scheduled_time, status, caption, posted_at = row
            
            if scheduled_time:
                local_time = scheduled_time.astimezone()
                time_str = local_time.strftime('%Y-%m-%d %I:%M:%S %p')
            else:
                time_str = "Unknown"
            
            status_emoji = "✅" if status == "posted" else "⏳" if status == "pending" else "❌"
            
            # Calculate time remaining
            if scheduled_time and status == 'pending':
                now = datetime.now(timezone.utc)
                if scheduled_time > now:
                    remaining = scheduled_time - now
                    hours_remaining = remaining.total_seconds() / 3600
                    if hours_remaining < 1:
                        minutes_remaining = int(remaining.total_seconds() / 60)
                        time_remaining = f"({minutes_remaining} minutes)"
                    else:
                        time_remaining = f"({hours_remaining:.1f} hours)"
                else:
                    time_remaining = "⚠️ OVERDUE!"
            else:
                time_remaining = ""
            
            print(f"{status_emoji} {status.upper()}: {time_str} {time_remaining}")
            print(f"   📹 {reel_url[:60]}...")
            if caption:
                print(f"   📝 {caption[:80]}...")
            if posted_at:
                posted_local = posted_at.astimezone()
                print(f"   📤 Posted at: {posted_local.strftime('%Y-%m-%d %I:%M:%S %p')}")
            print("-" * 50)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def get_upcoming_posts(hours=24):
    """Get posts scheduled in the next X hours."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 🔥 FIX: Use UTC time for comparison
        cur.execute("""
            SELECT 
                reel_url,
                scheduled_time,
                status,
                caption
            FROM scheduled_posts
            WHERE status = 'pending'
            AND scheduled_time <= NOW() + INTERVAL '%s hours'
            AND scheduled_time > NOW()
            ORDER BY scheduled_time ASC
        """, (hours,))
        
        results = cur.fetchall()
        
        if not results:
            print(f"ℹ️ No posts scheduled in the next {hours} hours.")
            return
        
        print(f"\n⏰ Upcoming posts in the next {hours} hours:")
        print("=" * 70)
        
        now = datetime.now(timezone.utc)  # 🔥 FIX: Use timezone-aware now
        
        for row in results:
            reel_url, scheduled_time, status, caption = row
            
            if scheduled_time:
                local_time = scheduled_time.astimezone()
                time_str = local_time.strftime('%Y-%m-%d %I:%M:%S %p')
                # Calculate time remaining
                if scheduled_time > now:
                    remaining = scheduled_time - now
                    hours_remaining = remaining.total_seconds() / 3600
                    if hours_remaining < 1:
                        minutes_remaining = int(remaining.total_seconds() / 60)
                        time_remaining = f"{minutes_remaining} minutes"
                    else:
                        time_remaining = f"{hours_remaining:.1f} hours"
                else:
                    time_remaining = "OVERDUE!"
            else:
                time_str = "Unknown"
                time_remaining = "Unknown"
            
            print(f"🕐 {time_str} ({time_remaining})")
            print(f"   📹 {reel_url[:60]}...")
            if caption:
                print(f"   📝 {caption[:80]}...")
            print("-" * 50)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def get_post_count():
    """Get summary counts of scheduled posts."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM scheduled_posts
            GROUP BY status
        """)
        
        results = cur.fetchall()
        
        print("\n📊 SUMMARY:")
        print("=" * 40)
        for status, count in results:
            emoji = "✅" if status == "posted" else "⏳" if status == "pending" else "❌"
            print(f"   {emoji} {status.upper()}: {count}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

# ============== RUN THE CHECKS ==============

if __name__ == "__main__":
    # Your pipeline ID from the success message
    PIPELINE_ID = "c580d6de-a577-4dbe-8cda-7875297c9d01"
    
    print("\n" + "="*80)
    print("📊 SCHEDULED POSTS REPORT")
    print("="*80 + "\n")
    
    # 1. Get summary counts
    get_post_count()
    
    # 2. Get all scheduled posts
    print("\n📋 ALL SCHEDULED POSTS:")
    print("-" * 80)
    get_all_scheduled_posts()
    
    # 3. Get posts for specific pipeline
    print(f"\n📋 PIPELINE {PIPELINE_ID[:8]}... SCHEDULED POSTS:")
    print("-" * 80)
    get_pipeline_scheduled_posts(PIPELINE_ID)
    
    # 4. Get upcoming posts
    print("\n📋 UPCOMING POSTS (NEXT 24 HOURS):")
    print("-" * 80)
    get_upcoming_posts(24)
    
    print("\n" + "="*80)
    print("✅ REPORT COMPLETE")
    print("="*80)