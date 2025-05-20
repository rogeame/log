import requests
from typing import Any, Dict, List, Optional


class CoinGeckoAPI:
    BASE_URL = "https://api.coingecko.com/api/v3"

    def get_price(self, coin_id: str, vs_currency: str = "usd") -> Dict[str, Any]:
        """
        Get the current price of a coin in the specified currency.
        """
        url = f"{self.BASE_URL}/simple/price"
        params = {"ids": coin_id, "vs_currencies": vs_currency}
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_ohlc(self, coin_id: str, vs_currency: str = "usd", days: int = 1) -> List[List[float]]:
        """
        Get OHLC (Open, High, Low, Close) data for the coin.
        days: 1, 7, 14, 30, 90, 180, 365, or 'max'
        """
        url = f"{self.BASE_URL}/coins/{coin_id}/ohlc"
        params = {"vs_currency": vs_currency, "days": days}
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        # List of [timestamp, open, high, low, close]
        return resp.json()

    def get_trending(self) -> Dict[str, Any]:
        """
        Get trending search coins on CoinGecko.
        """
        url = f"{self.BASE_URL}/search/trending"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_coin_categories(self) -> List[Dict[str, Any]]:
        """
        Get all coin categories (sectors, narratives, etc).
        """
        url = f"{self.BASE_URL}/coins/categories/list"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_coin_market_chart(self, coin_id: str, vs_currency: str = "usd", days: int = 30) -> Dict[str, Any]:
        """
        Get historical market data (price, market cap, total volumes).
        days: Number of days to look back (e.g. 1, 7, 30, 'max')
        """
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params = {"vs_currency": vs_currency, "days": days}
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_coin_info(self, coin_id: str) -> Dict[str, Any]:
        """
        Get detailed info for a coin (description, links, genesis date, etc).
        """
        url = f"{self.BASE_URL}/coins/{coin_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_supported_vs_currencies(self) -> List[str]:
        """
        Get all supported vs_currencies (fiat, BTC, ETH, etc).
        """
        url = f"{self.BASE_URL}/simple/supported_vs_currencies"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()