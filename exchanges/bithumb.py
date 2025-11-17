import requests
import time
from typing import Dict, Optional
from config import BITHUMB_REST_URL, ORDERBOOK_DEPTH


class BithumbClient:
    def __init__(self):
        self.base_url = BITHUMB_REST_URL
        self.ticker_cache = {}
        self.orderbook_cache = {}
        self.cache_timeout = 1.0  # 1 second cache
    
    def _get_ticker(self, coin: str) -> Optional[Dict]:
        """Get ticker data from Bithumb API"""
        try:
            url = f"{self.base_url}/ticker/{coin}_KRW"
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                ticker = data.get('data', {})
                # 빗썸 ticker API에는 bid/ask 가격이 없으므로 orderbook에서 가져옴
                orderbook = self._get_orderbook_direct(coin)
                bid_price = 0.0
                ask_price = 0.0
                
                if orderbook:
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                    if bids and len(bids) > 0:
                        bid_price = bids[0][0]  # Highest bid
                    if asks and len(asks) > 0:
                        ask_price = asks[0][0]  # Lowest ask
                
                return {
                    'price': float(ticker.get('closing_price', 0)),
                    'volume': float(ticker.get('acc_trade_value_24H', 0)),
                    'bid_price': bid_price,
                    'ask_price': ask_price,
                    'timestamp': time.time()
                }
        except Exception as e:
            print(f"Bithumb ticker error for {coin}: {e}")
        return None
    
    def _get_orderbook(self, coin: str) -> Optional[Dict]:
        """Get orderbook data from Bithumb API"""
        try:
            url = f"{self.base_url}/orderbook/{coin}_KRW"
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                orderbook = data.get('data', {})
                bids = [(float(item['price']), float(item['quantity'])) 
                        for item in orderbook.get('bids', [])[:ORDERBOOK_DEPTH]]
                asks = [(float(item['price']), float(item['quantity'])) 
                        for item in orderbook.get('asks', [])[:ORDERBOOK_DEPTH]]
                
                return {
                    'bids': bids,
                    'asks': asks,
                    'timestamp': time.time()
                }
        except Exception as e:
            print(f"Bithumb orderbook error for {coin}: {e}")
        return None
    
    def get_ticker(self, coin: str) -> Optional[Dict]:
        """Get ticker with caching"""
        cache_key = coin
        now = time.time()
        
        if cache_key in self.ticker_cache:
            cached_data, cached_time = self.ticker_cache[cache_key]
            if now - cached_time < self.cache_timeout:
                return cached_data
        
        data = self._get_ticker(coin)
        if data:
            self.ticker_cache[cache_key] = (data, now)
        return data
    
    def _get_orderbook_direct(self, coin: str) -> Optional[Dict]:
        """Get orderbook data directly from API (not cached)"""
        try:
            url = f"{self.base_url}/orderbook/{coin}_KRW"
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                orderbook = data.get('data', {})
                bids = [(float(item['price']), float(item['quantity'])) 
                        for item in orderbook.get('bids', [])[:ORDERBOOK_DEPTH]]
                asks = [(float(item['price']), float(item['quantity'])) 
                        for item in orderbook.get('asks', [])[:ORDERBOOK_DEPTH]]
                
                return {
                    'bids': bids,
                    'asks': asks,
                    'timestamp': time.time()
                }
        except Exception as e:
            print(f"Bithumb orderbook error for {coin}: {e}")
        return None
    
    def get_orderbook(self, coin: str) -> Optional[Dict]:
        """Get orderbook with caching"""
        cache_key = coin
        now = time.time()
        
        if cache_key in self.orderbook_cache:
            cached_data, cached_time = self.orderbook_cache[cache_key]
            if now - cached_time < self.cache_timeout:
                return cached_data
        
        data = self._get_orderbook(coin)
        if data:
            self.orderbook_cache[cache_key] = (data, now)
        return data
    
    def calculate_spread(self, coin: str) -> Optional[float]:
        """Calculate spread percentage"""
        ticker = self.get_ticker(coin)
        if not ticker:
            return None
        
        bid = ticker.get('bid_price', 0)
        ask = ticker.get('ask_price', 0)
        
        # Debug: 빗썸 bid/ask 가격 확인
        if bid == 0 or ask == 0:
            print(f"Bithumb bid/ask is 0 for {coin}, bid: {bid}, ask: {ask}, ticker: {ticker}")
            return None
        
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

