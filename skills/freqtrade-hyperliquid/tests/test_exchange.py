"""
测试 Hyperliquid Exchange Adapter
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from freqtrade_hl.exchange import (
    HyperliquidExchange, 
    FundingRate, 
    Position,
    create_hyperliquid_client
)


class TestHyperliquidExchange:
    """测试 HyperliquidExchange 类"""
    
    @pytest.fixture
    def exchange(self):
        """创建测试用的 exchange 实例"""
        return HyperliquidExchange(
            api_key="test_key",
            api_secret="test_secret",
            wallet_address="0x1234567890abcdef",
            testnet=True
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, exchange):
        """测试初始化"""
        assert exchange.api_key == "test_key"
        assert exchange.wallet_address == "0x1234567890abcdef"
        assert exchange.testnet == True
        assert "testnet" in exchange.rest_url
    
    @pytest.mark.asyncio
    async def test_get_all_funding_rates(self, exchange):
        """测试获取所有 funding rates"""
        # Mock 响应数据
        mock_response = [
            {"coin": "BTC", "fundingRate": "0.0001", "nextFundingTime": 1234567890},
            {"coin": "ETH", "fundingRate": "-0.0002", "nextFundingTime": 1234567890}
        ]
        
        with patch.object(exchange, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            rates = await exchange.get_all_funding_rates()
            
            assert len(rates) == 2
            assert rates[0].symbol == "BTC"
            assert rates[0].funding_rate == 0.0001
            assert rates[1].symbol == "ETH"
            assert rates[1].funding_rate == -0.0002
    
    @pytest.mark.asyncio
    async def test_get_funding_rate(self, exchange):
        """测试获取单个 funding rate"""
        mock_response = [
            {"coin": "BTC", "fundingRate": "0.0001", "nextFundingTime": 1234567890}
        ]
        
        with patch.object(exchange, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            rate = await exchange.get_funding_rate("BTC")
            
            assert rate is not None
            assert rate.symbol == "BTC"
            assert rate.funding_rate == 0.0001
    
    @pytest.mark.asyncio
    async def test_get_extreme_funding_rates(self, exchange):
        """测试获取极端 funding rates"""
        mock_response = [
            {"coin": "BTC", "fundingRate": "0.002", "nextFundingTime": 1234567890},
            {"coin": "ETH", "fundingRate": "0.0001", "nextFundingTime": 1234567890},
            {"coin": "SOL", "fundingRate": "-0.003", "nextFundingTime": 1234567890}
        ]
        
        with patch.object(exchange, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            extreme_rates = await exchange.get_extreme_funding_rates(threshold=0.001)
            
            assert len(extreme_rates) == 2
            # 应该按绝对值排序，SOL 最大
            assert extreme_rates[0].symbol == "SOL"
            assert extreme_rates[1].symbol == "BTC"
    
    @pytest.mark.asyncio
    async def test_get_market_price(self, exchange):
        """测试获取市场价格"""
        mock_mids = {"BTC": "45000.5", "ETH": "3000.2"}
        
        with patch.object(exchange, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_mids
            
            price = await exchange.get_market_price("BTC")
            
            assert price == 45000.5
    
    def test_calculate_funding_pnl(self, exchange):
        """测试计算 funding PnL"""
        # $10k 仓位，0.01% funding rate
        pnl = exchange.calculate_funding_pnl(
            position_size=0.222,  # ~$10k at $45k BTC
            funding_rate=0.0001,
            mark_price=45000
        )
        
        expected_pnl = 0.222 * 45000 * 0.0001  # ~$1
        assert abs(pnl - expected_pnl) < 0.01
    
    def test_create_hyperliquid_client(self):
        """测试创建客户端工厂函数"""
        config = {
            "exchange": {
                "key": "api_key",
                "secret": "api_secret",
                "wallet": "0xwallet",
                "testnet": False
            }
        }
        
        client = create_hyperliquid_client(config)
        
        assert isinstance(client, HyperliquidExchange)
        assert client.api_key == "api_key"
        assert client.wallet_address == "0xwallet"
        assert client.testnet == False


class TestFundingRate:
    """测试 FundingRate 数据类"""
    
    def test_creation(self):
        """测试创建 FundingRate"""
        rate = FundingRate(
            symbol="BTC",
            funding_rate=0.0001,
            next_funding_time=1234567890,
            timestamp=1234567800
        )
        
        assert rate.symbol == "BTC"
        assert rate.funding_rate == 0.0001
        assert rate.next_funding_time == 1234567890


class TestPosition:
    """测试 Position 数据类"""
    
    def test_creation(self):
        """测试创建 Position"""
        pos = Position(
            symbol="BTC",
            side="long",
            size=1.5,
            entry_price=45000,
            unrealized_pnl=500,
            liquidation_price=40000
        )
        
        assert pos.symbol == "BTC"
        assert pos.side == "long"
        assert pos.size == 1.5
        assert pos.entry_price == 45000
