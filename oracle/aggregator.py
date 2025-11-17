from typing import Dict, List, Optional, Tuple
from .calculator import Calculator
import statistics


class Aggregator:
    """Aggregate prices from multiple exchanges with weights"""
    
    def __init__(self):
        self.calculator = Calculator()
    
    def calculate_weights(
        self,
        exchange_data: Dict[str, Dict],
        user_weights: Dict[str, float],
        spread_weights: Dict[str, float] = None,
        volume_weights: Dict[str, float] = None,
        depth_weights: Dict[str, float] = None
    ) -> Dict[str, float]:
        """
        Calculate final weights for each exchange
        
        Args:
            exchange_data: Dict of {exchange: {price, volume, spread, depth}}
            user_weights: User-defined weight multipliers for each exchange
            spread_weights: User-defined weight multipliers for spread calculation
            volume_weights: User-defined weight multipliers for volume calculation
            depth_weights: User-defined weight multipliers for depth calculation
        """
        if not exchange_data:
            return {}
        
        # Extract volumes and depths for normalization
        volumes = {}
        depths = {}
        spreads = {}
        
        for exchange, data in exchange_data.items():
            volumes[exchange] = data.get('volume')
            depths[exchange] = data.get('depth')
            spreads[exchange] = data.get('spread')
        
        # Normalize volumes and depths
        normalized_volumes = self.calculator.normalize_volumes(volumes)
        normalized_depths = self.calculator.normalize_depths(depths)
        
        # Apply user-defined multipliers
        if volume_weights:
            for exchange in normalized_volumes:
                if exchange in volume_weights:
                    normalized_volumes[exchange] *= volume_weights[exchange]
        
        if depth_weights:
            for exchange in normalized_depths:
                if exchange in depth_weights:
                    normalized_depths[exchange] *= depth_weights[exchange]
        
        # Calculate base weights
        final_weights = {}
        for exchange, data in exchange_data.items():
            spread = spreads.get(exchange)
            norm_vol = normalized_volumes.get(exchange, 0.0)
            norm_depth = normalized_depths.get(exchange, 0.0)
            
            # Apply spread weight multiplier if provided
            spread_weight = self.calculator.calculate_spread_weight(spread)
            if spread_weights and exchange in spread_weights:
                spread_weight *= spread_weights[exchange]
            
            # Calculate base weight
            # 만약 모든 값이 0이면 기본 가중치 1.0 사용
            if spread_weight == 0 and norm_vol == 0 and norm_depth == 0:
                base_weight = 1.0
            else:
                # 최소한 하나의 값이라도 있으면 계산
                if norm_vol == 0:
                    norm_vol = 1.0  # 기본값
                if norm_depth == 0:
                    norm_depth = 1.0  # 기본값
                if spread_weight == 0:
                    spread_weight = 1.0  # 기본값
                base_weight = spread_weight * norm_vol * norm_depth
            
            # Apply user-defined exchange weight multiplier
            user_weight = user_weights.get(exchange, 1.0)
            final_weights[exchange] = base_weight * user_weight
        
        return final_weights
    
    def aggregate_average(
        self,
        prices: Dict[str, float],
        weights: Dict[str, float]
    ) -> Optional[float]:
        """Calculate weighted average price"""
        if not prices or not weights:
            return None
        
        total_weighted_price = 0.0
        total_weight = 0.0
        
        for exchange, price in prices.items():
            if price is not None and price > 0:
                weight = weights.get(exchange, 0.0)
                if weight > 0:
                    total_weighted_price += price * weight
                    total_weight += weight
        
        if total_weight == 0:
            return None
        
        return total_weighted_price / total_weight
    
    def aggregate_median(
        self,
        prices: Dict[str, float],
        weights: Dict[str, float]
    ) -> Optional[float]:
        """Calculate weighted median price"""
        if not prices or not weights:
            return None
        
        # Collect prices with their weights
        weighted_prices = []
        for exchange, price in prices.items():
            if price is not None and price > 0:
                weight = weights.get(exchange, 0.0)
                if weight > 0:
                    # Add price multiple times based on weight (simplified approach)
                    # For more accurate weighted median, we'd need to use percentile
                    weighted_prices.append(price)
        
        if not weighted_prices:
            return None
        
        # Simple median (can be improved with proper weighted median)
        return statistics.median(weighted_prices)
    
    def aggregate(
        self,
        exchange_data: Dict[str, Dict],
        user_weights: Dict[str, float],
        method: str = 'average',
        spread_weights: Dict[str, float] = None,
        volume_weights: Dict[str, float] = None,
        depth_weights: Dict[str, float] = None
    ) -> Tuple[Optional[float], Dict[str, float]]:
        """
        Aggregate prices from multiple exchanges
        
        Returns:
            Tuple of (aggregated_price, weights_dict)
        """
        # Extract prices
        prices = {ex: data.get('price') for ex, data in exchange_data.items()}
        
        # Calculate weights
        weights = self.calculate_weights(
            exchange_data,
            user_weights,
            spread_weights,
            volume_weights,
            depth_weights
        )
        
        # Aggregate based on method
        if method == 'median':
            aggregated_price = self.aggregate_median(prices, weights)
        else:  # default to average
            aggregated_price = self.aggregate_average(prices, weights)
        
        return aggregated_price, weights

