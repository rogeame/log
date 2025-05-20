import requests
from typing import Any, Dict, Optional

class FearGreedAPI:
    """
    Fetches the Crypto Fear & Greed Index from a free public API.
    No API key is required for most free sources.
    """

    BASE_URL = "https://api.alternative.me/fng/"

    def get_index(self, limit: int = 1) -> Dict[str, Any]:
        """
        Get the latest (or recent) Fear & Greed Index value(s).
        :param limit: Number of data points to return (1 = latest, up to 100).
        """
        params = {"limit": limit, "format": "json"}
        resp = requests.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_historical(self, limit: int = 30) -> Dict[str, Any]:
        """
        Get historical Fear & Greed Index values (up to 100).
        :param limit: Number of data points (days) to return.
        """
        return self.get_index(limit=limit)