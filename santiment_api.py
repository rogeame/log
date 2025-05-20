import os
import requests
from typing import Any, Dict, Optional

class SantimentAPI:
    BASE_URL = "https://api.santiment.net/graphql"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with your Santiment API key.
        If not provided, reads from the SANTIMENT_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("SANTIMENT_API_KEY")
        if not self.api_key:
            raise ValueError("Santiment API key must be set.")

    def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {"Authorization": f"Apikey {self.api_key}"}
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = requests.post(self.BASE_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_daily_active_addresses(self, slug: str, from_date: str, to_date: str) -> Dict[str, Any]:
        """
        Example metric: Daily active addresses for a project.
        Date format: 'YYYY-MM-DD'
        """
        query = """
        query($slug: String!, $from: DateTime!, $to: DateTime!) {
          getMetric(metric: "daily_active_addresses") {
            timeseriesData(
              slug: $slug
              from: $from
              to: $to
              interval: "1d"
            ) {
              datetime
              value
            }
          }
        }
        """
        variables = {
            "slug": slug,
            "from": f"{from_date}T00:00:00Z",
            "to": f"{to_date}T00:00:00Z",
        }
        return self._query(query, variables)

    def get_github_activity(self, slug: str, from_date: str, to_date: str) -> Dict[str, Any]:
        """
        Example metric: GitHub activity (dev activity) for a project.
        """
        query = """
        query($slug: String!, $from: DateTime!, $to: DateTime!) {
          getMetric(metric: "dev_activity") {
            timeseriesData(
              slug: $slug
              from: $from
              to: $to
              interval: "1d"
            ) {
              datetime
              value
            }
          }
        }
        """
        variables = {
            "slug": slug,
            "from": f"{from_date}T00:00:00Z",
            "to": f"{to_date}T00:00:00Z",
        }
        return self._query(query, variables)

    def get_social_volume(self, slug: str, from_date: str, to_date: str) -> Dict[str, Any]:
        """
        Example metric: Social volume (mentions in crypto social channels) for a project.
        """
        query = """
        query($slug: String!, $from: DateTime!, $to: DateTime!) {
          getMetric(metric: "social_volume_total") {
            timeseriesData(
              slug: $slug
              from: $from
              to: $to
              interval: "1d"
            ) {
              datetime
              value
            }
          }
        }
        """
        variables = {
            "slug": slug,
            "from": f"{from_date}T00:00:00Z",
            "to": f"{to_date}T00:00:00Z",
        }
        return self._query(query, variables)