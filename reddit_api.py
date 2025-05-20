import os
import requests
from typing import Any, Dict, List, Optional

class RedditAPI:
    BASE_URL = "https://oauth.reddit.com"
    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize with Reddit API credentials.
        If not provided, reads from environment variables.
        """
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT", "crypto-bot/0.1 by script")
        self.username = username or os.getenv("REDDIT_USERNAME")
        self.password = password or os.getenv("REDDIT_PASSWORD")
        self.access_token = None

        if not all([self.client_id, self.client_secret, self.user_agent, self.username, self.password]):
            raise ValueError("All Reddit API credentials must be set.")

        self.access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        """
        Authenticate via OAuth2 and get an access token.
        """
        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        headers = {"User-Agent": self.user_agent}
        resp = requests.post(self.TOKEN_URL, auth=auth, data=data, headers=headers)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"bearer {self.access_token}",
            "User-Agent": self.user_agent,
        }

    def get_subreddit_posts(self, subreddit: str, sort: str = "hot", limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit.
        :param subreddit: e.g. 'CryptoCurrency'
        :param sort: 'hot', 'new', 'top', 'rising'
        :param limit: Number of posts to fetch (max 100)
        """
        url = f"{self.BASE_URL}/r/{subreddit}/{sort}"
        params = {"limit": limit}
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("children", [])

    def get_post_comments(self, subreddit: str, post_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch comments from a specific post.
        :param subreddit: e.g. 'CryptoCurrency'
        :param post_id: The ID of the post (without 't3_')
        :param limit: Number of comments to fetch
        """
        url = f"{self.BASE_URL}/r/{subreddit}/comments/{post_id}"
        params = {"limit": limit}
        resp = requests.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        # Comments are in the second item of the returned list
        return resp.json()[1].get("data", {}).get("children", [])