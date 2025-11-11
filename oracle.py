"""
오라클 핵심 로직
여러 거래소의 가격을 수집하고 중앙값을 계산하며, 김치 프리미엄을 고려한 가격 변환을 수행합니다.
"""
import statistics
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import deque
import time


class Oracle:
    """가격 오라클 클래스"""
    
    def __init__(self, twap_window_seconds: int = 300, volatility_threshold: float = 0.05):
        """
        Args:
            twap_window_seconds: TWAP 계산을 위한 시간 윈도우 (초)
            volatility_threshold: USDT/KRW 변동성 임계값 (5% 기본값)
        """
        self.twap_window_seconds = twap_window_seconds
        self.volatility_threshold = volatility_threshold
        
        # USDT/KRW 가격 히스토리 (TWAP 계산용)
        self.usdt_krw_history = deque()  # [(timestamp, price), ...]
        
        # 조작된 USDT/KRW 가격 (테스트용)
        self.manual_usdt_krw_override: Optional[float] = None
        
        # 조작된 ETH/KRW 가격 (테스트용)
        self.manual_eth_krw_override: Optional[float] = None
        
    def add_usdt_krw_price(self, price: float, timestamp: Optional[float] = None):
        """USDT/KRW 가격 히스토리 추가"""
        if timestamp is None:
            timestamp = time.time()
        
        self.usdt_krw_history.append((timestamp, price))
        
        # 오래된 데이터 제거
        cutoff_time = timestamp - self.twap_window_seconds
        while self.usdt_krw_history and self.usdt_krw_history[0][0] < cutoff_time:
            self.usdt_krw_history.popleft()
    
    def calculate_twap(self) -> Optional[float]:
        """USDT/KRW의 TWAP (Time-Weighted Average Price) 계산"""
        if not self.usdt_krw_history:
            return None
        
        if len(self.usdt_krw_history) == 1:
            return self.usdt_krw_history[0][1]
        
        # 시간 가중 평균 계산
        total_weight = 0
        weighted_sum = 0
        
        for i, (timestamp, price) in enumerate(self.usdt_krw_history):
            if i == 0:
                # 첫 번째 데이터는 다음 데이터까지의 시간 간격을 가중치로 사용
                if len(self.usdt_krw_history) > 1:
                    weight = self.usdt_krw_history[1][0] - timestamp
                else:
                    weight = 1
            elif i == len(self.usdt_krw_history) - 1:
                # 마지막 데이터는 현재 시간까지의 간격
                weight = time.time() - timestamp
            else:
                # 중간 데이터는 양쪽 간격의 평균
                prev_time = self.usdt_krw_history[i-1][0]
                next_time = self.usdt_krw_history[i+1][0]
                weight = (timestamp - prev_time + next_time - timestamp) / 2
            
            weighted_sum += price * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else None
    
    def check_usdt_krw_volatility(self, current_price: float) -> bool:
        """USDT/KRW 가격 변동성 체크"""
        twap = self.calculate_twap()
        if twap is None:
            return False
        
        # 현재 가격과 TWAP의 차이 비율
        price_change = abs(current_price - twap) / twap
        
        return price_change > self.volatility_threshold
    
    def convert_overseas_price_to_krw(
        self, 
        eth_usdt_price: float, 
        usdt_krw_price: float
    ) -> float:
        """해외 거래소 ETH/USDT 가격을 ETH/KRW로 변환"""
        return eth_usdt_price * usdt_krw_price
    
    def convert_domestic_price_to_usdt(
        self,
        eth_krw_price: float,
        eth_usdt_price: float
    ) -> float:
        """국내 거래소 ETH/KRW 가격으로부터 USDT/KRW 역산"""
        return eth_krw_price / eth_usdt_price
    
    def calculate_median_eth_krw_price(
        self,
        upbit_eth_krw: Optional[float],
        upbit_usdt_krw: Optional[float],
        overseas_eth_usdt: Dict[str, Optional[float]],
        use_manual_usdt_krw: bool = False,
        use_manual_eth_krw: bool = False
    ) -> Dict:
        """
        ETH/KRW 중앙값 가격 계산
        
        Returns:
            {
                'median_price': float,
                'prices_used': List[float],
                'calculation_method': str,
                'usdt_krw_used': float,
                'is_volatile': bool,
                'twap': float,
            }
        """
        prices = []
        
        # 조작된 USDT/KRW 사용 여부
        if use_manual_usdt_krw and self.manual_usdt_krw_override is not None:
            usdt_krw_price = self.manual_usdt_krw_override
        else:
            usdt_krw_price = upbit_usdt_krw
        
        # USDT/KRW 가격 히스토리 업데이트 (수동 ETH/KRW 사용 여부와 관계없이)
        if usdt_krw_price is not None:
            self.add_usdt_krw_price(usdt_krw_price)
        
        # TWAP 계산 (수동 ETH/KRW 사용 여부와 관계없이)
        twap = self.calculate_twap()
        
        # USDT/KRW 변동성 체크
        is_volatile = False
        if usdt_krw_price is not None:
            is_volatile = self.check_usdt_krw_volatility(usdt_krw_price)
        
        # 국내 거래소 가격 추가 (수동 ETH/KRW가 설정되어 있으면 수동 가격 사용, 아니면 실제 가격 사용)
        if use_manual_eth_krw and self.manual_eth_krw_override is not None:
            # 수동 ETH/KRW 가격 사용
            prices.append(('upbit (manual)', self.manual_eth_krw_override))
        elif upbit_eth_krw is not None:
            # 실제 Upbit ETH/KRW 가격 사용
            prices.append(('upbit', upbit_eth_krw))
        
        # 역산된 USDT/KRW 가격 (역산 모드에서 사용)
        inverse_usdt_krw_avg = None
        
        # 해외 거래소 가격 변환
        if not is_volatile:
            # 정상적인 경우: 해외 ETH/USDT * USDT/KRW
            if usdt_krw_price is not None:
                for exchange_name, eth_usdt_price in overseas_eth_usdt.items():
                    if eth_usdt_price is not None:
                        eth_krw_price = self.convert_overseas_price_to_krw(
                            eth_usdt_price, usdt_krw_price
                        )
                        prices.append((f'{exchange_name} (Converted)', eth_krw_price))
        else:
            # 변동성이 큰 경우: 역산 모드
            # 1. 각 해외 거래소의 ETH/USDT로부터 역산된 USDT/KRW 계산
            # 2. 역산된 USDT/KRW들의 평균 계산
            # 3. 평균 USDT/KRW를 사용하여 해외 거래소 가격 변환
            # 역산에 사용할 Upbit ETH/KRW 가격 결정 (수동 가격이 있으면 수동 가격 사용)
            upbit_eth_krw_for_inverse = None
            if use_manual_eth_krw and self.manual_eth_krw_override is not None:
                upbit_eth_krw_for_inverse = self.manual_eth_krw_override
            else:
                upbit_eth_krw_for_inverse = upbit_eth_krw
            
            if upbit_eth_krw_for_inverse is not None:
                inverse_usdt_krw_list = []
                
                # 각 해외 거래소별로 역산된 USDT/KRW 계산
                for exchange_name, eth_usdt_price in overseas_eth_usdt.items():
                    if eth_usdt_price is not None:
                        inverse_usdt_krw = self.convert_domestic_price_to_usdt(
                            upbit_eth_krw_for_inverse, eth_usdt_price
                        )
                        inverse_usdt_krw_list.append(inverse_usdt_krw)
                
                # 역산된 USDT/KRW의 평균 계산
                if inverse_usdt_krw_list:
                    inverse_usdt_krw_avg = statistics.mean(inverse_usdt_krw_list)
                    
                    # 평균 역산 USDT/KRW를 사용하여 해외 거래소 가격 변환
                    for exchange_name, eth_usdt_price in overseas_eth_usdt.items():
                        if eth_usdt_price is not None:
                            eth_krw_price = self.convert_overseas_price_to_krw(
                                eth_usdt_price, inverse_usdt_krw_avg
                            )
                            prices.append((f'{exchange_name} (inverse)', eth_krw_price))
        
        # 중앙값 계산
        if not prices:
            return {
                'median_price': None,
                'prices_used': [],
                'calculation_method': 'no_data',
                'usdt_krw_used': usdt_krw_price,
                'usdt_krw_original': usdt_krw_price,
                'inverse_usdt_krw': None,
                'is_volatile': is_volatile,
                'twap': twap,
                'price_details': [],
            }
        
        price_values = [p[1] for p in prices]
        median_price = statistics.median(price_values)
        
        return {
            'median_price': median_price,
            'prices_used': price_values,
            'calculation_method': 'inverse' if is_volatile else 'normal',
            'usdt_krw_used': inverse_usdt_krw_avg if is_volatile and inverse_usdt_krw_avg is not None else usdt_krw_price,
            'usdt_krw_original': usdt_krw_price,  # 원본 USDT/KRW 가격 (변동성 체크용)
            'inverse_usdt_krw': inverse_usdt_krw_avg,  # 역산된 USDT/KRW (역산 모드일 때만)
            'is_volatile': is_volatile,
            'twap': twap,
            'price_details': prices,
        }
    
    def set_manual_usdt_krw(self, price: Optional[float]):
        """테스트용 USDT/KRW 가격 수동 설정"""
        self.manual_usdt_krw_override = price
    
    def get_manual_usdt_krw(self) -> Optional[float]:
        """테스트용 USDT/KRW 가격 가져오기"""
        return self.manual_usdt_krw_override
    
    def set_manual_eth_krw(self, price: Optional[float]):
        """테스트용 ETH/KRW 가격 수동 설정"""
        self.manual_eth_krw_override = price
    
    def get_manual_eth_krw(self) -> Optional[float]:
        """테스트용 ETH/KRW 가격 가져오기"""
        return self.manual_eth_krw_override


if __name__ == '__main__':
    # 테스트
    oracle = Oracle()
    
    # 테스트 데이터
    result = oracle.calculate_median_eth_krw_price(
        upbit_eth_krw=5000000,
        upbit_usdt_krw=1300,
        overseas_eth_usdt={
            'binance': 3000,
            'okx': 3001,
            'coinbase': 2999,
        }
    )
    
    print(result)

