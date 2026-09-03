#!/usr/bin/env python3
"""
Test script to fetch captions from Instagram reel URLs
Usage: python test_caption.py --url "https://www.instagram.com/reel/xxx/"
       python test_caption.py --username shaazjung --limit 5
"""

import yt_dlp
import json
import argparse
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import re

# Database connection (optional)
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

# ============== CAPTION EXTRACTION ==============

def get_reel_metadata(reel_url):
    """
    Extract all metadata from an Instagram reel.
    Returns: dict with caption, views, likes, comments, etc.
    """
    try:
        print(f"\n📥 Fetching: {reel_url}")
        
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "ignoreerrors": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(reel_url, download=False)
            
            if not info:
                return {"error": "No info extracted"}
            
            # Extract caption/description
            caption = info.get('description') or info.get('title') or ''
            
            # Clean up caption
            caption = caption.strip()
            if len(caption) > 200:
                caption_preview = caption[:200] + "..."
            else:
                caption_preview = caption
            
            # Get other metadata
            result = {
                "url": reel_url,
                "caption": caption,
                "caption_preview": caption_preview,
                "caption_length": len(caption),
                "title": info.get('title', ''),
                "uploader": info.get('uploader', ''),
                "uploader_id": info.get('uploader_id', ''),
                "view_count": info.get('view_count', 0),
                "like_count": info.get('like_count', 0),
                "comment_count": info.get('comment_count', 0),
                "duration": info.get('duration', 0),
                "timestamp": info.get('timestamp'),
                "thumbnail": info.get('thumbnail'),
                "webpage_url": info.get('webpage_url', reel_url),
                "extractor": info.get('extractor', ''),
                "success": True
            }
            
            # Get direct video URL
            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]
            if entries:
                target = entries[0]
                formats = target.get("formats", [])
                if formats:
                    for fmt in formats:
                        if fmt.get("ext") == "mp4" and fmt.get("acodec") != "none":
                            result["video_url"] = fmt.get("url")
                            break
                    if "video_url" not in result:
                        result["video_url"] = formats[0].get("url") if formats else None
            
            return result
            
    except yt_dlp.utils.DownloadError as e:
        return {"error": f"Download error: {str(e)}", "url": reel_url, "success": False}
    except Exception as e:
        return {"error": f"Error: {str(e)}", "url": reel_url, "success": False}

def test_single_url(url):
    """Test a single reel URL."""
    print("=" * 70)
    print("🔍 TESTING SINGLE URL")
    print("=" * 70)
    
    result = get_reel_metadata(url)
    
    if result.get("success"):
        print("\n✅ SUCCESS!")
        print(f"  Uploader: {result.get('uploader', 'N/A')}")
        print(f"  Views: {result.get('view_count', 0):,}")
        print(f"  Likes: {result.get('like_count', 0):,}")
        print(f"  Comments: {result.get('comment_count', 0):,}")
        print(f"  Duration: {result.get('duration', 0)} seconds")
        print(f"\n  📝 CAPTION:")
        print("  " + "-" * 50)
        print(f"  {result.get('caption_preview', 'No caption')}")
        if result.get('caption_length', 0) > 200:
            print(f"  ... (full caption is {result.get('caption_length', 0)} characters)")
        print("  " + "-" * 50)
        
        if result.get('video_url'):
            print(f"\n  🎬 Video URL: {result.get('video_url')[:80]}...")
        
        return result
    else:
        print(f"\n❌ FAILED: {result.get('error')}")
        return None

def test_multiple_urls(urls):
    """Test multiple reel URLs."""
    print("=" * 70)
    print(f"🔍 TESTING {len(urls)} URLs")
    print("=" * 70)
    
    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n📹 [{i}/{len(urls)}]")
        result = get_reel_metadata(url)
        
        if result.get("success"):
            print(f"  ✅ {result.get('uploader', 'Unknown')}")
            print(f"  📝 {result.get('caption_preview', 'No caption')[:60]}...")
            print(f"  👁️ {result.get('view_count', 0):,} views")
            results.append(result)
        else:
            print(f"  ❌ {result.get('error')}")
    
    print("\n" + "=" * 70)
    print(f"📊 SUMMARY: {len(results)}/{len(urls)} successful")
    print("=" * 70)
    
    return results

def test_username(username, limit=5):
    """Test reels for a specific username from database."""
    print("=" * 70)
    print(f"🔍 TESTING USERNAME: @{username} (limit: {limit})")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get reels for this username
        cur.execute("""
            SELECT results FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC
            LIMIT 1
        """, (username,))
        
        result = cur.fetchone()
        if not result:
            print(f"❌ No data found for @{username}")
            return []
        
        results = result['results']
        reels = []
        for profile in results:
            if profile.get('username') == username:
                reels = profile.get('reels', [])
                break
        
        if not reels:
            print(f"❌ No reels found for @{username}")
            return []
        
        print(f"📹 Found {len(reels)} reels for @{username}")
        
        # Test first N reels
        test_reels = reels[:limit]
        urls = []
        for reel in test_reels:
            if isinstance(reel, str):
                urls.append(reel)
            elif isinstance(reel, dict):
                urls.append(reel.get('url'))
        
        return test_multiple_urls(urls)
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def test_database_captions(username):
    """Check what captions are already in the database."""
    print("=" * 70)
    print(f"🔍 CHECKING DATABASE CAPTIONS: @{username}")
    print("=" * 70)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT results FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC
            LIMIT 1
        """, (username,))
        
        result = cur.fetchone()
        if not result:
            print(f"❌ No data found for @{username}")
            return
        
        results = result['results']
        for profile in results:
            if profile.get('username') == username:
                reels = profile.get('reels', [])
                print(f"\n📹 {len(reels)} reels found")
                
                has_caption_count = 0
                for i, reel in enumerate(reels[:10], 1):
                    if isinstance(reel, dict):
                        caption = reel.get('caption', '')
                        if caption and caption.strip():
                            has_caption_count += 1
                            print(f"  {i}. ✅ {caption[:60]}...")
                        else:
                            print(f"  {i}. ❌ No caption")
                    else:
                        print(f"  {i}. ❌ No caption (string format)")
                
                print(f"\n📊 Captions in database: {has_caption_count}/{len(reels[:10])} checked")
                break
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()

def save_caption_to_db(reel_url, caption):
    """Save a caption back to the database (helper function)."""
    # This would update the specific reel in the database
    pass

# ============== MAIN ==============

def main():
    parser = argparse.ArgumentParser(
        description='Test script to fetch captions from Instagram reels'
    )
    parser.add_argument('--url', '-u', help='Single reel URL to test')
    parser.add_argument('--urls', '-f', help='File with URLs (one per line)')
    parser.add_argument('--username', '-un', help='Username to test from database')
    parser.add_argument('--limit', '-l', type=int, default=5, help='Number of reels to test (default: 5)')
    parser.add_argument('--check-db', action='store_true', help='Check existing captions in database')
    parser.add_argument('--all', action='store_true', help='Test all reels for the username')
    
    args = parser.parse_args()
    
    if args.check_db:
        username = args.username or 'shaazjung'
        test_database_captions(username)
        sys.exit(0)
    
    if args.url:
        test_single_url(args.url)
    
    elif args.urls:
        with open(args.urls, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        test_multiple_urls(urls)
    
    elif args.username:
        if args.all:
            test_username(args.username, limit=9999)
        else:
            test_username(args.username, limit=args.limit)
    
    else:
        # Interactive mode
        print("=" * 70)
        print("🔍 INSTAGRAM CAPTION TESTER")
        print("=" * 70)
        print("\nOptions:")
        print("  1. Test a single URL")
        print("  2. Test from database username")
        print("  3. Check database captions")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            url = input("Enter Instagram reel URL: ").strip()
            test_single_url(url)
        elif choice == '2':
            username = input("Enter username (e.g., shaazjung): ").strip() or 'shaazjung'
            limit = input("Enter limit (default 5): ").strip() or '5'
            test_username(username, int(limit))
        elif choice == '3':
            username = input("Enter username (e.g., shaazjung): ").strip() or 'shaazjung'
            test_database_captions(username)
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()