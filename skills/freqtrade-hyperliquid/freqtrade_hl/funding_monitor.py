"""
Funding Rate 监控模块
实时监控 Hyperliquid 资金费率，检测极端值和套利机会
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .exchange import HyperliquidExchange, FundingRate

logger = logging.getLogger(__name__)


class FundingMonitor:
    """
    Funding Rate 监控器
    
    功能:
    - 实时监控所有交易对的 funding rate
    - 检测极端 funding rate
    - 触发告警和交易信号
    - 记录历史数据
    """
    
    def __init__(self, exchange: HyperliquidExchange, 
                 check_interval: int = 60,
                 extreme_threshold: float = 0.001):
        """
        初始化监控器
        
        Args:
            exchange: Hyperliquid 交易所客户端
            check_interval: 检查间隔（秒）
            extreme_threshold: 极端 funding rate 阈值
        """
        self.exchange = exchange
        self.check_interval = check_interval
        self.extreme_threshold = extreme_threshold
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        self._history: List[Dict] = []
        self._max_history = 10000
        
    def add_callback(self, callback: Callable):
        """
        添加回调函数，当检测到极端 funding 时触发
        
        Args:
            callback: 回调函数，接收 (funding_rate, is_extreme) 参数
        """
        self._callbacks.append(callback)
        
    def remove_callback(self, callback: Callable):
        """移除回调函数"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    async def start_monitoring(self):
        """启动监控循环"""
        if self._running:
            logger.warning("Funding monitor is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Funding monitor started (interval: {self.check_interval}s)")
        
    async def stop_monitoring(self):
        """停止监控循环"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Funding monitor stopped")
        
    async def _monitor_loop(self):
        """监控主循环"""
        while self._running:
            try:
                await self._check_funding_rates()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_funding_rates(self):
        """检查资金费率"""
        try:
            # 获取所有 funding rates
            rates = await self.exchange.get_all_funding_rates()
            
            # 检查极端值
            extreme_rates = [
                rate for rate in rates 
                if abs(rate.funding_rate) >= self.extreme_threshold
            ]
            
            # 记录历史
            timestamp = datetime.now().isoformat()
            for rate in rates:
                self._history.append({
                    "timestamp": timestamp,
                    "symbol": rate.symbol,
                    "funding_rate": rate.funding_rate,
                    "next_funding_time": rate.next_funding_time
                })
            
            # 限制历史记录大小
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            
            # 触发回调
            if extreme_rates:
                logger.info(f"Detected {len(extreme_rates)} extreme funding rates")
                for callback in self._callbacks:
                    try:
                        for rate in extreme_rates:
                            callback(rate, True)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to check funding rates: {e}")
    
    def get_current_stats(self) -> Dict:
        """
        获取当前统计信息
        
        Returns:
            Dict: 统计数据
        """
        if not self._history:
            return {"status": "no_data"}
        
        # 获取最新的 funding rates
        latest = {}
        for record in reversed(self._history):
            symbol = record["symbol"]
            if symbol not in latest:
                latest[symbol] = record
        
        # 计算统计
        rates = [r["funding_rate"] for r in latest.values()]
        extreme_count = sum(1 for r in rates if abs(r) >= self.extreme_threshold)
        
        return {
            "status": "running" if self._running else "stopped",
            "total_pairs": len(latest),
            "extreme_count": extreme_count,
            "avg_funding": sum(rates) / len(rates) if rates else 0,
            "max_funding": max(rates) if rates else 0,
            "min_funding": min(rates) if rates else 0,
            "history_size": len(self._history)
        }
    
    def get_extreme_rates(self, top_n: int = 10) -> List[Dict]:
        """
        获取最极端的 funding rates
        
        Args:
            top_n: 返回数量
            
        Returns:
            List[Dict]: 极端 funding rate 列表
        """
        # 获取最新数据
        latest = {}
        for record in reversed(self._history):
            symbol = record["symbol"]
            if symbol not in latest:
                latest[symbol] = record
        
        # 按绝对值排序
        sorted_rates = sorted(
            latest.values(),
            key=lambda x: abs(x["funding_rate"]),
            reverse=True
        )
        
        return sorted_rates[:top_n]
    
    def export_history(self, filename: str):
        """
        导出历史数据到文件
        
        Args:
            filename: 输出文件名
        """
        with open(filename, 'w') as f:
            json.dump(self._history, f, indent=2)
        logger.info(f"Exported {len(self._history)} records to {filename}")
    
    def get_funding_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """
        获取指定交易对的历史 funding rate
        
        Args:
            symbol: 交易对符号
            hours: 时间范围（小时）
            
        Returns:
            List[Dict]: 历史数据
        """
        symbol_upper = symbol.upper()
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        filtered = [
            record for record in self._history
            if record["symbol"].upper() == symbol_upper
        ]
        
        return filtered


class FundingSignalGenerator:
    """
    Funding Rate 交易信号生成器
    
    基于 funding rate 生成交易信号:
    - 极端 funding: 触发对冲信号
    - funding 趋势: 预测未来方向
    """
    
    def __init__(self, monitor: FundingMonitor):
        self.monitor = monitor
        self.signals: List[Dict] = []
        
    def generate_signal(self, rate: FundingRate) -> Optional[Dict]:
        """
        生成交易信号
        
        Args:
            rate: 资金费率数据
            
        Returns:
            Optional[Dict]: 交易信号
        """
        signal = None
        
        # 极端正 funding: 做空 Hyperliquid，做多 Polymarket
        if rate.funding_rate > 0.001:
            signal = {
                "type": "funding_arbitrage",
                "symbol": rate.symbol,
                "direction": "short_hl_long_pm",
                "funding_rate": rate.funding_rate,
                "confidence": min(abs(rate.funding_rate) * 1000, 1.0),
                "expected_funding_8h": rate.funding_rate * 10000,  # $10k 仓位
                "timestamp": datetime.now().isoformat(),
                "reason": f"High positive funding ({rate.funding_rate:.4%}), short HL to earn funding"
            }
        
        # 极端负 funding: 做多 Hyperliquid，做空 Polymarket
        elif rate.funding_rate < -0.001:
            signal = {
                "type": "funding_arbitrage",
                "symbol": rate.symbol,
                "direction": "long_hl_short_pm",
                "funding_rate": rate.funding_rate,
                "confidence": min(abs(rate.funding_rate) * 1000, 1.0),
                "expected_funding_8h": abs(rate.funding_rate) * 10000,
                "timestamp": datetime.now().isoformat(),
                "reason": f"High negative funding ({rate.funding_rate:.4%}), long HL to earn funding"
            }
        
        if signal:
            self.signals.append(signal)
            # 限制信号历史
            if len(self.signals) > 1000:
                self.signals = self.signals[-1000:]
        
        return signal
    
    def get_recent_signals(self, n: int = 10) -> List[Dict]:
        """获取最近的信号"""
        return self.signals[-n:]
    
    def clear_signals(self):
        """清除所有信号"""
        self.signals = []
