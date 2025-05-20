import os
import requests
from typing import Any, Dict, List, Optional

class TwitterAPI:
    BASE_URL = "https://api.twitter.com/2"

    def __init__(self, bearer_token: Optional[str] = None):
        """
        Initialize with your Twitter/X bearer token.
        If not provided, reads from the TWITTER_BEARER_TOKEN environment variable.
        """
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")
        if not self.bearer_token:
            raise ValueError("Twitter/X bearer token must be set.")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "crypto-bot/0.1"
        }

    def search_recent_tweets(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search recent tweets containing the query string.
        Note: Twitter free tier is extremely limited (few hundred tweets/month).
        :param query: Search string (e.g. 'bitcoin')
        :param max_results: Number of tweets to fetch (max 100 per request)
        """
        url = f"{self.BASE_URL}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,lang,public_metrics"
        }
        resp = requests.get(url, headers=self._headers(), params=params)
        if resp.status_code == 403:
            raise RuntimeError("Twitter API access forbidden: Check free tier limits and account eligibility.")
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_user_tweets(self, user_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent tweets from a user by user_id.
        :param user_id: Twitter user ID (not username)
        :param max_results: Number of tweets to fetch (max 100 per request)
        """
        url = f"{self.BASE_URL}/users/{user_id}/tweets"
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,lang,public_metrics"
        }
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])