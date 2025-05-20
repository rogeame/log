import os
import requests
from typing import Any, Dict, Optional

class LunarCrushAPI:
    BASE_URL = "https://api.lunarcrush.com/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with your LunarCrush API key.
        If not provided, it tries to read from the LUNARCRUSH_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("LUNARCRUSH_API_KEY")
        if not self.api_key:
            raise ValueError("LunarCrush API key must be set.")

    def get_assets(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get asset data (social/market metrics).
        :param symbol: Optional coin symbol, e.g. 'BTC'
        """
        params = {
            "api_key": self.api_key,
            "data": "assets"
        }
        if symbol:
            params["symbol"] = symbol
        resp = requests.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_influencers(self, symbol: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Get top influencers for a coin.
        :param symbol: Optional coin symbol, e.g. 'ETH'
        :param limit: Number of influencers to return
        """
        params = {
            "api_key": self.api_key,
            "data": "influencers",
            "limit": limit
        }
        if symbol:
            params["symbol"] = symbol
        resp = requests.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_global_metrics(self) -> Dict[str, Any]:
        """
        Get global social metrics (market-wide).
        """
        params = {
            "api_key": self.api_key,
            "data": "global"
        }
        resp = requests.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()