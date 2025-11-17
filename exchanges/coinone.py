import json
import threading
import time
import websocket
from typing import Dict, Optional, Callable
from config import ORDERBOOK_DEPTH

COINONE_WS_URL = "wss://stream.coinone.co.kr"


class CoinoneClient:
    def __init__(self):
        self.ws = None
        self.ws_thread = None
        self.is_connected = False
        self.session_id = None
        self.ticker_data = {}
        self.orderbook_data = {}
        self.callbacks = {}
        self.lock = threading.Lock()
        self.connected_event = threading.Event()
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # Handle CONNECTED response
            if data.get('response_type') == 'CONNECTED':
                self.session_id = data.get('data', {}).get('session_id')
                self.is_connected = True
                self.connected_event.set()
                print(f"Coinone WebSocket connected, session_id: {self.session_id}")
                return
            
            # Handle DATA response
            if data.get('response_type') == 'DATA':
                channel = data.get('channel')
                data_obj = data.get('data', {})
                
                if channel == 'TICKER':
                    target_currency = data_obj.get('target_currency', '').upper()
                    if target_currency:
                        with self.lock:
                            self.ticker_data[target_currency] = {
                                'price': float(data_obj.get('last', 0)),
                                'volume': float(data_obj.get('quote_volume', 0)),
                                'bid_price': float(data_obj.get('bid_best_price', 0)) if data_obj.get('bid_best_price') else None,
                                'ask_price': float(data_obj.get('ask_best_price', 0)) if data_obj.get('ask_best_price') else None,
                                'timestamp': time.time()
                            }
                        if target_currency in self.callbacks:
                            self.callbacks[target_currency]('ticker', self.ticker_data[target_currency])
                
                elif channel == 'ORDERBOOK':
                    target_currency = data_obj.get('target_currency', '').upper()
                    if target_currency:
                        bids = []
                        asks = []
                        
                        # Parse orderbook data - 코인원 ORDERBOOK 응답 형식 확인
                        # 코인원은 asks와 bids를 사용 (로그에서 확인됨)
                        bid_data = data_obj.get('bids', data_obj.get('bid', []))
                        ask_data = data_obj.get('asks', data_obj.get('ask', []))
                        
                        # Debug: bids가 없으면 로그 출력
                        if not bid_data and not ask_data:
                            print(f"Coinone ORDERBOOK data structure for {target_currency}: {json.dumps(data_obj, indent=2)[:500]}")
                        
                        if isinstance(bid_data, list) and len(bid_data) > 0:
                            bids = [(float(item.get('price', 0)), float(item.get('qty', item.get('quantity', 0)))) 
                                    for item in bid_data[:ORDERBOOK_DEPTH] 
                                    if item.get('price') and (item.get('qty') or item.get('quantity'))]
                        
                        if isinstance(ask_data, list) and len(ask_data) > 0:
                            asks = [(float(item.get('price', 0)), float(item.get('qty', item.get('quantity', 0)))) 
                                    for item in ask_data[:ORDERBOOK_DEPTH] 
                                    if item.get('price') and (item.get('qty') or item.get('quantity'))]
                        
                        # Sort bids descending (highest first), asks ascending (lowest first)
                        bids = sorted(bids, key=lambda x: x[0], reverse=True)
                        asks = sorted(asks, key=lambda x: x[0])
                        
                        with self.lock:
                            self.orderbook_data[target_currency] = {
                                'bids': bids,
                                'asks': asks,
                                'timestamp': time.time()
                            }
                        if target_currency in self.callbacks:
                            self.callbacks[target_currency]('orderbook', self.orderbook_data[target_currency])
        except Exception as e:
            print(f"Coinone WebSocket message error: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_error(self, ws, error):
        print(f"Coinone WebSocket error: {error}")
        self.is_connected = False
        self.connected_event.clear()
    
    def _on_close(self, ws, close_status_code, close_msg):
        print("Coinone WebSocket closed")
        self.is_connected = False
        self.connected_event.clear()
    
    def _on_open(self, ws):
        print("Coinone WebSocket opened, waiting for CONNECTED...")
    
    def _run_websocket(self):
        self.ws.run_forever()
    
    def connect(self, coins: list, callback: Optional[Callable] = None):
        """Connect to Coinone WebSocket and subscribe to ticker and orderbook"""
        # Store callbacks
        for coin in coins:
            if callback:
                self.callbacks[coin.upper()] = callback
        
        self.ws = websocket.WebSocketApp(
            COINONE_WS_URL,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Start WebSocket thread
        self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self.ws_thread.start()
        
        # Wait for connection
        if self.connected_event.wait(timeout=10):
            # Subscribe to ticker and orderbook for each coin
            for coin in coins:
                coin_upper = coin.upper()
                
                # Subscribe to TICKER
                ticker_subscribe = {
                    "request_type": "SUBSCRIBE",
                    "channel": "TICKER",
                    "topic": {
                        "quote_currency": "KRW",
                        "target_currency": coin_upper
                    },
                    "format": "DEFAULT"
                }
                self.ws.send(json.dumps(ticker_subscribe))
                time.sleep(0.1)  # Small delay between subscriptions
                
                # Subscribe to ORDERBOOK
                orderbook_subscribe = {
                    "request_type": "SUBSCRIBE",
                    "channel": "ORDERBOOK",
                    "topic": {
                        "quote_currency": "KRW",
                        "target_currency": coin_upper
                    },
                    "format": "DEFAULT"
                }
                self.ws.send(json.dumps(orderbook_subscribe))
                time.sleep(0.1)  # Small delay between subscriptions
            
            print(f"Coinone subscribed to {len(coins)} coins")
        else:
            print("Coinone WebSocket connection timeout")
    
    def get_ticker(self, coin: str) -> Optional[Dict]:
        """Get current ticker data"""
        coin_upper = coin.upper()
        with self.lock:
            ticker = self.ticker_data.get(coin_upper)
            if ticker:
                # If bid/ask prices are not in ticker, try to get from orderbook
                if not ticker.get('bid_price') or not ticker.get('ask_price'):
                    orderbook = self.orderbook_data.get(coin_upper)
                    if orderbook:
                        bids = orderbook.get('bids', [])
                        asks = orderbook.get('asks', [])
                        if bids and asks:
                            ticker['bid_price'] = bids[0][0]  # Highest bid
                            ticker['ask_price'] = asks[0][0]  # Lowest ask
            return ticker
    
    def get_orderbook(self, coin: str) -> Optional[Dict]:
        """Get current orderbook data"""
        coin_upper = coin.upper()
        with self.lock:
            return self.orderbook_data.get(coin_upper)
    
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
        """Calculate order book depth"""
        orderbook = self.get_orderbook(coin)
        if not orderbook:
            return None
        
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        if not bids or not asks:
            return None
        
        bid_depth = sum(price * size for price, size in bids)
        ask_depth = sum(price * size for price, size in asks)
        
        return (bid_depth + ask_depth) / 2
    
    def disconnect(self):
        """Disconnect WebSocket"""
        if self.ws:
            self.ws.close()
        self.is_connected = False
        self.connected_event.clear()
