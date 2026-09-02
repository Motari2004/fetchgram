import requests
import json
import os
from datetime import datetime

# ============== ZERNIO CONFIGURATION ==============

ZERNIO_API_KEY = "sk_48ad5dd4a9d9bd8e2561633862dc1708b3fb2013645023fde617921bd065a037"
ZERNIO_BASE_URL = "https://api.zernio.com"

ZERNIO_HEADERS = {
    "Authorization": f"Bearer {ZERNIO_API_KEY}",
    "Content-Type": "application/json"
}

# Your Facebook account IDs from Zernio
# Replace these with your actual account IDs
FACEBOOK_ACCOUNT_1 = "6a8c73ab77555aae01fabf32"
FACEBOOK_ACCOUNT_2 = "your_facebook_account_id_2"

# ============== TEST VIDEO URL ==============

# The Instagram video URL you provided
TEST_VIDEO_URL = "https://scontent-iad6-1.cdninstagram.com/o1/v/t2/f2/m86/AQMz1Cbqz2nnVS0mfWVlxU9aWlACzJ0J2Tx5Qwby5DTGAsH4LZ4PNNdrt5QIYG2DzUIhlAmBZVXon9BfWuYc6DlGNL7PlOWtgnnDugA.mp4?_nc_cat=100&_nc_sid=5e9851&_nc_ht=scontent-iad6-1.cdninstagram.com&_nc_ohc=qnQmE4OwM5YQ7kNvwFrAI-h&efg=eyJ2ZW5jb2RlX3RhZyI6Inhwdl9wcm9ncmVzc2l2ZS5JTlNUQUdSQU0uQ0xJUFMuQzMuNzIwLmRhc2hfYmFzZWxpbmVfMV92MSIsInhwdl9hc3NldF9pZCI6MTY5MjExODQzNTIyMTI3NSwiYXNzZXRfYWdlX2RheXMiOjAsInZpX3VzZWNhc2VfaWQiOjEwMDk5LCJkdXJhdGlvbl9zIjoxNywidXJsZ2VuX3NvdXJjZSI6Ind3dyJ9&ccb=17-1&vs=2e9f5cb0eb32cb59&_nc_vs=HBksFQIYUmlnX3hwdl9yZWVsc19wZXJtYW5lbnRfc3JfcHJvZC8wRjQ1QTMxNTFGOTRDMzU5NDEyQTMwRTUwRkY4MDM5OV92aWRlb19kYXNoaW5pdC5tcDQVAALIARIAFQIYUWlnX3hwdl9wbGFjZW1lbnRfcGVybWFuZW50X3YyLzhCNDFEQzg2OEU2RjkyOEU0RkE2MTEwQjY5QjRFQTk4X2F1ZGlvX2Rhc2hpbml0Lm1wNBUCAsgBEgAoABgAGwKIB3VzZV9vaWwBMRJwcm9ncmVzc2l2ZV9yZWNpcGUBMRUAACa2vP7joL6BBhUCKAJDMywXQDFwo9cKPXEYEmRhc2hfYmFzZWxpbmVfMV92MREAdf4HZeadAQA&_nc_gid=U3o8Vz2CtlFK1UhXt8Xivg&_nc_zt=28&_nc_ss=7a22e&oh=00_AQLxqPGjDhDtsYLZO4NsUG4sWw5JIG1n2kPAU9CY7m_mwQ&oe=6A9A4A95"

# ============== TEST FUNCTIONS ==============

def test_zernio_connection():
    """Test Zernio API connection"""
    print("🔍 Testing Zernio connection...")
    
    try:
        response = requests.get(
            f"{ZERNIO_BASE_URL}/profiles",
            headers=ZERNIO_HEADERS
        )
        
        if response.status_code == 200:
            print("✅ Zernio connection successful!")
            data = response.json()
            print(f"📊 Found {len(data.get('data', []))} profiles")
            return True
        else:
            print(f"❌ Zernio connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_get_facebook_accounts():
    """Get Facebook accounts from Zernio"""
    print("\n🔍 Getting Facebook accounts...")
    
    try:
        response = requests.get(
            f"{ZERNIO_BASE_URL}/accounts",
            headers=ZERNIO_HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            facebook_accounts = []
            for account in data.get('data', []):
                if account.get('platform') == 'facebook':
                    facebook_accounts.append(account)
                    print(f"✅ Found Facebook account: {account.get('name')} (ID: {account.get('id')})")
            
            if not facebook_accounts:
                print("⚠️ No Facebook accounts found. Please connect Facebook first.")
            return facebook_accounts
        else:
            print(f"❌ Failed to get accounts: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def test_upload_video_to_facebook(video_url, text, account_id):
    """Upload video to Facebook via Zernio"""
    print(f"\n📤 Uploading video to Facebook...")
    print(f"📝 Text: {text}")
    print(f"🎬 Video URL: {video_url[:100]}...")
    
    payload = {
        "text": text,
        "accounts": [account_id],
        "media": [video_url]
    }
    
    try:
        response = requests.post(
            f"{ZERNIO_BASE_URL}/posts",
            headers=ZERNIO_HEADERS,
            json=payload,
            timeout=120  # 2 minute timeout for video upload
        )
        
        if response.status_code in [200, 201]:
            print("✅ Video uploaded successfully!")
            data = response.json()
            print(f"📊 Response: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except requests.exceptions.Timeout:
        print("❌ Upload timed out. The video might be large or the connection slow.")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_upload_with_video_file(video_file_path, text, account_id):
    """Upload a local video file to Facebook via Zernio"""
    print(f"\n📤 Uploading video file to Facebook...")
    print(f"📝 Text: {text}")
    print(f"📁 Video file: {video_file_path}")
    
    # Check if file exists
    if not os.path.exists(video_file_path):
        print(f"❌ Video file not found: {video_file_path}")
        return None
    
    # Read the video file
    try:
        with open(video_file_path, 'rb') as f:
            video_data = f.read()
        
        # Convert to base64 or multipart form data
        files = {
            'media': (os.path.basename(video_file_path), video_data, 'video/mp4')
        }
        
        data = {
            'text': text,
            'accounts': json.dumps([account_id])
        }
        
        # Note: Zernio might support multipart upload. If not, you'd need to upload to a temp URL first.
        print("ℹ️ This is a placeholder. Zernio's API may need the video as a URL or base64.")
        
        # Alternative: Upload to a temp service first (e.g., imgur, cloudinary)
        return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# ============== MAIN TEST ==============

def main():
    print("=" * 60)
    print("🚀 ZERNIO FACEBOOK UPLOAD TEST")
    print("=" * 60)
    
    # 1. Test connection
    if not test_zernio_connection():
        print("\n❌ Cannot continue. Zernio connection failed.")
        return
    
    # 2. Get Facebook accounts
    facebook_accounts = test_get_facebook_accounts()
    if not facebook_accounts:
        print("\n⚠️ No Facebook accounts connected. Please connect your Facebook accounts first.")
        print("\n💡 To connect Facebook accounts:")
        print("  1. Run: zernio connect:get-url --platform facebook --profileId <your_profile_id>")
        print("  2. Open the URL in your browser")
        print("  3. Authorize Zernio to access your Facebook account")
        return
    
    # 3. Use the first Facebook account
    account_id = facebook_accounts[0]['id']
    account_name = facebook_accounts[0]['name']
    print(f"\n✅ Using Facebook account: {account_name} (ID: {account_id})")
    
    # 4. Upload video
    test_text = "🎬 Test video upload from my Instagram downloader app! #testing #instagram #facebook"
    
    result = test_upload_video_to_facebook(
        TEST_VIDEO_URL,
        test_text,
        account_id
    )
    
    if result:
        print("\n✅ Test completed successfully!")
        print(f"📊 Post ID: {result.get('id')}")
        print(f"🔗 Post URL: {result.get('url', 'N/A')}")
    else:
        print("\n❌ Test failed. Please check the errors above.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()