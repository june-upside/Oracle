from typing import Dict, List, Optional


class Calculator:
    """Calculate spread, depth, and normalize volumes for weight calculation"""
    
    @staticmethod
    def calculate_spread(bid_price: float, ask_price: float) -> Optional[float]:
        """Calculate spread percentage: (ask - bid) / mid_price * 100"""
        if not bid_price or not ask_price or bid_price <= 0 or ask_price <= 0:
            return None
        
        mid_price = (bid_price + ask_price) / 2
        if mid_price == 0:
            return None
        
        spread = ((ask_price - bid_price) / mid_price) * 100
        return spread
    
    @staticmethod
    def normalize_volumes(volumes: Dict[str, float]) -> Dict[str, float]:
        """Normalize volumes to 0-1 range"""
        if not volumes:
            return {}
        
        values = [v for v in volumes.values() if v is not None and v > 0]
        if not values:
            return {k: 0.0 for k in volumes.keys()}
        
        min_vol = min(values)
        max_vol = max(values)
        
        if max_vol == min_vol:
            return {k: 1.0 for k in volumes.keys()}
        
        normalized = {}
        for exchange, volume in volumes.items():
            if volume is None or volume <= 0:
                normalized[exchange] = 0.0
            else:
                normalized[exchange] = (volume - min_vol) / (max_vol - min_vol)
        
        return normalized
    
    @staticmethod
    def normalize_depths(depths: Dict[str, float]) -> Dict[str, float]:
        """Normalize depths to 0-1 range"""
        if not depths:
            return {}
        
        values = [v for v in depths.values() if v is not None and v > 0]
        if not values:
            return {k: 0.0 for k in depths.keys()}
        
        min_depth = min(values)
        max_depth = max(values)
        
        if max_depth == min_depth:
            return {k: 1.0 for k in depths.keys()}
        
        normalized = {}
        for exchange, depth in depths.items():
            if depth is None or depth <= 0:
                normalized[exchange] = 0.0
            else:
                normalized[exchange] = (depth - min_depth) / (max_depth - min_depth)
        
        return normalized
    
    @staticmethod
    def calculate_spread_weight(spread: Optional[float]) -> float:
        """Calculate weight based on spread: lower spread = higher weight"""
        if spread is None or spread < 0:
            return 0.0
        
        # weight = 1 / (1 + spread)
        # This gives higher weight for lower spread
        weight = 1.0 / (1.0 + spread)
        return weight
    
    @staticmethod
    def calculate_base_weight(
        spread: Optional[float],
        normalized_volume: float,
        normalized_depth: float
    ) -> float:
        """Calculate base weight from spread, volume, and depth"""
        spread_weight = Calculator.calculate_spread_weight(spread)
        
        # Base weight = spread_weight * volume * depth
        base_weight = spread_weight * normalized_volume * normalized_depth
        
        return base_weight

