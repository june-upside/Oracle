from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import threading
import time
from collections import deque
from typing import Dict, List

from config import (
    SUPPORTED_COINS, UPDATE_INTERVAL, CHART_HISTORY_SIZE,
    DEFAULT_EXCHANGE_WEIGHTS, DEFAULT_AGGREGATION_METHOD
)
from exchanges import UpbitClient, BithumbClient, CoinoneClient
from oracle import Aggregator, Calculator

app = Flask(__name__)
CORS(app)

# Initialize exchange clients
upbit = UpbitClient()
bithumb = BithumbClient()
coinone = CoinoneClient()

# Initialize aggregator
aggregator = Aggregator()
calculator = Calculator()

# Data storage
exchange_clients = {
    'upbit': upbit,
    'bithumb': bithumb,
    'coinone': coinone
}

# Chart data storage (circular buffer for each coin)
chart_data = {coin: deque(maxlen=CHART_HISTORY_SIZE) for coin in SUPPORTED_COINS}

# User parameters (stored in memory, can be persisted)
user_params = {
    'exchange_weights': DEFAULT_EXCHANGE_WEIGHTS.copy(),
    'spread_weights': {'upbit': 1.0, 'bithumb': 1.0, 'coinone': 1.0},
    'volume_weights': {'upbit': 1.0, 'bithumb': 1.0, 'coinone': 1.0},
    'depth_weights': {'upbit': 1.0, 'bithumb': 1.0, 'coinone': 1.0},
    'aggregation_method': DEFAULT_AGGREGATION_METHOD
}

# Lock for thread-safe access
data_lock = threading.Lock()


def collect_exchange_data(coin: str) -> Dict[str, Dict]:
    """Collect data from all exchanges for a coin"""
    exchange_data = {}
    
    # Upbit
    ticker = upbit.get_ticker(coin)
    if ticker:
        spread = upbit.calculate_spread(coin)
        depth = upbit.calculate_depth(coin)
        exchange_data['upbit'] = {
            'price': ticker.get('price'),
            'volume': ticker.get('volume'),
            'spread': spread,
            'depth': depth
        }
    
    # Bithumb
    ticker = bithumb.get_ticker(coin)
    if ticker:
        spread = bithumb.calculate_spread(coin)
        depth = bithumb.calculate_depth(coin)
        exchange_data['bithumb'] = {
            'price': ticker.get('price'),
            'volume': ticker.get('volume'),
            'spread': spread,
            'depth': depth
        }
        # Debug: 빗썸 스프레드 계산 확인
        if spread is None:
            print(f"Bithumb spread is None for {coin}, bid_price: {ticker.get('bid_price')}, ask_price: {ticker.get('ask_price')}")
    
    # Coinone
    ticker = coinone.get_ticker(coin)
    if ticker:
        spread = coinone.calculate_spread(coin)
        depth = coinone.calculate_depth(coin)
        exchange_data['coinone'] = {
            'price': ticker.get('price'),
            'volume': ticker.get('volume'),
            'spread': spread,
            'depth': depth
        }
        # Debug: 코인원 호가 깊이 확인
        if depth is None:
            orderbook = coinone.get_orderbook(coin)
            print(f"Coinone depth is None for {coin}, orderbook: {orderbook}")
    
    return exchange_data


def update_data():
    """Update data for all coins periodically"""
    while True:
        try:
            for coin in SUPPORTED_COINS:
                exchange_data = collect_exchange_data(coin)
                
                if exchange_data:
                    # Aggregate price
                    aggregated_price, weights = aggregator.aggregate(
                        exchange_data,
                        user_params['exchange_weights'],
                        user_params['aggregation_method'],
                        user_params['spread_weights'],
                        user_params['volume_weights'],
                        user_params['depth_weights']
                    )
                    
                    # Debug: 집계 가격 확인
                    if aggregated_price is None:
                        print(f"Aggregated price is None for {coin}")
                        print(f"Exchange data: {exchange_data}")
                        print(f"Weights: {weights}")
                    
                    # Store chart data
                    if aggregated_price:
                        timestamp = time.time() * 1000  # milliseconds
                        with data_lock:
                            chart_data[coin].append({
                                'timestamp': timestamp,
                                'price': aggregated_price,
                                'exchanges': {
                                    ex: data.get('price') for ex, data in exchange_data.items()
                                }
                            })
            
            time.sleep(UPDATE_INTERVAL)
        except Exception as e:
            print(f"Error in update_data: {e}")
            time.sleep(UPDATE_INTERVAL)


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/prices')
def get_prices():
    """Get current prices from all exchanges"""
    result = {}
    
    for coin in SUPPORTED_COINS:
        exchange_data = collect_exchange_data(coin)
        coin_data = {}
        
        for exchange, data in exchange_data.items():
            coin_data[exchange] = {
                'price': data.get('price'),
                'volume': data.get('volume'),
                'spread': data.get('spread'),
                'depth': data.get('depth')
            }
        
        result[coin] = coin_data
    
    return jsonify(result)


@app.route('/api/aggregated')
def get_aggregated():
    """Get aggregated prices for all coins"""
    result = {}
    
    for coin in SUPPORTED_COINS:
        exchange_data = collect_exchange_data(coin)
        
        if exchange_data:
            aggregated_price, weights = aggregator.aggregate(
                exchange_data,
                user_params['exchange_weights'],
                user_params['aggregation_method'],
                user_params['spread_weights'],
                user_params['volume_weights'],
                user_params['depth_weights']
            )
            
            result[coin] = {
                'price': aggregated_price,
                'weights': weights,
                'exchanges': {
                    ex: data.get('price') for ex, data in exchange_data.items()
                }
            }
        else:
            result[coin] = {
                'price': None,
                'weights': {},
                'exchanges': {}
            }
    
    return jsonify(result)


@app.route('/api/chart/<coin>')
def get_chart_data(coin):
    """Get chart data for a specific coin"""
    if coin.upper() not in SUPPORTED_COINS:
        return jsonify({'error': 'Unsupported coin'}), 400
    
    coin = coin.upper()
    with data_lock:
        data = list(chart_data[coin])
    
    return jsonify(data)


@app.route('/api/params', methods=['GET'])
def get_params():
    """Get current user parameters"""
    return jsonify(user_params)


@app.route('/api/params', methods=['POST'])
def update_params():
    """Update user parameters"""
    data = request.get_json()
    
    if 'exchange_weights' in data:
        user_params['exchange_weights'].update(data['exchange_weights'])
    
    if 'spread_weights' in data:
        user_params['spread_weights'].update(data['spread_weights'])
    
    if 'volume_weights' in data:
        user_params['volume_weights'].update(data['volume_weights'])
    
    if 'depth_weights' in data:
        user_params['depth_weights'].update(data['depth_weights'])
    
    if 'aggregation_method' in data:
        if data['aggregation_method'] in ['average', 'median']:
            user_params['aggregation_method'] = data['aggregation_method']
    
    return jsonify({'status': 'success', 'params': user_params})


if __name__ == '__main__':
    # Connect to exchange WebSockets
    upbit.connect(SUPPORTED_COINS)
    coinone.connect(SUPPORTED_COINS)
    
    # Start data update thread
    update_thread = threading.Thread(target=update_data, daemon=True)
    update_thread.start()
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=False)

