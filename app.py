"""
Flask 웹 애플리케이션
가격 오라클 대시보드를 제공합니다.
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import time
from datetime import datetime
from price_fetcher import PriceFetcher
from oracle import Oracle

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 전역 변수
price_fetcher = PriceFetcher()
oracle = Oracle(twap_window_seconds=300, volatility_threshold=0.05)

# 최신 데이터 저장
latest_data = {
    'prices': None,
    'oracle_result': None,
    'timestamp': None,
}

# 가격 히스토리 (차트용, 최대 100개 데이터 포인트)
price_history = {
    'timestamps': [],
    'median_prices': [],
    'upbit_eth_krw': [],
    'upbit_usdt_krw': [],
    'max_points': 100,
}

# 데이터 업데이트 스레드
update_lock = threading.Lock()
running = True

def update_prices():
    """주기적으로 가격 데이터 업데이트 및 웹소켓으로 브로드캐스트"""
    global latest_data, running
    
    while running:
        try:
            update_start = time.time()
            
            # 가격 데이터 수집 (병렬 처리로 빠르게)
            prices = price_fetcher.get_all_prices()
            
            # 오라클 계산
            oracle_result = oracle.calculate_median_eth_krw_price(
                upbit_eth_krw=prices['upbit_eth_krw'],
                upbit_usdt_krw=prices['upbit_usdt_krw'],
                overseas_eth_usdt=prices['overseas_eth_usdt'],
                use_manual_usdt_krw=oracle.manual_usdt_krw_override is not None,
                use_manual_eth_krw=oracle.manual_eth_krw_override is not None
            )
            
            timestamp = datetime.now().isoformat()
            
            # 가격 히스토리 업데이트 (차트용)
            price_history_snapshot = None
            with update_lock:
                latest_data = {
                    'prices': prices,
                    'oracle_result': oracle_result,
                    'timestamp': timestamp,
                }
                
                if oracle_result.get('median_price') is not None:
                    price_history['timestamps'].append(timestamp)
                    price_history['median_prices'].append(oracle_result['median_price'])
                    # None 값 대신 0 또는 이전 값 사용
                    upbit_eth = prices.get('upbit_eth_krw') if prices.get('upbit_eth_krw') is not None else 0
                    upbit_usdt = prices.get('upbit_usdt_krw') if prices.get('upbit_usdt_krw') is not None else 0
                    price_history['upbit_eth_krw'].append(upbit_eth)
                    price_history['upbit_usdt_krw'].append(upbit_usdt)
                    
                    # 최대 포인트 수 제한
                    if len(price_history['timestamps']) > price_history['max_points']:
                        price_history['timestamps'].pop(0)
                        price_history['median_prices'].pop(0)
                        price_history['upbit_eth_krw'].pop(0)
                        price_history['upbit_usdt_krw'].pop(0)
                
                # 히스토리 스냅샷 생성 (락 내에서 빠르게)
                price_history_snapshot = {
                    'timestamps': price_history['timestamps'].copy(),
                    'median_prices': price_history['median_prices'].copy(),
                    'upbit_eth_krw': price_history['upbit_eth_krw'].copy(),
                    'upbit_usdt_krw': price_history['upbit_usdt_krw'].copy(),
                }
            
            # 웹소켓으로 데이터 브로드캐스트 (락 밖에서 실행하여 블로킹 최소화)
            data_to_send = {
                'prices': prices,
                'oracle_result': oracle_result,
                'timestamp': timestamp,
                'price_history': price_history_snapshot,
            }
            
            # 비동기 브로드캐스트 (모든 클라이언트에게 즉시 전송)
            socketio.emit('price_update', data_to_send, namespace='/')
            
            update_duration = (time.time() - update_start) * 1000
            print(f"가격 업데이트 완료: {datetime.now()} (소요: {update_duration:.1f}ms)")
            
        except Exception as e:
            print(f"가격 업데이트 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # 병렬 처리로 속도가 빨라졌으므로 0.5초마다 업데이트 (더 빠른 반응성)
        time.sleep(0.5)

@app.route('/')
def index():
    """메인 대시보드 페이지"""
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """현재 가격 데이터 API (웹소켓 미지원 클라이언트용)"""
    with update_lock:
        data = latest_data.copy()
        data['price_history'] = price_history.copy()
        return jsonify(data)

@socketio.on('connect')
def handle_connect():
    """클라이언트 연결 시 최신 데이터 즉시 전송"""
    print('클라이언트 연결됨')
    with update_lock:
        data = latest_data.copy()
        if data.get('prices') is not None:  # 데이터가 있을 때만 전송
            data['price_history'] = {
                'timestamps': price_history['timestamps'].copy(),
                'median_prices': price_history['median_prices'].copy(),
                'upbit_eth_krw': price_history['upbit_eth_krw'].copy(),
                'upbit_usdt_krw': price_history['upbit_usdt_krw'].copy(),
            }
            emit('price_update', data)

@socketio.on('disconnect')
def handle_disconnect():
    """클라이언트 연결 해제"""
    print('클라이언트 연결 해제됨')

@app.route('/api/usdt-krw/manual', methods=['POST'])
def set_manual_usdt_krw():
    """USDT/KRW 수동 가격 설정"""
    data = request.get_json()
    price = data.get('price')
    
    if price is None:
        oracle.set_manual_usdt_krw(None)
        return jsonify({'success': True, 'message': '수동 가격 해제됨'})
    
    try:
        price = float(price)
        oracle.set_manual_usdt_krw(price)
        return jsonify({'success': True, 'message': f'USDT/KRW 가격이 {price}로 설정됨'})
    except ValueError:
        return jsonify({'success': False, 'message': '잘못된 가격 형식'}), 400

@app.route('/api/usdt-krw/manual', methods=['GET'])
def get_manual_usdt_krw():
    """USDT/KRW 수동 가격 조회"""
    manual_price = oracle.get_manual_usdt_krw()
    return jsonify({'manual_price': manual_price})

@app.route('/api/eth-krw/manual', methods=['POST'])
def set_manual_eth_krw():
    """ETH/KRW 수동 가격 설정"""
    data = request.get_json()
    price = data.get('price')
    
    if price is None:
        oracle.set_manual_eth_krw(None)
        return jsonify({'success': True, 'message': '수동 가격 해제됨'})
    
    try:
        price = float(price)
        oracle.set_manual_eth_krw(price)
        return jsonify({'success': True, 'message': f'ETH/KRW 가격이 {price}로 설정됨'})
    except ValueError:
        return jsonify({'success': False, 'message': '잘못된 가격 형식'}), 400

@app.route('/api/eth-krw/manual', methods=['GET'])
def get_manual_eth_krw():
    """ETH/KRW 수동 가격 조회"""
    manual_price = oracle.get_manual_eth_krw()
    return jsonify({'manual_price': manual_price})

@app.route('/api/oracle/update', methods=['POST'])
def force_update():
    """수동으로 가격 업데이트 강제 실행"""
    try:
        prices = price_fetcher.get_all_prices()
        oracle_result = oracle.calculate_median_eth_krw_price(
            upbit_eth_krw=prices['upbit_eth_krw'],
            upbit_usdt_krw=prices['upbit_usdt_krw'],
            overseas_eth_usdt=prices['overseas_eth_usdt'],
            use_manual_usdt_krw=oracle.manual_usdt_krw_override is not None,
            use_manual_eth_krw=oracle.manual_eth_krw_override is not None
        )
        
        timestamp = datetime.now().isoformat()
        
        with update_lock:
            latest_data = {
                'prices': prices,
                'oracle_result': oracle_result,
                'timestamp': timestamp,
            }
        
        # 웹소켓으로도 브로드캐스트
        data_to_send = {
            'prices': prices,
            'oracle_result': oracle_result,
            'timestamp': timestamp,
            'price_history': {
                'timestamps': price_history['timestamps'].copy(),
                'median_prices': price_history['median_prices'].copy(),
                'upbit_eth_krw': price_history['upbit_eth_krw'].copy(),
                'upbit_usdt_krw': price_history['upbit_usdt_krw'].copy(),
            }
        }
        socketio.emit('price_update', data_to_send)
        
        return jsonify({'success': True, 'data': latest_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    # 백그라운드 스레드 시작
    update_thread = threading.Thread(target=update_prices, daemon=True)
    update_thread.start()
    
    print("가격 오라클 대시보드 시작...")
    print("http://localhost:5100 에서 접속하세요.")
    print("웹소켓을 사용하여 실시간 데이터를 전송합니다.")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5100, debug=True, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        running = False
        print("서버 종료 중...")

