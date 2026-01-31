#!/usr/bin/env python3
"""
Microsoft News Aggregator
Auto-collects Microsoft/Power Platform news and syncs to Planka
"""

from __future__ import annotations
import os
from typing import Optional, Dict, List, Set, Any
from datetime import datetime
from dataclasses import dataclass
import requests
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import pytz

load_dotenv()

FeedEntry = Dict[str, Any]
PlankaCard = Dict[str, Any]
Headers = Dict[str, str]


@dataclass(frozen=True)
class Config:
    """Configuration loaded from environment variables."""
    PLANKA_URL: str = os.getenv("PLANKA_URL", "")
    PLANKA_TOKEN: Optional[str] = os.getenv("PLANKA_TOKEN")
    BOARD_ID: str = os.getenv("PLANKA_BOARD_ID", "")
    TODO_LIST_ID: str = os.getenv("PLANKA_TODO_LIST_ID", "")
    
    def __post_init__(self):
        """Validate required configuration."""
        if not self.PLANKA_TOKEN:
            raise ValueError("PLANKA_TOKEN environment variable is required")
        if not self.PLANKA_URL:
            raise ValueError("PLANKA_URL environment variable is required")
        if not self.BOARD_ID:
            raise ValueError("PLANKA_BOARD_ID environment variable is required")
        if not self.TODO_LIST_ID:
            raise ValueError("PLANKA_TODO_LIST_ID environment variable is required")


FEEDS: Dict[str, str] = {
    "Microsoft Tech Community": "https://techcommunity.microsoft.com/rss-feeds",
    "Power Platform Blog": "https://powerplatform.microsoft.com/en-us/blog/feed/",
    "Microsoft 365 Blog": "https://www.microsoft.com/en-us/microsoft-365/blog/feed/",
    "Azure Blog": "https://azure.microsoft.com/en-us/blog/feed/",
    "Microsoft Learn": "https://docs.microsoft.com/api/search/rss?search=Power%20Platform&locale=en-us",
    "Dynamics 365 Blog": "https://cloudblogs.microsoft.com/dynamics365/feed/",
}

KEYWORDS: List[str] = [
    "power platform", "copilot", "power apps", "power automate", 
    "power bi", "dynamics 365", "m365", "microsoft 365",
    "ai", "agent", "automation", "low-code", "no-code",
    "sharepoint", "teams", "azure", "microsoft"
]


class NewsAggregator:
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.headers: Headers = {
            "Authorization": f"Bearer {self.config.PLANKA_TOKEN}",
            "Content-Type": "application/json"
        }
        self.processed_urls: Set[str] = set()
        
    def fetch_feed(self, name: str, url: str) -> List[FeedEntry]:
        try:
            print(f"📡 Fetching: {name}")
            feed = feedparser.parse(url)
            return feed.entries
        except Exception as e:
            print(f"❌ Error fetching {name}: {e}")
            return []
    
    def is_relevant(self, title: str, summary: str) -> bool:
        text: str = f"{title} {summary}".lower()
        return any(keyword in text for keyword in KEYWORDS)
    
    def summarize_article(self, title: str, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        text: str = soup.get_text(separator=' ', strip=True)
        summary: str = text[:300] + "..." if len(text) > 300 else text
        return {"title": title, "summary": summary}
    
    def create_planka_card(self, title: str, description: str, url: str, source: str) -> Optional[PlankaCard]:
        card_name: str = f"[{source}] {title[:80]}"
        card_desc: str = f"{description}\n\n🔗 Source: {url}\n📅 Found: {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M')}"
        
        data: Dict[str, Any] = {
            "name": card_name,
            "description": card_desc,
            "listId": self.config.TODO_LIST_ID,
            "position": 1
        }
        
        try:
            response = requests.post(
                f"{self.config.PLANKA_URL}/lists/{self.config.TODO_LIST_ID}/cards",
                headers=self.headers,
                json=data,
                timeout=10
            )
            if response.status_code == 200:
                print(f"✅ Created card: {card_name[:50]}...")
                return response.json()
            else:
                print(f"❌ Failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def check_existing_cards(self, url: str) -> bool:
        try:
            response = requests.get(
                f"{self.config.PLANKA_URL}/boards/{self.config.BOARD_ID}",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                cards = data.get("included", {}).get("cards", [])
                return any(url in card.get("description", "") for card in cards)
        except Exception as e:
            print(f"⚠️ Error checking: {e}")
        return False
    
    def run(self) -> int:
        print(f"\n🚀 M365-Scout - {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)
        
        new_articles: int = 0
        
        for source_name, feed_url in FEEDS.items():
            entries: List[FeedEntry] = self.fetch_feed(source_name, feed_url)
            
            for entry in entries[:5]:
                title: str = entry.get("title", "")
                link: str = entry.get("link", "")
                summary: str = entry.get("summary", entry.get("description", ""))
                
                if link in self.processed_urls:
                    continue
                if self.check_existing_cards(link):
                    self.processed_urls.add(link)
                    continue
                
                if self.is_relevant(title, summary):
                    article_data = self.summarize_article(title, summary)
                    result: Optional[PlankaCard] = self.create_planka_card(
                        article_data["title"],
                        article_data["summary"],
                        link,
                        source_name
                    )
                    if result:
                        new_articles += 1
                        self.processed_urls.add(link)
        
        print("=" * 60)
        print(f"✅ Added {new_articles} articles to Planka.")
        return new_articles


def main() -> None:
    NewsAggregator().run()


if __name__ == "__main__":
    main()
