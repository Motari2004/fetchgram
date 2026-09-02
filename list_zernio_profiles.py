import requests
import json

API_KEY = "sk_48ad5dd4a9d9bd8e2561633862dc1708b3fb2013645023fde617921bd065a037"
BASE_URL = "https://zernio.com/api/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}

print("📊 Fetching Zernio accounts...")
resp = requests.get(f"{BASE_URL}/accounts", headers=headers, timeout=30)
resp.raise_for_status()

data = resp.json()
print(json.dumps(data, indent=2))  # Pretty print the raw response

# Or get a clean summary
accounts = data.get('data', data) if isinstance(data, dict) else data

print("\n" + "=" * 60)
print("📱 YOUR CONNECTED ACCOUNTS")
print("=" * 60)

# If the response is a list directly
if isinstance(accounts, list):
    account_list = accounts
else:
    # If it's wrapped in a 'data' or 'accounts' field
    account_list = accounts.get('accounts', []) if isinstance(accounts, dict) else []

if not account_list:
    print("⚠️ No accounts found or unexpected response format")
    print("Raw response:", data)
else:
    for i, account in enumerate(account_list, 1):
        print(f"\n📱 Account #{i}")
        print(f"  🆔 ID: {account.get('id') or account.get('_id', 'N/A')}")
        print(f"  📱 Platform: {account.get('platform', 'N/A')}")
        print(f"  📛 Name: {account.get('name') or account.get('displayName', 'N/A')}")
        print(f"  👤 Username: {account.get('username', 'N/A')}")
        print(f"  📊 Status: {account.get('status', account.get('platformStatus', 'N/A'))}")
        
        # Check if there's a page/account info
        if account.get('profileData'):
            profile = account.get('profileData')
            print(f"  📄 Page Name: {profile.get('displayName', 'N/A')}")
            print(f"  📄 Page ID: {profile.get('id', 'N/A')}")
        
        # Check for token expiry
        if account.get('tokenExpiresAt'):
            print(f"  🔑 Token Expires: {account.get('tokenExpiresAt')}")

print("\n" + "=" * 60)