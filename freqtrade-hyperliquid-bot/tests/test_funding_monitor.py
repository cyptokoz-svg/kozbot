"""
测试 Funding Monitor 模块
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from freqtrade_hl.funding_monitor import FundingMonitor, FundingSignalGenerator
from freqtrade_hl.exchange import HyperliquidExchange, FundingRate


class TestFundingMonitor:
    """测试 FundingMonitor 类"""
    
    @pytest.fixture
    def mock_exchange(self):
        """创建 mock exchange"""
        exchange = MagicMock(spec=HyperliquidExchange)
        exchange.get_all_funding_rates = AsyncMock()
        return exchange
    
    @pytest.fixture
    def monitor(self, mock_exchange):
        """创建测试用的 monitor 实例"""
        return FundingMonitor(
            exchange=mock_exchange,
            check_interval=1,
            extreme_threshold=0.001
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, monitor, mock_exchange):
        """测试初始化"""
        assert monitor.exchange == mock_exchange
        assert monitor.check_interval == 1
        assert monitor.extreme_threshold == 0.001
        assert monitor._running == False
    
    @pytest.mark.asyncio
    async def test_add_remove_callback(self, monitor):
        """测试添加和移除回调"""
        callback = MagicMock()
        
        monitor.add_callback(callback)
        assert callback in monitor._callbacks
        
        monitor.remove_callback(callback)
        assert callback not in monitor._callbacks
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitor, mock_exchange):
        """测试启动和停止监控"""
        # Mock 返回空数据
        mock_exchange.get_all_funding_rates.return_value = []
        
        # 启动监控
        await monitor.start_monitoring()
        assert monitor._running == True
        assert monitor._task is not None
        
        # 等待一小段时间
        await asyncio.sleep(0.1)
        
        # 停止监控
        await monitor.stop_monitoring()
        assert monitor._running == False
    
    @pytest.mark.asyncio
    async def test_get_current_stats(self, monitor):
        """测试获取统计数据"""
        # 添加一些历史数据
        monitor._history = [
            {"timestamp": datetime.now().isoformat(), "symbol": "BTC", "funding_rate": 0.0001},
            {"timestamp": datetime.now().isoformat(), "symbol": "ETH", "funding_rate": 0.002},
            {"timestamp": datetime.now().isoformat(), "symbol": "SOL", "funding_rate": -0.0005}
        ]
        
        stats = monitor.get_current_stats()
        
        assert stats["status"] == "stopped"
        assert stats["total_pairs"] == 3
        assert stats["extreme_count"] == 1  # ETH with 0.002
        assert stats["history_size"] == 3
    
    @pytest.mark.asyncio
    async def test_get_extreme_rates(self, monitor):
        """测试获取极端 rates"""
        monitor._history = [
            {"timestamp": datetime.now().isoformat(), "symbol": "BTC", "funding_rate": 0.0001},
            {"timestamp": datetime.now().isoformat(), "symbol": "ETH", "funding_rate": 0.003},
            {"timestamp": datetime.now().isoformat(), "symbol": "SOL", "funding_rate": -0.002}
        ]
        
        extreme = monitor.get_extreme_rates(top_n=2)
        
        assert len(extreme) == 2
        # ETH 应该是第一个 (0.003)
        assert extreme[0]["symbol"] == "ETH"
        assert extreme[1]["symbol"] == "SOL"
    
    @pytest.mark.asyncio
    async def test_funding_history_filtering(self, monitor):
        """测试历史数据过滤"""
        now = datetime.now()
        
        monitor._history = [
            {"timestamp": now.isoformat(), "symbol": "BTC", "funding_rate": 0.0001},
            {"timestamp": now.isoformat(), "symbol": "ETH", "funding_rate": 0.0002},
        ]
        
        btc_history = monitor.get_funding_history("BTC", hours=24)
        
        assert len(btc_history) == 1
        assert btc_history[0]["symbol"] == "BTC"


class TestFundingSignalGenerator:
    """测试 FundingSignalGenerator 类"""
    
    @pytest.fixture
    def generator(self):
        """创建测试用的 generator 实例"""
        mock_monitor = MagicMock(spec=FundingMonitor)
        return FundingSignalGenerator(mock_monitor)
    
    def test_generate_positive_funding_signal(self, generator):
        """测试正 funding rate 信号生成"""
        rate = FundingRate(
            symbol="BTC",
            funding_rate=0.002,
            next_funding_time=1234567890,
            timestamp=1234567800
        )
        
        signal = generator.generate_signal(rate)
        
        assert signal is not None
        assert signal["type"] == "funding_arbitrage"
        assert signal["symbol"] == "BTC"
        assert signal["direction"] == "short_hl_long_pm"
        assert signal["funding_rate"] == 0.002
        assert "short HL" in signal["reason"]
    
    def test_generate_negative_funding_signal(self, generator):
        """测试负 funding rate 信号生成"""
        rate = FundingRate(
            symbol="ETH",
            funding_rate=-0.0015,
            next_funding_time=1234567890,
            timestamp=1234567800
        )
        
        signal = generator.generate_signal(rate)
        
        assert signal is not None
        assert signal["type"] == "funding_arbitrage"
        assert signal["symbol"] == "ETH"
        assert signal["direction"] == "long_hl_short_pm"
        assert signal["funding_rate"] == -0.0015
        assert "long HL" in signal["reason"]
    
    def test_no_signal_for_normal_funding(self, generator):
        """测试正常 funding rate 不产生信号"""
        rate = FundingRate(
            symbol="SOL",
            funding_rate=0.0001,
            next_funding_time=1234567890,
            timestamp=1234567800
        )
        
        signal = generator.generate_signal(rate)
        
        assert signal is None
    
    def test_get_recent_signals(self, generator):
        """测试获取最近信号"""
        # 生成一些信号
        for i in range(15):
            rate = FundingRate(
                symbol=f"COIN{i}",
                funding_rate=0.002 if i % 2 == 0 else -0.002,
                next_funding_time=1234567890,
                timestamp=1234567800
            )
            generator.generate_signal(rate)
        
        recent = generator.get_recent_signals(n=10)
        
        assert len(recent) == 10
    
    def test_clear_signals(self, generator):
        """测试清除信号"""
        rate = FundingRate(
            symbol="BTC",
            funding_rate=0.002,
            next_funding_time=1234567890,
            timestamp=1234567800
        )
        generator.generate_signal(rate)
        
        assert len(generator.signals) > 0
        
        generator.clear_signals()
        
        assert len(generator.signals) == 0
