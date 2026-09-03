#!/usr/bin/env python3
"""
Test script to check if scraped data has captions
Usage: python test_captions.py --username natgeo
       python test_captions.py --all
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import argparse
import sys

# Your Neon PostgreSQL database URL
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

def check_captions_for_username(username):
    """Check if a username's scraped data has captions."""
    
    try:
        print(f"\n🔍 Checking captions for @{username}")
        print("=" * 60)
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get scraped data for this username
        cur.execute("""
            SELECT results, created_at, usernames 
            FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC
            LIMIT 1
        """, (username,))
        
        result = cur.fetchone()
        
        if not result:
            print(f"❌ No scraped data found for @{username}")
            return
        
        print(f"📅 Scraped at: {result['created_at']}")
        print(f"👥 Usernames in this job: {result['usernames']}")
        print("-" * 60)
        
        # Find the profile
        data = result['results']
        profile_data = None
        for profile in data:
            if profile.get('username') == username:
                profile_data = profile
                break
        
        if not profile_data:
            print(f"❌ Profile @{username} not found in results")
            return
        
        reels = profile_data.get('reels', [])
        total_reels = len(reels)
        
        print(f"📹 Total reels: {total_reels}")
        print("-" * 60)
        
        if total_reels == 0:
            print("⚠️ No reels found")
            return
        
        # Check each reel for captions
        has_caption_count = 0
        no_caption_count = 0
        string_format_count = 0
        
        print("\n📝 REEL DETAILS:\n")
        
        for i, reel in enumerate(reels[:10], 1):  # Show first 10
            if isinstance(reel, dict):
                reel_url = reel.get('url', 'N/A')
                caption = reel.get('caption', '')
                
                if caption and caption.strip():
                    has_caption_count += 1
                    status = "✅ HAS CAPTION"
                    caption_preview = caption[:80] + "..." if len(caption) > 80 else caption
                else:
                    no_caption_count += 1
                    status = "❌ NO CAPTION"
                    caption_preview = ""
                
                print(f"{i}. {status}")
                print(f"   URL: {reel_url[:60]}...")
                if caption_preview:
                    print(f"   📝 {caption_preview}")
                print()
                
            else:
                string_format_count += 1
                print(f"{i}. ❌ STRING FORMAT (no caption field)")
                print(f"   URL: {str(reel)[:60]}...")
                print()
        
        if total_reels > 10:
            print(f"... and {total_reels - 10} more reels\n")
        
        # Summary
        print("=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        print(f"  Total reels: {total_reels}")
        print(f"  ✅ Has caption: {has_caption_count}")
        print(f"  ❌ No caption: {no_caption_count}")
        print(f"  📄 String format: {string_format_count}")
        print("=" * 60)
        
        # Recommendation
        if has_caption_count > 0:
            print(f"✅ @{username} has captions! Ready for posting with real captions.")
        else:
            print(f"⚠️ @{username} has NO captions. Run: python update_captions.py --username {username}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def list_all_usernames():
    """List all usernames in the database."""
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT unnest(usernames) as username 
            FROM scraped_reels 
            WHERE usernames IS NOT NULL AND array_length(usernames, 1) > 0
            ORDER BY username
        """)
        
        usernames = [row[0] for row in cur.fetchall()]
        
        print("=" * 60)
        print("👥 ALL USERNAMES IN DATABASE")
        print("=" * 60)
        for i, username in enumerate(usernames, 1):
            print(f"  {i}. @{username}")
        print("=" * 60)
        print(f"Total: {len(usernames)} usernames")
        
        cur.close()
        conn.close()
        
        return usernames
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def check_all_usernames():
    """Check captions for all usernames."""
    
    usernames = list_all_usernames()
    
    for username in usernames:
        check_captions_for_username(username)
        print("\n" + "-" * 60 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Check if scraped data has captions')
    parser.add_argument('--username', '-u', help='Username to check (e.g., natgeo)')
    parser.add_argument('--all', '-a', action='store_true', help='Check all usernames')
    parser.add_argument('--list', '-l', action='store_true', help='List all usernames')
    
    args = parser.parse_args()
    
    if args.list:
        list_all_usernames()
        sys.exit(0)
    
    if args.all:
        check_all_usernames()
        sys.exit(0)
    
    if args.username:
        check_captions_for_username(args.username)
    else:
        # Interactive mode
        print("=" * 60)
        print("🔍 CAPTION CHECKER")
        print("=" * 60)
        print("\nOptions:")
        print("  1. Check a specific username")
        print("  2. List all usernames")
        print("  3. Check all usernames")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            username = input("Enter username (e.g., natgeo): ").strip()
            if username:
                check_captions_for_username(username)
        elif choice == '2':
            list_all_usernames()
        elif choice == '3':
            check_all_usernames()
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()