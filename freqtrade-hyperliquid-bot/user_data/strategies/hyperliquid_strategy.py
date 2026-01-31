"""
Hyperliquid Funding Rate 策略
基于 Funding Rate 的套利和对冲策略
"""

import logging
from typing import Dict, Optional

import pandas as pd
from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class HyperliquidStrategy(IStrategy):
    """
    Hyperliquid Funding Rate 策略
    
    策略逻辑:
    1. 监控 Hyperliquid funding rates
    2. 当 funding rate 极端时 (>0.1% 或 <-0.1%)，进行对冲交易
    3. 正 funding: 做空 Hyperliquid，赚取 funding 费用
    4. 负 funding: 做多 Hyperliquid，赚取 funding 费用
    5. 结合 Polymarket 信号进行复合策略
    
    时间周期: 15m (适配 Polymarket 15m 周期)
    """
    
    # 策略配置
    timeframe = '15m'
    stoploss = -0.35  # 35% 止损
    minimal_roi = {"0": 0.15}  # 15% 止盈
    
    # Funding 阈值
    funding_threshold = 0.001  # 0.1%
    
    # 仓位配置
    position_size = 0.1  # 10% 资金
    max_positions = 3    # 最大同时持仓
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.hl_exchange = None
        
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        添加技术指标
        
        这里可以接入 Hyperliquid funding rate 数据
        """
        # 添加 funding rate 列 (需要从外部数据填充)
        if 'funding_rate' not in dataframe.columns:
            dataframe['funding_rate'] = 0.0
            
        # 标记极端 funding
        dataframe['extreme_funding'] = (
            (dataframe['funding_rate'] > self.funding_threshold) |
            (dataframe['funding_rate'] < -self.funding_threshold)
        )
        
        # 简单的移动平均线
        dataframe['sma_20'] = dataframe['close'].rolling(window=20).mean()
        dataframe['sma_50'] = dataframe['close'].rolling(window=50).mean()
        
        return dataframe
    
    def populate_buy_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        生成做多信号
        
        条件:
        1. Funding rate < -0.1% (负 funding，做多赚取 funding)
        2. 价格高于 SMA20 (趋势向上)
        """
        conditions = []
        
        # 负 funding 极端值
        conditions.append(dataframe['funding_rate'] < -self.funding_threshold)
        
        # 趋势向上
        conditions.append(dataframe['close'] > dataframe['sma_20'])
        
        if conditions:
            dataframe.loc[
                pd.concat(conditions, axis=1).all(axis=1),
                'buy'
            ] = 1
        
        return dataframe
    
    def populate_sell_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        生成做空/卖出信号
        
        条件:
        1. Funding rate > 0.1% (正 funding，做空赚取 funding)
        2. 价格低于 SMA20 (趋势向下)
        """
        conditions = []
        
        # 正 funding 极端值
        conditions.append(dataframe['funding_rate'] > self.funding_threshold)
        
        # 趋势向下
        conditions.append(dataframe['close'] < dataframe['sma_20'])
        
        if conditions:
            dataframe.loc[
                pd.concat(conditions, axis=1).all(axis=1),
                'sell'
            ] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time, current_rate,
                       current_profit: float, **kwargs) -> Optional[float]:
        """
        自定义止损逻辑
        
        可以基于 funding rate 变化动态调整止损
        """
        # 如果 funding rate 回归正常，收紧止损
        # 这里需要接入实时 funding 数据
        
        return self.stoploss
    
    def custom_exit(self, pair: str, trade: Trade, current_time, current_rate,
                   current_profit: float, **kwargs) -> Optional[str]:
        """
        自定义退出逻辑
        
        当 funding rate 回归正常范围时退出
        """
        # 如果 profit > 5% 且 funding 回归正常，退出
        if current_profit > 0.05:
            return "funding_normalized"
        
        return None


class HyperliquidPolymarketComboStrategy(HyperliquidStrategy):
    """
    Hyperliquid + Polymarket 复合策略
    
    结合两个市场的信号:
    - Polymarket 提供方向预测 (UP/DOWN)
    - Hyperliquid 提供 funding 收益
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.polymarket_signals = {}
    
    def update_polymarket_signal(self, symbol: str, signal: dict):
        """
        更新 Polymarket 信号
        
        Args:
            symbol: 交易对
            signal: Polymarket 信号 {'direction': 'UP'/'DOWN', 'probability': float}
        """
        self.polymarket_signals[symbol] = signal
    
    def populate_buy_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        做多信号 (结合 Polymarket)
        
        条件:
        1. Polymarket 预测 UP
        2. Hyperliquid funding 为负 (做多有收益)
        """
        conditions = []
        
        # Polymarket UP 信号
        pair = metadata['pair']
        pm_signal = self.polymarket_signals.get(pair, {})
        conditions.append(pm_signal.get('direction') == 'UP')
        
        # 负 funding
        conditions.append(dataframe['funding_rate'] < 0)
        
        if conditions:
            dataframe.loc[
                pd.concat(conditions, axis=1).all(axis=1),
                'buy'
            ] = 1
        
        return dataframe
    
    def populate_sell_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        做空信号 (结合 Polymarket)
        
        条件:
        1. Polymarket 预测 DOWN
        2. Hyperliquid funding 为正 (做空有收益)
        """
        conditions = []
        
        # Polymarket DOWN 信号
        pair = metadata['pair']
        pm_signal = self.polymarket_signals.get(pair, {})
        conditions.append(pm_signal.get('direction') == 'DOWN')
        
        # 正 funding
        conditions.append(dataframe['funding_rate'] > 0)
        
        if conditions:
            dataframe.loc[
                pd.concat(conditions, axis=1).all(axis=1),
                'sell'
            ] = 1
        
        return dataframe
