#!/usr/bin/env python3
"""
Publish unreel videos from database to Facebook via Zernio
Usage: python publish.py --pipeline PIPELINE_ID --limit 2
"""

import requests
import json
import argparse
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import yt_dlp
import os
import re
from datetime import datetime

# ============== CONFIGURATION ==============
# Get your API key from Zernio dashboard
ZERNIO_API_KEY = "sk_48ad5dd4a9d9bd8e2561633862dc1708b3fb2013645023fde617921bd065a037"
ZERNIO_BASE_URL = "https://zernio.com/api/v1"

# Your Neon PostgreSQL database URL
DATABASE_URL = "postgresql://neondb_owner:npg_Ft7zdnlh1jWL@ep-quiet-fire-ay6p33yj-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

# ============== DATABASE FUNCTIONS ==============

def get_db_connection():
    """Get a connection to the Neon PostgreSQL database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

def get_unposted_reels_from_db(pipeline_id=None, username=None, limit=2):
    """
    Get unposted reels from database.
    If pipeline_id provided, uses that pipeline's configuration.
    If username provided, gets reels for that username directly.
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # If pipeline_id is provided, get configuration from pipeline
        if pipeline_id:
            cur.execute("""
                SELECT profile_username, daily_limit, facebook_account_id 
                FROM pipelines 
                WHERE id = %s AND is_active = true
            """, (pipeline_id,))
            pipeline = cur.fetchone()
            
            if not pipeline:
                print(f"❌ Pipeline {pipeline_id} not found or inactive")
                return []
            
            profile_username = pipeline['profile_username']
            daily_limit = pipeline['daily_limit'] or limit
            facebook_account_id = pipeline['facebook_account_id']
            
            print(f"📋 Using pipeline: {profile_username} (limit: {daily_limit})")
        else:
            # Use provided username or default
            profile_username = username or 'nasa'
            daily_limit = limit
            # Get first active Facebook account
            cur.execute("""
                SELECT DISTINCT facebook_account_id FROM pipelines 
                WHERE is_active = true LIMIT 1
            """)
            fb_result = cur.fetchone()
            facebook_account_id = fb_result['facebook_account_id'] if fb_result else None
        
        # Get scraped reels for this username
        cur.execute("""
            SELECT 
                results
            FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC
            LIMIT 1
        """, (profile_username,))
        
        result = cur.fetchone()
        if not result:
            print(f"❌ No scraped data found for username: {profile_username}")
            return []
        
        # Extract reels for this profile
        results = result['results']
        profile_reels = []
        for item in results:
            if item.get('username') == profile_username:
                profile_reels = item.get('reels', [])
                break
        
        # Get already posted reels
        posted_urls = set()
        if pipeline_id:
            cur.execute("""
                SELECT reel_url FROM posted_reels 
                WHERE pipeline_id = %s
            """, (pipeline_id,))
            for row in cur.fetchall():
                posted_urls.add(row['reel_url'])
        
        # Filter unposted reels
        unposted = []
        for reel in profile_reels:
            if isinstance(reel, str):
                reel_url = reel
                caption = ""
            elif isinstance(reel, dict):
                reel_url = reel.get('url')
                caption = reel.get('caption', '')
            else:
                continue
            
            if reel_url and reel_url not in posted_urls:
                unposted.append({
                    "url": reel_url,
                    "caption": caption
                })
        
        # Limit to daily_limit
        unposted = unposted[:daily_limit]
        
        return {
            "username": profile_username,
            "facebook_account_id": facebook_account_id,
            "reels": unposted,
            "total_available": len(profile_reels),
            "already_posted": len(posted_urls)
        }
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def mark_reel_as_posted(pipeline_id, reel_url, direct_video_url=None, caption=None, 
                        facebook_post_id=None, facebook_post_url=None, status='success', error_message=None):
    """Mark a reel as posted in database."""
    if not pipeline_id:
        print("⚠️ No pipeline_id provided, skipping database update")
        return False
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO posted_reels (
                pipeline_id, reel_url, direct_video_url, caption, 
                facebook_post_id, facebook_post_url, status, error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pipeline_id, reel_url) DO UPDATE SET
                direct_video_url = EXCLUDED.direct_video_url,
                caption = EXCLUDED.caption,
                facebook_post_id = EXCLUDED.facebook_post_id,
                facebook_post_url = EXCLUDED.facebook_post_url,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                posted_at = NOW()
        """, (pipeline_id, reel_url, direct_video_url, caption, 
              facebook_post_id, facebook_post_url, status, error_message))
        
        conn.commit()
        print(f"  📝 Marked as posted: {reel_url[:50]}...")
        return True
    except Exception as e:
        print(f"  ❌ Failed to mark as posted: {e}")
        return False
    finally:
        cur.close()
        conn.close()

# ============== VIDEO EXTRACTION ==============

def get_direct_video_url(reel_url):
    """Extract direct video URL from Instagram reel URL."""
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "best[ext=mp4]/best",
            "nocheckcertificate": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(reel_url, download=False)
            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]
            target = entries[0] if entries else None
            if not target:
                return None
            formats = target.get("formats", [])
            if not formats:
                return target.get("url") or target.get("webpage_url")
            for fmt in formats:
                if fmt.get("ext") == "mp4" and fmt.get("acodec") != "none" and fmt.get("vcodec") != "none":
                    return fmt.get("url")
            return formats[0].get("url") if formats else None
    except Exception as e:
        print(f"  ❌ yt-dlp error: {e}")
        return None

# ============== PUBLISH FUNCTIONS ==============

def publish_to_facebook(video_url, text, account_id):
    """Publish a video to Facebook via Zernio."""
    headers = {
        "Authorization": f"Bearer {ZERNIO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": text,
        "platforms": [
            {
                "platform": "facebook",
                "accountId": account_id
            }
        ],
        "mediaItems": [
            {
                "type": "video",
                "url": video_url
            }
        ],
        "publishNow": True
    }
    
    try:
        response = requests.post(
            f"{ZERNIO_BASE_URL}/posts",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code in [200, 201]:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": response.text, "status_code": response.status_code}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_accounts():
    """List all connected Facebook accounts."""
    headers = {
        "Authorization": f"Bearer {ZERNIO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{ZERNIO_BASE_URL}/accounts",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('accounts', [])
            
            print("\n📱 Connected Facebook Accounts:")
            print("-" * 60)
            for account in accounts:
                if account.get('platform') == 'facebook':
                    print(f"  ID: {account.get('_id')}")
                    print(f"  Name: {account.get('displayName', 'Unknown')}")
                    print(f"  Status: {account.get('platformStatus', 'unknown')}")
                    print("-" * 60)
            return accounts
        else:
            print(f"❌ Failed to list accounts: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

# ============== MAIN ==============

def main():
    parser = argparse.ArgumentParser(
        description='Publish unreel videos from database to Facebook via Zernio'
    )
    parser.add_argument('--pipeline', '-p', help='Pipeline ID to use')
    parser.add_argument('--username', '-u', help='Username to post from (if no pipeline)')
    parser.add_argument('--limit', '-l', type=int, default=2, help='Number of reels to post (default: 2)')
    parser.add_argument('--account', '-a', help='Facebook account ID (auto-detected if not provided)')
    parser.add_argument('--list', action='store_true', help='List available accounts and exit')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be posted without actually posting')
    
    args = parser.parse_args()
    
    # List accounts if requested
    if args.list:
        list_accounts()
        sys.exit(0)
    
    # Get unposted reels from database
    print("🔍 Fetching unposted reels from database...")
    
    if args.pipeline:
        data = get_unposted_reels_from_db(pipeline_id=args.pipeline, limit=args.limit)
    else:
        data = get_unposted_reels_from_db(username=args.username or 'nasa', limit=args.limit)
    
    if not data or not data.get('reels'):
        print("✅ No unposted reels found!")
        sys.exit(0)
    
    reels = data['reels']
    username = data['username']
    facebook_account_id = args.account or data.get('facebook_account_id')
    
    print(f"\n📊 Found {len(reels)} unposted reels for @{username}")
    print(f"  Total available: {data.get('total_available', 0)}")
    print(f"  Already posted: {data.get('already_posted', 0)}")
    
    if not facebook_account_id:
        print("❌ No Facebook account ID found. Please provide --account")
        sys.exit(1)
    
    print(f"  Facebook Account: {facebook_account_id}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN - Would post these reels:")
        for i, reel in enumerate(reels, 1):
            print(f"  {i}. URL: {reel['url'][:60]}...")
            print(f"     Caption: {reel.get('caption', 'No caption')[:50]}...")
        print("\n✅ Dry run complete! No posts were made.")
        sys.exit(0)
    
    # Post each reel
    print(f"\n📤 Publishing {len(reels)} reels...")
    print("-" * 60)
    
    posted_count = 0
    failed_count = 0
    
    for i, reel in enumerate(reels, 1):
        reel_url = reel['url']
        caption = reel.get('caption', '')
        
        # If no caption, use fallback
        if not caption or caption.strip() == '':
            caption = f"🎬 New reel from @{username}!"
        
        # Truncate if too long (Facebook max 5,000 characters)
        if len(caption) > 5000:
            caption = caption[:4997] + "..."
        
        print(f"\n📹 Reel {i}/{len(reels)}:")
        print(f"  URL: {reel_url[:60]}...")
        print(f"  Caption: {caption[:60]}...")
        
        # Get direct video URL
        print("  ⏳ Extracting direct video URL...")
        direct_url = get_direct_video_url(reel_url)
        
        if not direct_url:
            print("  ❌ Failed to extract direct URL")
            failed_count += 1
            continue
        
        print(f"  ✅ Direct URL obtained")
        
        # Publish to Facebook
        print("  📤 Publishing to Facebook...")
        result = publish_to_facebook(direct_url, caption, facebook_account_id)
        
        if result['success']:
            post_data = result['data']
            post_id = post_data.get('post', {}).get('_id') or post_data.get('post_id')
            
            # Get Facebook URL
            post_url = None
            platforms = post_data.get('post', {}).get('platforms', [])
            for platform in platforms:
                if platform.get('platform') == 'facebook':
                    post_url = platform.get('publishedUrl')
                    break
            
            print(f"  ✅ SUCCESS!")
            print(f"     Post ID: {post_id}")
            if post_url:
                print(f"     URL: {post_url}")
            
            # Mark as posted in database
            if args.pipeline:
                mark_reel_as_posted(
                    pipeline_id=args.pipeline,
                    reel_url=reel_url,
                    direct_video_url=direct_url,
                    caption=caption,
                    facebook_post_id=post_id,
                    facebook_post_url=post_url,
                    status='success'
                )
            
            posted_count += 1
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"  ❌ FAILED: {error_msg}")
            
            # Mark as failed in database
            if args.pipeline:
                mark_reel_as_posted(
                    pipeline_id=args.pipeline,
                    reel_url=reel_url,
                    direct_video_url=direct_url,
                    caption=caption,
                    status='failed',
                    error_message=error_msg
                )
            
            failed_count += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 SUMMARY:")
    print(f"  ✅ Posted: {posted_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  📹 Total: {len(reels)}")
    print("=" * 60)

if __name__ == "__main__":
    main()