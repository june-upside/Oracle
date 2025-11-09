"""
거래소 가격 데이터 수집 모듈
CCTX를 사용하여 여러 거래소에서 가격 정보를 가져옵니다.
병렬 처리를 통해 모든 거래소 API를 동시에 호출하여 시간 동기화 문제를 해결합니다.
"""
import ccxt
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


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
    
    def _fetch_upbit_eth_krw(self) -> Tuple[str, Optional[float], float]:
        """업비트 ETH/KRW 가격 수집 (병렬 처리용)"""
        timestamp = time.time()
        try:
            ticker = self.upbit.fetch_ticker('ETH/KRW')
            price = float(ticker['last'])
            self.price_cache['upbit_eth_krw'] = price
            self.cache_timestamp['upbit_eth_krw'] = timestamp
            return ('upbit_eth_krw', price, timestamp)
        except Exception as e:
            print(f"업비트 ETH/KRW 가격 수집 실패: {e}")
            return ('upbit_eth_krw', self.price_cache.get('upbit_eth_krw'), timestamp)
    
    def _fetch_upbit_usdt_krw(self) -> Tuple[str, Optional[float], float]:
        """업비트 USDT/KRW 가격 수집 (병렬 처리용)"""
        timestamp = time.time()
        try:
            ticker = self.upbit.fetch_ticker('USDT/KRW')
            price = float(ticker['last'])
            self.price_cache['upbit_usdt_krw'] = price
            self.cache_timestamp['upbit_usdt_krw'] = timestamp
            return ('upbit_usdt_krw', price, timestamp)
        except Exception as e:
            print(f"업비트 USDT/KRW 가격 수집 실패: {e}")
            return ('upbit_usdt_krw', self.price_cache.get('upbit_usdt_krw'), timestamp)
    
    def _fetch_overseas_price(self, exchange_name: str, exchange) -> Tuple[str, Optional[float], float]:
        """해외 거래소 ETH/USDT 가격 수집 (병렬 처리용)"""
        timestamp = time.time()
        try:
            ticker = exchange.fetch_ticker('ETH/USDT')
            price = float(ticker['last'])
            cache_key = f'{exchange_name}_eth_usdt'
            self.price_cache[cache_key] = price
            self.cache_timestamp[cache_key] = timestamp
            return (exchange_name, price, timestamp)
        except Exception as e:
            print(f"{exchange_name} ETH/USDT 가격 수집 실패: {e}")
            cache_key = f'{exchange_name}_eth_usdt'
            return (exchange_name, self.price_cache.get(cache_key), timestamp)
    
    def get_upbit_eth_krw(self) -> Optional[float]:
        """업비트에서 ETH/KRW 가격 가져오기 (하위 호환성)"""
        _, price, _ = self._fetch_upbit_eth_krw()
        return price
    
    def get_upbit_usdt_krw(self) -> Optional[float]:
        """업비트에서 USDT/KRW 가격 가져오기 (하위 호환성)"""
        _, price, _ = self._fetch_upbit_usdt_krw()
        return price
    
    def get_overseas_eth_usdt(self) -> Dict[str, Optional[float]]:
        """해외 거래소에서 ETH/USDT 가격 가져오기 (하위 호환성)"""
        prices = {}
        for exchange_name, exchange in self.overseas_exchanges:
            _, price, _ = self._fetch_overseas_price(exchange_name, exchange)
            prices[exchange_name] = price
        return prices
    
    def get_all_prices(self) -> Dict:
        """
        모든 가격 정보를 병렬로 수집
        모든 거래소 API를 동시에 호출하여 시간 동기화 문제를 해결합니다.
        """
        # 수집 시작 시간 기록
        collection_start_time = time.time()
        
        # 모든 작업을 동시에 실행
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            # 업비트 가격 수집 작업
            futures.append(executor.submit(self._fetch_upbit_eth_krw))
            futures.append(executor.submit(self._fetch_upbit_usdt_krw))
            
            # 해외 거래소 가격 수집 작업
            for exchange_name, exchange in self.overseas_exchanges:
                futures.append(executor.submit(
                    self._fetch_overseas_price, 
                    exchange_name, 
                    exchange
                ))
            
            # 결과 수집
            results = {}
            timestamps = {}
            overseas_prices = {}
            
            for future in as_completed(futures):
                try:
                    key, price, timestamp = future.result()
                    
                    if key == 'upbit_eth_krw':
                        results['upbit_eth_krw'] = price
                        timestamps['upbit_eth_krw'] = timestamp
                    elif key == 'upbit_usdt_krw':
                        results['upbit_usdt_krw'] = price
                        timestamps['upbit_usdt_krw'] = timestamp
                    else:
                        # 해외 거래소
                        overseas_prices[key] = price
                        timestamps[f'{key}_eth_usdt'] = timestamp
                        
                except Exception as e:
                    print(f"가격 수집 중 오류 발생: {e}")
        
        # 수집 완료 시간
        collection_end_time = time.time()
        collection_duration = collection_end_time - collection_start_time
        
        # 타임스탬프 동기화 정보 계산
        valid_timestamps = [ts for ts in timestamps.values() if ts is not None]
        if valid_timestamps:
            max_timestamp = max(valid_timestamps)
            min_timestamp = min(valid_timestamps)
            time_diff = max_timestamp - min_timestamp
        else:
            time_diff = 0
        
        # 타임스탬프 차이가 너무 크면 경고
        if time_diff > 0.5:  # 500ms 이상 차이
            print(f"⚠️ 경고: 거래소 간 타임스탬프 차이가 큼 ({time_diff*1000:.1f}ms)")
        
        return {
            'upbit_eth_krw': results.get('upbit_eth_krw'),
            'upbit_usdt_krw': results.get('upbit_usdt_krw'),
            'overseas_eth_usdt': overseas_prices,
            'timestamp': datetime.now().isoformat(),
            'collection_metadata': {
                'collection_start': collection_start_time,
                'collection_end': collection_end_time,
                'collection_duration_ms': round(collection_duration * 1000, 2),
                'max_timestamp_diff_ms': round(time_diff * 1000, 2),
            }
        }


if __name__ == '__main__':
    # 테스트
    fetcher = PriceFetcher()
    prices = fetcher.get_all_prices()
    print(prices)

