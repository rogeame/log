import pandas as pd
from apis.cmc_api import CMCAPI
from apis.reddit_api import RedditAPI
from apis.twitter_api import TwitterAPI

def fetch_market_data_cmc(symbols, convert='USD'):
    """
    Fetches price and market data for the given symbols from CoinMarketCap.
    Returns a DataFrame.
    """
    cmc = CMCAPI()
    data = []
    resp = cmc.get_quotes_latest(symbol=",".join(symbols), convert=convert)
    for symbol in symbols:
        info = resp['data'].get(symbol)
        if not info:
            continue
        quote = info['quote'][convert]
        data.append({
            'symbol': symbol,
            'price': quote['price'],
            'market_cap': quote.get('market_cap'),
            'percent_change_24h': quote.get('percent_change_24h'),
            'volume_24h': quote.get('volume_24h'),
            'last_updated': quote.get('last_updated')
        })
    return pd.DataFrame(data)

def fetch_reddit_mentions(subreddit, limit=20):
    """
    Fetches latest post titles from a subreddit.
    Returns a list of strings.
    """
    reddit = RedditAPI()
    posts = reddit.get_subreddit_posts(subreddit=subreddit, sort='hot', limit=limit)
    return [p['data']['title'] for p in posts]

def fetch_twitter_mentions(keyword, max_results=20):
    """
    Fetches recent tweets containing the keyword.
    Returns a list of tweet texts.
    """
    twitter = TwitterAPI()
    try:
        tweets = twitter.search_recent_tweets(query=keyword, max_results=max_results)
        return [t['text'] for t in tweets]
    except Exception as e:
        print(f"[ERROR] Twitter data fetch: {e}")
        return []

def aggregate_market_data(symbols, convert='USD'):
    """
    Aggregates CMC market data and social mentions for each symbol.
    Returns a dict: symbol -> {market_data, reddit, twitter}
    """
    result = {}
    market_df = fetch_market_data_cmc(symbols, convert=convert)
    for _, row in market_df.iterrows():
        symbol = row['symbol']
        reddit_mentions = fetch_reddit_mentions(subreddit=symbol.lower(), limit=10)
        twitter_mentions = fetch_twitter_mentions(keyword=symbol, max_results=10)
        result[symbol] = {
            'market': row.to_dict(),
            'reddit_mentions': reddit_mentions,
            'twitter_mentions': twitter_mentions
        }
    return result

# Example usage:
if __name__ == "__main__":
    symbols = ["BTC", "ETH", "SOL"]
    data = aggregate_market_data(symbols)
    for symbol, info in data.items():
        print(f"{symbol}:")
        print("  Market:", info['market'])
        print("  Reddit Mentions:", info['reddit_mentions'][:2])
        print("  Twitter Mentions:", info['twitter_mentions'][:2])