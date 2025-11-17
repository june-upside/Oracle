# Configuration file for Price Oracle

# Supported coins
SUPPORTED_COINS = ['BTC', 'ETH', 'SOL', 'XRP']

# Exchange API endpoints
UPBIT_WS_URL = "wss://api.upbit.com/websocket/v1"
UPBIT_REST_URL = "https://api.upbit.com/v1"

BITHUMB_REST_URL = "https://api.bithumb.com/public"

COINONE_WS_URL = "wss://stream.coinone.co.kr"

# Update interval (seconds)
UPDATE_INTERVAL = 1.0

# Order book depth (number of levels)
ORDERBOOK_DEPTH = 15

# Chart data history (number of data points)
CHART_HISTORY_SIZE = 100

# Default weights
DEFAULT_EXCHANGE_WEIGHTS = {
    'upbit': 1.0,
    'bithumb': 1.0,
    'coinone': 1.0
}

# Default aggregation method
DEFAULT_AGGREGATION_METHOD = 'average'  # 'average' or 'median'

