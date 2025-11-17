import json
import threading
import time
import uuid
import websocket
from typing import Dict, Optional, Callable
from config import UPBIT_WS_URL, ORDERBOOK_DEPTH


class UpbitClient:
    def __init__(self):
        self.ws = None
        self.ws_thread = None
        self.is_connected = False
        self.ticker_data = {}
        self.orderbook_data = {}
        self.callbacks = {}
        self.lock = threading.Lock()
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'type' in data:
                if data['type'] == 'ticker':
                    code = data['code']
                    with self.lock:
                        self.ticker_data[code] = {
                            'price': float(data.get('trade_price', 0)),
                            'volume': float(data.get('acc_trade_volume_24h', 0)),
                            'timestamp': time.time()
                        }
                    if code in self.callbacks:
                        self.callbacks[code]('ticker', self.ticker_data[code])
                
                elif data['type'] == 'orderbook':
                    code = data['code']
                    # Upbit orderbook_units contains both bid and ask prices
                    orderbook_units = data.get('orderbook_units', [])
                    bids = []
                    asks = []
                    for item in orderbook_units[:ORDERBOOK_DEPTH]:
                        if 'bid_price' in item and 'bid_size' in item:
                            bids.append((float(item['bid_price']), float(item['bid_size'])))
                        if 'ask_price' in item and 'ask_size' in item:
                            asks.append((float(item['ask_price']), float(item['ask_size'])))
                    # Sort bids descending (highest first), asks ascending (lowest first)
                    bids = sorted(bids, key=lambda x: x[0], reverse=True)
                    asks = sorted(asks, key=lambda x: x[0])
                    with self.lock:
                        self.orderbook_data[code] = {
                            'bids': bids,
                            'asks': asks,
                            'timestamp': time.time()
                        }
                    if code in self.callbacks:
                        self.callbacks[code]('orderbook', self.orderbook_data[code])
        except Exception as e:
            print(f"Upbit WebSocket message error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_error(self, ws, error):
        print(f"Upbit WebSocket error: {error}")
        self.is_connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        print("Upbit WebSocket closed")
        self.is_connected = False
    
    def _on_open(self, ws):
        print("Upbit WebSocket connected")
        self.is_connected = True
    
    def _run_websocket(self):
        self.ws.run_forever()
    
    def connect(self, coins: list, callback: Optional[Callable] = None):
        """Connect to Upbit WebSocket and subscribe to ticker and orderbook"""
        ticker_codes = [f"KRW-{coin}" for coin in coins]
        orderbook_codes = [f"KRW-{coin}" for coin in coins]
        
        # Store callbacks
        for coin in coins:
            code = f"KRW-{coin}"
            if callback:
                self.callbacks[code] = callback
        
        # WebSocket message format (업비트 API 문서에 따른 형식)
        ticket = str(uuid.uuid4())
        subscribe_message = [
            {"ticket": ticket},
            {
                "type": "ticker",
                "codes": ticker_codes
            },
            {
                "type": "orderbook",
                "codes": orderbook_codes
            },
            {
                "format": "DEFAULT"
            }
        ]
        
        self.ws = websocket.WebSocketApp(
            UPBIT_WS_URL,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Send subscription message after connection
        def on_open_with_subscribe(ws):
            self._on_open(ws)
            ws.send(json.dumps(subscribe_message))
        
        self.ws.on_open = on_open_with_subscribe
        
        self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self.ws_thread.start()
    
    def get_ticker(self, coin: str) -> Optional[Dict]:
        """Get current ticker data from WebSocket"""
        code = f"KRW-{coin}"
        with self.lock:
            ticker = self.ticker_data.get(code)
            if ticker:
                # Get bid/ask prices from orderbook
                orderbook = self.orderbook_data.get(code)
                if orderbook:
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                    if bids and asks:
                        ticker['bid_price'] = bids[0][0]  # Highest bid
                        ticker['ask_price'] = asks[0][0]  # Lowest ask
            return ticker
    
    def get_orderbook(self, coin: str) -> Optional[Dict]:
        """Get current orderbook data from WebSocket"""
        code = f"KRW-{coin}"
        with self.lock:
            return self.orderbook_data.get(code)
    
    def calculate_spread(self, coin: str) -> Optional[float]:
        """Calculate spread percentage"""
        ticker = self.get_ticker(coin)
        if not ticker or not ticker.get('bid_price') or not ticker.get('ask_price'):
            return None
        
        bid = ticker['bid_price']
        ask = ticker['ask_price']
        mid = (bid + ask) / 2
        
        if mid == 0:
            return None
        
        spread = ((ask - bid) / mid) * 100
        return spread
    
    def calculate_depth(self, coin: str) -> Optional[float]:
        """Calculate order book depth (total liquidity in top N levels)"""
        orderbook = self.get_orderbook(coin)
        if not orderbook:
            return None
        
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        if not bids or not asks:
            return None
        
        # Calculate total liquidity (sum of size * price for top N levels)
        bid_depth = sum(price * size for price, size in bids)
        ask_depth = sum(price * size for price, size in asks)
        
        # Return average depth
        return (bid_depth + ask_depth) / 2
    
    def disconnect(self):
        """Disconnect WebSocket"""
        if self.ws:
            self.ws.close()
        self.is_connected = False

