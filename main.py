#!/usr/bin/env python3
"""
Microsoft News Aggregator
Auto-collects Microsoft/Power Platform news and syncs to Planka
"""

import os
import json
import requests
import feedparser
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Configuration
PLANKA_URL = os.getenv("PLANKA_URL", "http://10.0.3.3:1337/api")
PLANKA_TOKEN = os.getenv("PLANKA_TOKEN")
BOARD_ID = os.getenv("PLANKA_BOARD_ID", "1700130106099368966")
TODO_LIST_ID = os.getenv("PLANKA_TODO_LIST_ID", "1700134749361669129")

# Microsoft/Power Platform RSS Feeds
FEEDS = {
    "Microsoft Tech Community": "https://techcommunity.microsoft.com/rss-feeds",
    "Power Platform Blog": "https://powerplatform.microsoft.com/en-us/blog/feed/",
    "Microsoft 365 Blog": "https://www.microsoft.com/en-us/microsoft-365/blog/feed/",
    "Azure Blog": "https://azure.microsoft.com/en-us/blog/feed/",
    "Microsoft Learn": "https://docs.microsoft.com/api/search/rss?search=Power%20Platform&locale=en-us",
    "Dynamics 365 Blog": "https://cloudblogs.microsoft.com/dynamics365/feed/",
}

# Keywords to filter relevant content
KEYWORDS = [
    "power platform", "copilot", "power apps", "power automate", 
    "power bi", "dynamics 365", "m365", "microsoft 365",
    "ai", "agent", "automation", "low-code", "no-code",
    "sharepoint", "teams", "azure", "microsoft"
]


class NewsAggregator:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {PLANKA_TOKEN}",
            "Content-Type": "application/json"
        }
        self.processed_urls = set()
        
    def fetch_feed(self, name, url):
        """Fetch and parse RSS feed"""
        try:
            print(f"Fetching: {name}")
            feed = feedparser.parse(url)
            return feed.entries
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            return []
    
    def is_relevant(self, title, summary):
        """Check if article is relevant to Microsoft/Power Platform"""
        text = f"{title} {summary}".lower()
        return any(keyword in text for keyword in KEYWORDS)
    
    def summarize_article(self, title, content):
        """Create a brief summary for Planka card"""
        # Simple summarization - extract first 200 chars
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        summary = text[:300] + "..." if len(text) > 300 else text
        
        return {
            "title": title,
            "summary": summary
        }
    
    def create_planka_card(self, title, description, url, source):
        """Create a card in Planka"""
        card_name = f"[{source}] {title[:80]}"
        card_desc = f"{description}\n\n🔗 Source: {url}\n📅 Found: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M')}"
        
        data = {
            "name": card_name,
            "description": card_desc,
            "listId": TODO_LIST_ID,
            "position": 1
        }
        
        try:
            response = requests.post(
                f"{PLANKA_URL}/lists/{TODO_LIST_ID}/cards",
                headers=self.headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Created card: {card_name[:50]}...")
                return response.json()
            else:
                print(f"❌ Failed to create card: {response.status_code}")
                print(response.text)
                return None
                
        except Exception as e:
            print(f"❌ Error creating card: {e}")
            return None
    
    def check_existing_cards(self, url):
        """Check if URL already exists in Planka cards"""
        try:
            response = requests.get(
                f"{PLANKA_URL}/boards/{BOARD_ID}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                cards = data.get("included", {}).get("cards", [])
                
                for card in cards:
                    if url in card.get("description", ""):
                        return True
                        
        except Exception as e:
            print(f"Error checking existing cards: {e}")
            
        return False
    
    def run(self):
        """Main aggregation loop"""
        print(f"\n🚀 Starting News Aggregation - {datetime.now(pytz.UTC)}")
        print("=" * 60)
        
        new_articles = 0
        
        for source_name, feed_url in FEEDS.items():
            entries = self.fetch_feed(source_name, feed_url)
            
            for entry in entries[:5]:  # Process last 5 entries per feed
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", entry.get("description", ""))
                
                # Skip if already processed
                if link in self.processed_urls:
                    continue
                    
                # Check if already in Planka
                if self.check_existing_cards(link):
                    self.processed_urls.add(link)
                    continue
                
                # Check relevance
                if self.is_relevant(title, summary):
                    article_data = self.summarize_article(title, summary)
                    
                    # Create Planka card
                    result = self.create_planka_card(
                        article_data["title"],
                        article_data["summary"],
                        link,
                        source_name
                    )
                    
                    if result:
                        new_articles += 1
                        self.processed_urls.add(link)
        
        print("=" * 60)
        print(f"✅ Aggregation complete! Added {new_articles} new articles to Planka.")
        return new_articles


if __name__ == "__main__":
    aggregator = NewsAggregator()
    aggregator.run()
