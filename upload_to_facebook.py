# zernio_publish_now.py
import requests
import json

# ============== CONFIGURATION ==============

API_KEY = "sk_48ad5dd4a9d9bd8e2561633862dc1708b3fb2013645023fde617921bd065a037"
BASE_URL = "https://zernio.com/api/v1"

# Wildlife Explorers Facebook Account
ACCOUNT_ID = "6a8c73ab77555aae01fabf32"

# The Instagram video URL
VIDEO_URL = "https://scontent-iad6-1.cdninstagram.com/o1/v/t2/f2/m86/AQMz1Cbqz2nnVS0mfWVlxU9aWlACzJ0J2Tx5Qwby5DTGAsH4LZ4PNNdrt5QIYG2DzUIhlAmBZVXon9BfWuYc6DlGNL7PlOWtgnnDugA.mp4?_nc_cat=100&_nc_sid=5e9851&_nc_ht=scontent-iad6-1.cdninstagram.com&_nc_ohc=qnQmE4OwM5YQ7kNvwFrAI-h&efg=eyJ2ZW5jb2RlX3RhZyI6Inhwdl9wcm9ncmVzc2l2ZS5JTlNUQUdSQU0uQ0xJUFMuQzMuNzIwLmRhc2hfYmFzZWxpbmVfMV92MSIsInhwdl9hc3NldF9pZCI6MTY5MjExODQzNTIyMTI3NSwiYXNzZXRfYWdlX2RheXMiOjAsInZpX3VzZWNhc2VfaWQiOjEwMDk5LCJkdXJhdGlvbl9zIjoxNywidXJsZ2VuX3NvdXJjZSI6Ind3dyJ9&ccb=17-1&vs=2e9f5cb0eb32cb59&_nc_vs=HBksFQIYUmlnX3hwdl9yZWVsc19wZXJtYW5lbnRfc3JfcHJvZC8wRjQ1QTMxNTFGOTRDMzU5NDEyQTMwRTUwRkY4MDM5OV92aWRlb19kYXNoaW5pdC5tcDQVAALIARIAFQIYUWlnX3hwdl9wbGFjZW1lbnRfcGVybWFuZW50X3YyLzhCNDFEQzg2OEU2RjkyOEU0RkE2MTEwQjY5QjRFQTk4X2F1ZGlvX2Rhc2hpbml0Lm1wNBUCAsgBEgAoABgAGwKIB3VzZV9vaWwBMRJwcm9ncmVzc2l2ZV9yZWNpcGUBMRUAACa2vP7joL6BBhUCKAJDMywXQDFwo9cKPXEYEmRhc2hfYmFzZWxpbmVfMV92MREAdf4HZeadAQA&_nc_gid=U3o8Vz2CtlFK1UhXt8Xivg&_nc_zt=28&_nc_ss=7a22e&oh=00_AQLxqPGjDhDtsYLZO4NsUG4sWw5JIG1n2kPAU9CY7m_mwQ&oe=6A9A4A95"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ============== PUBLISH IMMEDIATELY ==============

def publish_to_facebook_now(video_url, text, account_id):
    """
    Publish a video to Facebook immediately using publishNow: true
    """
    print("📤 Publishing video to Facebook (Immediate)...")
    print(f"📱 Account: Wildlife Explorers")
    print(f"📝 Text: {text[:60]}...")
    
    payload = {
        "content": text,
        "publishNow": True,  # <-- KEY: This publishes immediately!
        "profileId": None,   # Optional: use if you have a profile
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
        ]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/posts",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            post = data.get('post', data)
            
            print("\n✅ Video published successfully!")
            print(f"  🆔 Post ID: {post.get('_id', 'N/A')}")
            print(f"  📊 Status: {post.get('status', 'N/A')}")
            
            # Check if it was published
            if post.get('status') == 'published':
                print("  ✅ POST IS LIVE ON FACEBOOK!")
                # Get the platform URL if available
                platforms = post.get('platforms', [])
                for p in platforms:
                    if p.get('platform') == 'facebook':
                        print(f"  🔗 Facebook URL: {p.get('publishedUrl', 'N/A')}")
            else:
                print(f"  ⚠️ Post status: {post.get('status', 'unknown')}")
                print("  💡 Check the full response for details.")
            
            return data
        else:
            print(f"❌ Failed to publish")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ============== MAIN ==============

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ZERNIO FACEBOOK LIVE PUBLISH")
    print("=" * 60)
    
    result = publish_to_facebook_now(
        video_url=VIDEO_URL,
        text="🎬 Check out this amazing wildlife video! 🌍🦁\n\n#wildlife #nature #animals #conservation #biodiversity #wildlifephotography",
        account_id=ACCOUNT_ID
    )
    
    print("\n" + "=" * 60)
    if result:
        post = result.get('post', result)
        if post.get('status') == 'published':
            print("✅ VIDEO IS LIVE ON FACEBOOK!")
        else:
            print(f"⚠️ Post status: {post.get('status', 'unknown')}")
    else:
        print("❌ Failed to publish. Please check the errors above.")