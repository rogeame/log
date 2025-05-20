import os
import requests
from typing import Any, Dict, Optional

class CryptoPanicAPI:
    BASE_URL = "https://cryptopanic.com/api/v1/posts/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with your CryptoPanic API key.
        If not provided, it tries to read from the CRYPTOPANIC_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("CRYPTOPANIC_API_KEY")
        if not self.api_key:
            raise ValueError("CryptoPanic API key must be set.")

    def get_latest_news(
        self,
        filter_type: str = "hot",
        currencies: Optional[str] = None,
        public: bool = True,
        kind: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch the latest crypto news headlines.
        :param filter_type: 'hot', 'rising', 'latest', 'bullish', 'bearish', 'important', 'saved', or 'lol'
        :param currencies: Comma-separated cryptocurrency symbols (e.g. 'BTC,ETH')
        :param public: If True, only public posts
        :param kind: 'news', 'media', or None for all
        :return: API response as dict
        """
        params = {
            "auth_token": self.api_key,
            "filter": filter_type,
            "public": str(public).lower()
        }
        if currencies:
            params["currencies"] = currencies
        if kind:
            params["kind"] = kind

        resp = requests.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_post_details(self, post_id: int) -> Dict[str, Any]:
        """
        Fetch details for a specific news post by its ID.
        """
        url = f"{self.BASE_URL}{post_id}/"
        params = {"auth_token": self.api_key}
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()