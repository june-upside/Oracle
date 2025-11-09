"""
거래소 가격 데이터 수집 모듈
업비트는 웹소켓을 사용하고, 다른 거래소는 CCXT를 사용합니다.
병렬 처리를 통해 모든 거래소 API를 동시에 호출하여 시간 동기화 문제를 해결합니다.
"""
import ccxt
import time
import json
import threading
import uuid
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("경고: websocket-client가 설치되지 않았습니다. 업비트 웹소켓을 사용하려면 'pip install websocket-client'를 실행하세요.")


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
        
        # 업비트 웹소켓 관련 변수
        self.upbit_ws = None
        self.upbit_ws_thread = None
        self.upbit_ws_running = False
        self.upbit_ws_lock = threading.Lock()
        
        # 업비트 웹소켓 초기화 (websocket-client가 있는 경우)
        if WEBSOCKET_AVAILABLE:
            self._init_upbit_websocket()
    
    def _process_upbit_ticker(self, data: dict):
        """업비트 티커 데이터 처리"""
        try:
            code = data['code']
            price = float(data['trade_price'])
            timestamp = time.time()
            
            with self.upbit_ws_lock:
                if code == 'KRW-ETH':
                    self.price_cache['upbit_eth_krw'] = price
                    self.cache_timestamp['upbit_eth_krw'] = timestamp
                elif code == 'KRW-USDT':
                    self.price_cache['upbit_usdt_krw'] = price
                    self.cache_timestamp['upbit_usdt_krw'] = timestamp
        except Exception as e:
            print(f"업비트 티커 데이터 처리 오류: {e}")
    
    def _init_upbit_websocket(self):
        """업비트 웹소켓 초기화 및 연결"""
        if not WEBSOCKET_AVAILABLE:
            return
        
        def on_message(ws, message):
            """웹소켓 메시지 수신 핸들러"""
            try:
                # 업비트 웹소켓은 JSON 문자열을 보냄
                data = json.loads(message)
                
                # 배열 형식일 수도 있고, 단일 객체일 수도 있음
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'code' in item and 'trade_price' in item:
                            self._process_upbit_ticker(item)
                elif isinstance(data, dict) and 'code' in data and 'trade_price' in data:
                    self._process_upbit_ticker(data)
            except json.JSONDecodeError:
                # 바이너리 형식일 수 있음 (압축된 경우)
                try:
                    import gzip
                    decompressed = gzip.decompress(message).decode('utf-8')
                    data = json.loads(decompressed)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'code' in item and 'trade_price' in item:
                                self._process_upbit_ticker(item)
                    elif isinstance(data, dict) and 'code' in data and 'trade_price' in data:
                        self._process_upbit_ticker(data)
                except Exception as e:
                    print(f"업비트 웹소켓 메시지 압축 해제 오류: {e}")
            except Exception as e:
                print(f"업비트 웹소켓 메시지 처리 오류: {e}")
        
        def on_error(ws, error):
            """웹소켓 오류 핸들러"""
            print(f"업비트 웹소켓 오류: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            """웹소켓 연결 종료 핸들러"""
            print("업비트 웹소켓 연결 종료")
            was_running = self.upbit_ws_running
            self.upbit_ws_running = False
            # 재연결 시도 (의도적으로 종료한 경우가 아닐 때)
            if was_running:
                time.sleep(5)
                self._init_upbit_websocket()
        
        def on_open(ws):
            """웹소켓 연결 성공 핸들러"""
            print("업비트 웹소켓 연결 성공")
            # 티커 구독 요청
            ticket = str(uuid.uuid4())
            subscribe_message = [
                {"ticket": ticket},
                {
                    "type": "ticker",
                    "codes": ["KRW-ETH", "KRW-USDT"]
                }
            ]
            ws.send(json.dumps(subscribe_message))
        
        def run_websocket():
            """웹소켓 실행 함수"""
            ws_url = "wss://api.upbit.com/websocket/v1"
            self.upbit_ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            self.upbit_ws_running = True
            self.upbit_ws.run_forever()
        
        # 웹소켓을 별도 스레드에서 실행
        self.upbit_ws_thread = threading.Thread(target=run_websocket, daemon=True)
        self.upbit_ws_thread.start()
    
    def _fetch_upbit_eth_krw(self) -> Tuple[str, Optional[float], float]:
        """업비트 ETH/KRW 가격 수집 (웹소켓 캐시 사용 또는 폴백)"""
        timestamp = time.time()
        
        # 웹소켓 캐시에서 가격 가져오기
        with self.upbit_ws_lock:
            cached_price = self.price_cache.get('upbit_eth_krw')
            cached_timestamp = self.cache_timestamp.get('upbit_eth_krw', 0)
            
            # 캐시된 가격이 있고 최근 것(5초 이내)이면 사용
            if cached_price is not None and (timestamp - cached_timestamp) < 5:
                return ('upbit_eth_krw', cached_price, cached_timestamp)
        
        # 웹소켓이 없거나 캐시가 오래된 경우 REST API 폴백
        try:
            ticker = self.upbit.fetch_ticker('ETH/KRW')
            price = float(ticker['last'])
            with self.upbit_ws_lock:
                self.price_cache['upbit_eth_krw'] = price
                self.cache_timestamp['upbit_eth_krw'] = timestamp
            return ('upbit_eth_krw', price, timestamp)
        except Exception as e:
            print(f"업비트 ETH/KRW 가격 수집 실패: {e}")
            return ('upbit_eth_krw', cached_price, timestamp)
    
    def _fetch_upbit_usdt_krw(self) -> Tuple[str, Optional[float], float]:
        """업비트 USDT/KRW 가격 수집 (웹소켓 캐시 사용 또는 폴백)"""
        timestamp = time.time()
        
        # 웹소켓 캐시에서 가격 가져오기
        with self.upbit_ws_lock:
            cached_price = self.price_cache.get('upbit_usdt_krw')
            cached_timestamp = self.cache_timestamp.get('upbit_usdt_krw', 0)
            
            # 캐시된 가격이 있고 최근 것(5초 이내)이면 사용
            if cached_price is not None and (timestamp - cached_timestamp) < 5:
                return ('upbit_usdt_krw', cached_price, cached_timestamp)
        
        # 웹소켓이 없거나 캐시가 오래된 경우 REST API 폴백
        try:
            ticker = self.upbit.fetch_ticker('USDT/KRW')
            price = float(ticker['last'])
            with self.upbit_ws_lock:
                self.price_cache['upbit_usdt_krw'] = price
                self.cache_timestamp['upbit_usdt_krw'] = timestamp
            return ('upbit_usdt_krw', price, timestamp)
        except Exception as e:
            print(f"업비트 USDT/KRW 가격 수집 실패: {e}")
            return ('upbit_usdt_krw', cached_price, timestamp)
    
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

