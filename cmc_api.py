import os
import requests
from typing import Any, Dict, Optional

class CMCAPI:
    """
    CoinMarketCap API integration (free tier).
    Supports public price/market endpoints allowed under the free plan.
    """
    BASE_URL = "https://pro-api.coinmarketcap.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with your CoinMarketCap API key.
        If not provided, reads from the CMC_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("CMC_API_KEY")
        if not self.api_key:
            raise ValueError("CoinMarketCap API key must be set.")

    def _headers(self) -> Dict[str, str]:
        return {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': self.api_key,
        }

    def get_latest_listings(self, start: int = 1, limit: int = 10, convert: str = "USD") -> Dict[str, Any]:
        """
        Get latest market listings (ticker style).
        :param start: Rank to start at (default 1)
        :param limit: Number of results (default 10, up to 5000)
        :param convert: Currency to convert to (e.g., 'USD', 'BTC')
        """
        url = f"{self.BASE_URL}/cryptocurrency/listings/latest"
        params = {
            "start": start,
            "limit": limit,
            "convert": convert
        }
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_quotes_latest(self, symbol: str, convert: str = "USD") -> Dict[str, Any]:
        """
        Get latest market quote for one or more cryptocurrencies.
        :param symbol: Comma-separated symbols (e.g., 'BTC,ETH')
        :param convert: Convert prices to this currency
        """
        url = f"{self.BASE_URL}/cryptocurrency/quotes/latest"
        params = {
            "symbol": symbol,
            "convert": convert
        }
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get static info (metadata, logo, description, URLs) for one or more cryptocurrencies.
        :param symbol: Comma-separated symbols
        """
        url = f"{self.BASE_URL}/cryptocurrency/info"
        params = {
            "symbol": symbol
        }
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_map(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get mapping of all cryptocurrencies to their IDs, with optional symbol filter.
        :param symbol: Optional comma-separated symbols to filter
        """
        url = f"{self.BASE_URL}/cryptocurrency/map"
        params = {}
        if symbol:
            params["symbol"] = symbol
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()