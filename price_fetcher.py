"""
거래소 가격 데이터 수집 모듈
CCTX를 사용하여 여러 거래소에서 가격 정보를 가져옵니다.
"""
import ccxt
import time
from typing import Dict, Optional, List
from datetime import datetime


class PriceFetcher:
    """거래소 가격 수집 클래스"""
    
    def __init__(self):
        """거래소 초기화"""
        # 업비트 (국내)
        self.upbit = ccxt.upbit({
            'enableRateLimit': True,
        })
        
        # 해외 거래소들
        self.binance = ccxt.binance({
            'enableRateLimit': True,
        })
        
        self.okx = ccxt.okx({
            'enableRateLimit': True,
        })
        
        # 추가 해외 거래소들 (선택적)
        self.coinbase = None
        self.kraken = None
        self.bybit = None
        
        # Coinbase 초기화 시도
        try:
            if hasattr(ccxt, 'coinbase'):
                self.coinbase = ccxt.coinbase({'enableRateLimit': True})
            elif hasattr(ccxt, 'coinbasepro'):
                self.coinbase = ccxt.coinbasepro({'enableRateLimit': True})
        except Exception as e:
            print(f"경고: Coinbase 거래소 초기화 실패: {e}")
        
        # Kraken 초기화 시도
        try:
            if hasattr(ccxt, 'kraken'):
                self.kraken = ccxt.kraken({'enableRateLimit': True})
        except Exception as e:
            print(f"경고: Kraken 거래소 초기화 실패: {e}")
        
        # Bybit 초기화 시도
        try:
            if hasattr(ccxt, 'bybit'):
                self.bybit = ccxt.bybit({'enableRateLimit': True})
        except Exception as e:
            print(f"경고: Bybit 거래소 초기화 실패: {e}")
        
        # 해외 거래소 리스트 (초기화된 거래소만 추가)
        self.overseas_exchanges = [
            ('binance', self.binance),
            ('okx', self.okx),
        ]
        if self.coinbase is not None:
            self.overseas_exchanges.append(('coinbase', self.coinbase))
        if self.kraken is not None:
            self.overseas_exchanges.append(('kraken', self.kraken))
        if self.bybit is not None:
            self.overseas_exchanges.append(('bybit', self.bybit))
        
        # 가격 캐시 (최근 가격 저장)
        self.price_cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 1  # 1초 캐시
        
    def get_upbit_eth_krw(self) -> Optional[float]:
        """업비트에서 ETH/KRW 가격 가져오기"""
        try:
            ticker = self.upbit.fetch_ticker('ETH/KRW')
            price = float(ticker['last'])
            self.price_cache['upbit_eth_krw'] = price
            self.cache_timestamp['upbit_eth_krw'] = time.time()
            return price
        except Exception as e:
            print(f"업비트 ETH/KRW 가격 수집 실패: {e}")
            return self.price_cache.get('upbit_eth_krw')
    
    def get_upbit_usdt_krw(self) -> Optional[float]:
        """업비트에서 USDT/KRW 가격 가져오기"""
        try:
            ticker = self.upbit.fetch_ticker('USDT/KRW')
            price = float(ticker['last'])
            self.price_cache['upbit_usdt_krw'] = price
            self.cache_timestamp['upbit_usdt_krw'] = time.time()
            return price
        except Exception as e:
            print(f"업비트 USDT/KRW 가격 수집 실패: {e}")
            return self.price_cache.get('upbit_usdt_krw')
    
    def get_overseas_eth_usdt(self) -> Dict[str, Optional[float]]:
        """해외 거래소에서 ETH/USDT 가격 가져오기"""
        prices = {}
        
        for exchange_name, exchange in self.overseas_exchanges:
            try:
                ticker = exchange.fetch_ticker('ETH/USDT')
                price = float(ticker['last'])
                prices[exchange_name] = price
                cache_key = f'{exchange_name}_eth_usdt'
                self.price_cache[cache_key] = price
                self.cache_timestamp[cache_key] = time.time()
            except Exception as e:
                print(f"{exchange_name} ETH/USDT 가격 수집 실패: {e}")
                # 캐시에서 가져오기 시도
                cache_key = f'{exchange_name}_eth_usdt'
                prices[exchange_name] = self.price_cache.get(cache_key)
        
        return prices
    
    def get_all_prices(self) -> Dict:
        """모든 가격 정보 수집"""
        return {
            'upbit_eth_krw': self.get_upbit_eth_krw(),
            'upbit_usdt_krw': self.get_upbit_usdt_krw(),
            'overseas_eth_usdt': self.get_overseas_eth_usdt(),
            'timestamp': datetime.now().isoformat(),
        }


if __name__ == '__main__':
    # 테스트
    fetcher = PriceFetcher()
    prices = fetcher.get_all_prices()
    print(prices)

