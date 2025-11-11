"""
거래소 가격 데이터 수집 모듈
업비트와 해외 거래소 모두 웹소켓을 사용합니다.
업비트는 직접 웹소켓을 사용하고, 해외 거래소는 CCXT Pro를 사용합니다.
"""
import ccxt
import time
import json
import threading
import uuid
import asyncio
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("경고: websocket-client가 설치되지 않았습니다. 업비트 웹소켓을 사용하려면 'pip install websocket-client'를 실행하세요.")

try:
    import ccxt.pro as ccxtpro
    CCXT_PRO_AVAILABLE = True
except ImportError:
    CCXT_PRO_AVAILABLE = False
    print("경고: ccxt-pro가 설치되지 않았습니다. 해외 거래소 웹소켓을 사용하려면 'pip install ccxt-pro'를 실행하세요.")


class PriceFetcher:
    """거래소 가격 수집 클래스"""
    
    def __init__(self):
        """거래소 초기화"""
        # 업비트 (국내)
        self.upbit = ccxt.upbit({
            'enableRateLimit': True,
        })
        
        # 해외 거래소들 (CCXT Pro 사용)
        self.overseas_exchanges_pro = {}  # CCXT Pro 인스턴스
        self.overseas_exchanges = []  # 거래소 리스트
        
        # CCXT Pro로 해외 거래소 초기화
        if CCXT_PRO_AVAILABLE:
            # Binance 초기화
            try:
                self.binance_pro = ccxtpro.binance({
                    'enableRateLimit': True,
                })
                self.overseas_exchanges_pro['binance'] = self.binance_pro
                self.overseas_exchanges.append(('binance', self.binance_pro))
                print("✅ Binance WebSocket 초기화 완료")
            except Exception as e:
                print(f"경고: Binance 초기화 실패: {e}")
            
            # OKX 초기화
            try:
                self.okx_pro = ccxtpro.okx({
                    'enableRateLimit': True,
                })
                self.overseas_exchanges_pro['okx'] = self.okx_pro
                self.overseas_exchanges.append(('okx', self.okx_pro))
                print("✅ OKX WebSocket 초기화 완료")
            except Exception as e:
                print(f"경고: OKX 초기화 실패: {e}")
            
            # Bybit 초기화
            try:
                if hasattr(ccxtpro, 'bybit'):
                    self.bybit_pro = ccxtpro.bybit({
                        'enableRateLimit': True,
                    })
                    self.overseas_exchanges_pro['bybit'] = self.bybit_pro
                    self.overseas_exchanges.append(('bybit', self.bybit_pro))
                    print("✅ Bybit WebSocket 초기화 완료")
            except Exception as e:
                print(f"경고: Bybit 초기화 실패: {e}")
            
            # Coinbase 초기화
            try:
                if hasattr(ccxtpro, 'coinbase'):
                    self.coinbase_pro = ccxtpro.coinbase({
                        'enableRateLimit': True,
                    })
                    self.overseas_exchanges_pro['coinbase'] = self.coinbase_pro
                    self.overseas_exchanges.append(('coinbase', self.coinbase_pro))
                    print("✅ Coinbase WebSocket 초기화 완료")
                elif hasattr(ccxtpro, 'coinbasepro'):
                    self.coinbase_pro = ccxtpro.coinbasepro({
                        'enableRateLimit': True,
                    })
                    self.overseas_exchanges_pro['coinbase'] = self.coinbase_pro
                    self.overseas_exchanges.append(('coinbase', self.coinbase_pro))
                    print("✅ Coinbase Pro WebSocket 초기화 완료")
            except Exception as e:
                print(f"경고: Coinbase 초기화 실패: {e}")
            
            # Kraken 초기화
            try:
                if hasattr(ccxtpro, 'kraken'):
                    self.kraken_pro = ccxtpro.kraken({
                        'enableRateLimit': True,
                    })
                    self.overseas_exchanges_pro['kraken'] = self.kraken_pro
                    self.overseas_exchanges.append(('kraken', self.kraken_pro))
                    print("✅ Kraken WebSocket 초기화 완료")
            except Exception as e:
                print(f"경고: Kraken 초기화 실패: {e}")
        else:
            # CCXT Pro가 없으면 일반 CCXT 사용 (폴백)
            print("⚠️ CCXT Pro가 없어 해외 거래소는 HTTP 폴링을 사용합니다.")
            try:
                self.binance = ccxt.binance({'enableRateLimit': True})
                self.overseas_exchanges.append(('binance', self.binance))
            except Exception as e:
                print(f"경고: Binance 초기화 실패: {e}")
            
            try:
                self.okx = ccxt.okx({'enableRateLimit': True})
                self.overseas_exchanges.append(('okx', self.okx))
            except Exception as e:
                print(f"경고: OKX 초기화 실패: {e}")
            
            # Coinbase 초기화 (폴백)
            try:
                if hasattr(ccxt, 'coinbase'):
                    self.coinbase = ccxt.coinbase({'enableRateLimit': True})
                    self.overseas_exchanges.append(('coinbase', self.coinbase))
                elif hasattr(ccxt, 'coinbasepro'):
                    self.coinbase = ccxt.coinbasepro({'enableRateLimit': True})
                    self.overseas_exchanges.append(('coinbase', self.coinbase))
            except Exception as e:
                print(f"경고: Coinbase 초기화 실패: {e}")
            
            # Kraken 초기화 (폴백)
            try:
                if hasattr(ccxt, 'kraken'):
                    self.kraken = ccxt.kraken({'enableRateLimit': True})
                    self.overseas_exchanges.append(('kraken', self.kraken))
            except Exception as e:
                print(f"경고: Kraken 초기화 실패: {e}")
        
        # 해외 거래소 WebSocket 관련 변수
        self.overseas_ws_tasks = {}  # asyncio 태스크 저장
        self.overseas_ws_loops = {}  # 각 거래소별 이벤트 루프
        self.overseas_ws_threads = {}  # 각 거래소별 스레드
        self.overseas_ws_running = {}  # 실행 상태
        self.overseas_ws_lock = threading.Lock()
        
        # 해외 거래소 WebSocket 초기화
        if CCXT_PRO_AVAILABLE:
            self._init_overseas_websockets()
        
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
    
    def _process_overseas_ticker(self, exchange_name: str, ticker: dict):
        """해외 거래소 티커 데이터 처리"""
        try:
            if ticker is None:
                return
            
            # CCXT Pro 티커 형식에서 가격 추출
            price = ticker.get('last') or ticker.get('close')
            if price is None:
                return
            
            price = float(price)
            
            # 타임스탬프 추출
            timestamp = ticker.get('timestamp')
            if timestamp is None:
                timestamp = time.time()
            elif timestamp > 1e10:
                timestamp = timestamp / 1000.0  # ms를 초로 변환
            
            cache_key = f'{exchange_name}_eth_usdt'
            with self.overseas_ws_lock:
                self.price_cache[cache_key] = price
                self.cache_timestamp[cache_key] = timestamp
        except (KeyError, ValueError, TypeError) as e:
            print(f"{exchange_name} 티커 데이터 처리 오류: {e}, 데이터: {ticker}")
    
    def _init_overseas_websockets(self):
        """해외 거래소 WebSocket 초기화 및 연결"""
        if not CCXT_PRO_AVAILABLE:
            return
        
        async def watch_ticker_loop(exchange_name: str, exchange):
            """각 거래소별 티커 수신 루프"""
            try:
                while self.overseas_ws_running.get(exchange_name, False):
                    try:
                        # CCXT Pro의 watch_ticker 사용
                        ticker = await exchange.watch_ticker('ETH/USDT')
                        self._process_overseas_ticker(exchange_name, ticker)
                    except Exception as e:
                        print(f"{exchange_name} WebSocket 티커 수신 오류: {e}")
                        await asyncio.sleep(1)  # 오류 시 1초 대기 후 재시도
            except Exception as e:
                print(f"{exchange_name} WebSocket 루프 오류: {e}")
            finally:
                self.overseas_ws_running[exchange_name] = False
        
        def run_async_loop(exchange_name: str, exchange):
            """각 거래소별 이벤트 루프 실행"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.overseas_ws_loops[exchange_name] = loop
            
            try:
                self.overseas_ws_running[exchange_name] = True
                loop.run_until_complete(watch_ticker_loop(exchange_name, exchange))
            except Exception as e:
                print(f"{exchange_name} 이벤트 루프 오류: {e}")
            finally:
                loop.close()
        
        # 각 거래소별로 WebSocket 스레드 시작
        for exchange_name, exchange in self.overseas_exchanges:
            if exchange_name in self.overseas_exchanges_pro:
                thread = threading.Thread(
                    target=run_async_loop,
                    args=(exchange_name, exchange),
                    daemon=True
                )
                thread.start()
                self.overseas_ws_threads[exchange_name] = thread
                print(f"✅ {exchange_name} WebSocket 스레드 시작")
    
    def _process_upbit_ticker(self, data: dict):
        """업비트 티커 데이터 처리"""
        try:
            # 레퍼런스에 따라 필드명 확인 (trade_price 또는 tp)
            code = data.get('code') or data.get('cd')
            if not code:
                return
            
            # trade_price 또는 tp 필드에서 가격 가져오기
            price = data.get('trade_price') or data.get('tp')
            if price is None:
                return
            
            price = float(price)
            
            # 타임스탬프는 tms (ms) 또는 timestamp 사용, 없으면 현재 시간
            timestamp_ms = data.get('timestamp') or data.get('tms')
            if timestamp_ms:
                timestamp = float(timestamp_ms) / 1000.0  # ms를 초로 변환
            else:
                timestamp = time.time()
            
            # stream_type 확인 (SNAPSHOT 또는 REALTIME)
            stream_type = data.get('stream_type') or data.get('st', 'REALTIME')
            
            with self.upbit_ws_lock:
                if code == 'KRW-ETH':
                    self.price_cache['upbit_eth_krw'] = price
                    self.cache_timestamp['upbit_eth_krw'] = timestamp
                elif code == 'KRW-USDT':
                    self.price_cache['upbit_usdt_krw'] = price
                    self.cache_timestamp['upbit_usdt_krw'] = timestamp
        except (KeyError, ValueError, TypeError) as e:
            print(f"업비트 티커 데이터 처리 오류: {e}, 데이터: {data}")
    
    def _init_upbit_websocket(self):
        """업비트 웹소켓 초기화 및 연결"""
        if not WEBSOCKET_AVAILABLE:
            return
        
        def on_message(ws, message):
            """웹소켓 메시지 수신 핸들러"""
            try:
                # 업비트 웹소켓은 JSON 문자열을 보냄
                # 레퍼런스에 따르면 단일 객체 또는 배열 형식 가능
                data = json.loads(message)
                
                # 배열 형식인 경우
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            # type이 ticker인 경우만 처리
                            item_type = item.get('type') or item.get('ty')
                            if item_type == 'ticker':
                                self._process_upbit_ticker(item)
                # 단일 객체인 경우
                elif isinstance(data, dict):
                    data_type = data.get('type') or data.get('ty')
                    if data_type == 'ticker':
                        self._process_upbit_ticker(data)
            except json.JSONDecodeError as e:
                print(f"업비트 웹소켓 JSON 파싱 오류: {e}")
            except Exception as e:
                print(f"업비트 웹소켓 메시지 처리 오류: {e}")
        
        def on_error(ws, error):
            """웹소켓 오류 핸들러"""
            print(f"업비트 웹소켓 오류: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            """웹소켓 연결 종료 핸들러"""
            print(f"업비트 웹소켓 연결 종료 (코드: {close_status_code}, 메시지: {close_msg})")
            was_running = self.upbit_ws_running
            self.upbit_ws_running = False
            
            # 재연결 시도 (의도적으로 종료한 경우가 아닐 때)
            # close_status_code가 None이 아니고 정상 종료가 아닌 경우에만 재연결
            if was_running and close_status_code != 1000:
                print("업비트 웹소켓 재연결 시도 중...")
                time.sleep(5)
                # 재연결 시도 (무한 루프 방지를 위해 한 번만)
                if not self.upbit_ws_running:
                    self._init_upbit_websocket()
        
        def on_open(ws):
            """웹소켓 연결 성공 핸들러"""
            print("업비트 웹소켓 연결 성공")
            # 티커 구독 요청 (레퍼런스 형식에 맞춤)
            ticket = str(uuid.uuid4())
            subscribe_message = [
                {"ticket": ticket},
                {
                    "type": "ticker",
                    "codes": ["KRW-ETH", "KRW-USDT"]  # 대문자로 요청 (레퍼런스 요구사항)
                },
                {
                    "format": "DEFAULT"  # 레퍼런스에 따라 format 추가
                }
            ]
            try:
                ws.send(json.dumps(subscribe_message))
                print("업비트 티커 구독 요청 전송 완료")
            except Exception as e:
                print(f"업비트 티커 구독 요청 전송 실패: {e}")
        
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
        """해외 거래소 ETH/USDT 가격 수집 (WebSocket 캐시 사용 또는 폴백)"""
        timestamp = time.time()
        cache_key = f'{exchange_name}_eth_usdt'
        
        # WebSocket 캐시에서 가격 가져오기
        with self.overseas_ws_lock:
            cached_price = self.price_cache.get(cache_key)
            cached_timestamp = self.cache_timestamp.get(cache_key, 0)
            
            # 캐시된 가격이 있고 최근 것(5초 이내)이면 사용
            if cached_price is not None and (timestamp - cached_timestamp) < 5:
                return (exchange_name, cached_price, cached_timestamp)
        
        # WebSocket이 없거나 캐시가 오래된 경우 REST API 폴백
        if CCXT_PRO_AVAILABLE and exchange_name in self.overseas_exchanges_pro:
            # CCXT Pro는 일반 CCXT 인스턴스도 필요할 수 있음
            try:
                # 일반 CCXT로 폴백 시도
                if hasattr(ccxt, exchange_name):
                    fallback_exchange = getattr(ccxt, exchange_name)({'enableRateLimit': True})
                    ticker = fallback_exchange.fetch_ticker('ETH/USDT')
                    price = float(ticker['last'])
                    with self.overseas_ws_lock:
                        self.price_cache[cache_key] = price
                        self.cache_timestamp[cache_key] = timestamp
                    return (exchange_name, price, timestamp)
            except Exception as e:
                print(f"{exchange_name} REST API 폴백 실패: {e}")
        else:
            # 일반 CCXT 사용
            try:
                ticker = exchange.fetch_ticker('ETH/USDT')
                price = float(ticker['last'])
                with self.overseas_ws_lock:
                    self.price_cache[cache_key] = price
                    self.cache_timestamp[cache_key] = timestamp
                return (exchange_name, price, timestamp)
            except Exception as e:
                print(f"{exchange_name} ETH/USDT 가격 수집 실패: {e}")
        
        # 모든 방법 실패 시 캐시된 값 반환
        return (exchange_name, cached_price, timestamp)
    
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

