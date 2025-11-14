#!/usr/bin/env python3
"""
Fetch keyword data from Apple Search Ads API and save to JSON files.
This runs automatically via GitHub Actions daily.
"""

import os
import json
import requests
from datetime import datetime
import jwt
import time

# Categories to fetch keywords for
CATEGORIES = [
    "games",
    "business", 
    "productivity",
    "education",
    "entertainment",
    "finance",
    "health-fitness",
    "lifestyle",
    "social-networking",
    "utilities"
]

API_BASE_URL = "https://api.searchads.apple.com/api/v4"

def generate_jwt_token():
    """Generate JWT token for Apple Search Ads API authentication"""
    import base64
    
    client_id = os.environ.get('APPLE_SEARCH_ADS_CLIENT_ID')
    team_id = os.environ.get('APPLE_SEARCH_ADS_TEAM_ID')
    key_id = os.environ.get('APPLE_SEARCH_ADS_KEY_ID')
    private_key_env = os.environ.get('APPLE_SEARCH_ADS_PRIVATE_KEY')
    
    if not all([client_id, team_id, key_id, private_key_env]):
        raise ValueError("Missing required environment variables")
    
    # Try to decode if it's base64 encoded, otherwise use as-is
    try:
        private_key_pem = base64.b64decode(private_key_env).decode('utf-8')
    except:
        private_key_pem = private_key_env
    
    # Ensure proper formatting
    if not private_key_pem.startswith('-----BEGIN'):
        raise ValueError("Invalid private key format")
    
    # Current timestamp
    now = int(time.time())
    
    # JWT payload as per Apple Search Ads API documentation
    payload = {
        'sub': client_id,
        'aud': 'https://appleid.apple.com',
        'iat': now,
        'exp': now + 86400,  # 24 hours
        'iss': team_id
    }
    
    # JWT headers
    headers = {
        'alg': 'ES256',
        'kid': key_id,
        'typ': 'JWT'
    }
    
    # Generate token
    token = jwt.encode(payload, private_key_pem, algorithm='ES256', headers=headers)
    
    # PyJWT 2.x returns string, older versions return bytes
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    
    return token

def fetch_keyword_recommendations(category, limit=100):
    """Fetch keyword recommendations from Apple Search Ads API"""
    token = generate_jwt_token()
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'X-AP-Context': 'orgId=YOUR_ORG_ID'  # You'll need to get this from your account
    }
    
    # Apple Search Ads API endpoint for keyword recommendations
    # Note: You may need to adjust this based on your campaign structure
    url = f"{API_BASE_URL}/campaigns/YOUR_CAMPAIGN_ID/adgroups/YOUR_ADGROUP_ID/targetingkeywords/find"
    
    # Request body for keyword search
    body = {
        "pagination": {
            "offset": 0,
            "limit": limit
        },
        "selector": {
            "orderBy": [
                {
                    "field": "relevance",
                    "sortOrder": "DESCENDING"
                }
            ],
            "conditions": [
                {
                    "field": "keywordText",
                    "operator": "CONTAINS",
                    "values": [category]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching keywords for {category}: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

def process_keywords(raw_data):
    """Process raw API data into our format"""
    if not raw_data or 'data' not in raw_data:
        return []
    
    keywords = []
    for item in raw_data['data']:
        keyword = {
            'id': item.get('id'),
            'keyword': item.get('keyword'),
            'searchPopularity': item.get('searchPopularity', 0),
            'competitionLevel': map_competition_level(item.get('bidStrength', 'MEDIUM')),
            'suggestedBidRange': {
                'min': item.get('suggestedBidAmount', {}).get('min', 0),
                'max': item.get('suggestedBidAmount', {}).get('max', 0),
                'currency': item.get('suggestedBidAmount', {}).get('currency', 'USD')
            } if 'suggestedBidAmount' in item else None,
            'category': item.get('category'),
            'lastUpdated': datetime.utcnow().isoformat() + 'Z'
        }
        keywords.append(keyword)
    
    return keywords

def map_competition_level(bid_strength):
    """Map Apple's bid strength to our competition levels"""
    mapping = {
        'LOW': 'low',
        'MEDIUM': 'medium',
        'HIGH': 'high',
        'VERY_HIGH': 'very_high'
    }
    return mapping.get(bid_strength, 'medium')

def save_keywords(keywords, category):
    """Save keywords to JSON file"""
    os.makedirs('categories', exist_ok=True)
    
    data = {
        'keywords': keywords,
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
        'source': 'Apple Search Ads API'
    }
    
    filename = f'categories/{category}.json'
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Saved {len(keywords)} keywords to {filename}")

def save_trending_keywords(all_keywords):
    """Save top trending keywords across all categories"""
    os.makedirs('trending', exist_ok=True)
    
    # Sort by search popularity and take top 100
    trending = sorted(all_keywords, key=lambda x: x.get('searchPopularity', 0), reverse=True)[:100]
    
    data = {
        'keywords': trending,
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
        'source': 'Apple Search Ads API'
    }
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    filename = f'trending/{today}.json'
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Saved {len(trending)} trending keywords to {filename}")

def save_metadata():
    """Save metadata about available data"""
    metadata = {
        'categories': CATEGORIES,
        'lastUpdated': datetime.utcnow().isoformat() + 'Z',
        'version': '1.0'
    }
    
    with open('metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("✓ Saved metadata.json")

def main():
    """Main execution"""
    print("🚀 Starting keyword data fetch from Apple Search Ads API...")
    print()
    
    all_keywords = []
    
    # Fetch keywords for each category
    for category in CATEGORIES:
        print(f"📊 Fetching keywords for {category}...")
        raw_data = fetch_keyword_recommendations(category)
        
        if raw_data:
            keywords = process_keywords(raw_data)
            save_keywords(keywords, category)
            all_keywords.extend(keywords)
        
        # Rate limiting - be nice to the API
        time.sleep(2)
    
    print()
    
