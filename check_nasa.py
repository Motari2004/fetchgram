#!/usr/bin/env python3
"""
Check NASA profile data in the database
Usage: python check_nasa.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import requests

DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def check_database():
    """Check what's in the database for NASA."""
    
    try:
        print("=" * 60)
        print("🔍 CHECKING NASA PROFILE IN DATABASE")
        print("=" * 60)
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check scraped_reels for NASA
        cur.execute("""
            SELECT 
                id,
                job_id,
                usernames,
                results,
                total_profiles,
                total_reels,
                created_at
            FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = 'nasa'
            )
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = cur.fetchone()
        
        if result:
            print(f"\n✅ Found NASA data in database!")
            print(f"  Job ID: {result['job_id']}")
            print(f"  Created: {result['created_at']}")
            print(f"  Total Profiles: {result['total_profiles']}")
            print(f"  Total Reels: {result['total_reels']}")
            print(f"  Usernames: {result['usernames']}")
            
            # Parse results
            results = result['results']
            for profile in results:
                if profile.get('username') == 'nasa':
                    reels = profile.get('reels', [])
                    print(f"\n📹 Found {len(reels)} reels for @nasa")
                    
                    # Check if captions exist
                    with_captions = 0
                    for i, reel in enumerate(reels[:5], 1):
                        if isinstance(reel, dict):
                            caption = reel.get('caption', '')
                            reel_url = reel.get('url', '')
                            if caption and caption.strip():
                                with_captions += 1
                                print(f"\n  {i}. ✅ HAS CAPTION")
                                print(f"     URL: {reel_url[:60]}...")
                                print(f"     📝 {caption[:100]}...")
                            else:
                                print(f"\n  {i}. ❌ NO CAPTION")
                                print(f"     URL: {reel_url[:60]}...")
                        else:
                            print(f"\n  {i}. ❌ NO CAPTION (string format)")
                            print(f"     URL: {str(reel)[:60]}...")
                    
                    if len(reels) > 5:
                        print(f"\n  ... and {len(reels) - 5} more reels")
                    
                    print(f"\n📊 Captions: {with_captions}/{len(reels)}")
        else:
            print("\n❌ No NASA data found in database")
            print("   You need to scrape NASA first!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_scrape_nasa():
    """Test scraping NASA directly."""
    
    print("\n" + "=" * 60)
    print("🚀 TEST SCRAPING NASA")
    print("=" * 60)
    
    # Check if cookies exist
    try:
        response = requests.get('https://fetchgram-one.vercel.app/api/instagram/cookies_status')
        if response.status_code == 200:
            data = response.json()
            if data.get('has_cookies'):
                print(f"✅ Cookies found for user: {data.get('username')}")
            else:
                print("❌ No cookies found. Please upload cookies.json")
                return
    except Exception as e:
        print(f"❌ Error checking cookies: {e}")
        return
    
    # Option to scrape
    print("\n📝 Do you want to scrape NASA now? (y/n)")
    choice = input().strip().lower()
    
    if choice == 'y':
        try:
            print("\n⏳ Sending scrape request to Render...")
            response = requests.post(
                'https://ig-reels-scraper.onrender.com/api/scrape/start',
                json={
                    "usernames": ["nasa"],
                    "maxReels": 5,
                    "maxScrolls": 3,
                    "sendToVercel": True
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Scrape started! Job ID: {data.get('jobId')}")
                print(f"   Check status: https://ig-reels-scraper.onrender.com/api/scrape/status/{data.get('jobId')}")
                print("\n⏳ Wait a few seconds, then run 'python check_nasa.py' again to see results")
            else:
                print(f"❌ Scrape failed: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    import sys
    
    # Check database
    check_database()
    
    # Option to scrape
    if len(sys.argv) > 1 and sys.argv[1] == '--scrape':
        test_scrape_nasa()