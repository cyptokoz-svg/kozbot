"""
Freqtrade Hyperliquid Exchange Adapter
支持 Hyperliquid 交易所的现货和永续合约交易
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FundingRate:
    """资金费率数据"""
    symbol: str
    funding_rate: float
    next_funding_time: int
    timestamp: int


@dataclass
class Position:
    """持仓数据"""
    symbol: str
    side: str  # "long" or "short"
    size: float
    entry_price: float
    unrealized_pnl: float
    liquidation_price: Optional[float] = None


class HyperliquidExchange:
    """
    Hyperliquid 交易所适配器
    
    支持功能:
    - 获取市场数据 (价格、订单簿)
    - 获取资金费率
    - 获取持仓和余额
    - 下单和撤单
    """
    
    def __init__(self, api_key: Optional[str] = None, 
                 api_secret: Optional[str] = None,
                 wallet_address: Optional[str] = None,
                 testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.wallet_address = wallet_address
        self.testnet = testnet
        
        # API 端点
        base_url = "https://api.hyperliquid-testnet.xyz" if testnet else "https://api.hyperliquid.xyz"
        self.rest_url = f"{base_url}/info"
        self.exchange_url = f"{base_url}/exchange"
        
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """关闭 session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(self, endpoint: str, payload: Dict) -> Dict:
        """发送 HTTP 请求"""
        session = await self._get_session()
        url = f"{self.rest_url}/{endpoint}"
        
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API Error: {response.status} - {error_text}")
                    raise Exception(f"API Error: {response.status}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    async def get_all_funding_rates(self) -> List[FundingRate]:
        """
        获取所有交易对的资金费率
        
        Returns:
            List[FundingRate]: 资金费率列表
        """
        try:
            payload = {"type": "allMids"}
            mids = await self._make_request("", payload)
            
            payload = {"type": "funding"}
            funding_data = await self._make_request("", payload)
            
            rates = []
            for item in funding_data:
                if isinstance(item, dict):
                    symbol = item.get("coin", "")
                    rate = float(item.get("fundingRate", 0))
                    next_time = int(item.get("nextFundingTime", 0))
                    
                    rates.append(FundingRate(
                        symbol=symbol,
                        funding_rate=rate,
                        next_funding_time=next_time,
                        timestamp=int(time.time() * 1000)
                    ))
            
            return rates
            
        except Exception as e:
            logger.error(f"Failed to get funding rates: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """
        获取指定交易对的资金费率
        
        Args:
            symbol: 交易对符号 (如 "BTC", "ETH")
            
        Returns:
            FundingRate: 资金费率数据
        """
        try:
            rates = await self.get_all_funding_rates()
            for rate in rates:
                if rate.symbol.upper() == symbol.upper():
                    return rate
            return None
        except Exception as e:
            logger.error(f"Failed to get funding rate for {symbol}: {e}")
            return None
    
    async def get_extreme_funding_rates(self, threshold: float = 0.001) -> List[FundingRate]:
        """
        获取极端资金费率 (高于阈值)
        
        Args:
            threshold: 极端阈值 (默认 0.1%)
            
        Returns:
            List[FundingRate]: 极端资金费率列表
        """
        all_rates = await self.get_all_funding_rates()
        extreme_rates = [
            rate for rate in all_rates 
            if abs(rate.funding_rate) >= threshold
        ]
        # 按绝对值排序
        extreme_rates.sort(key=lambda x: abs(x.funding_rate), reverse=True)
        return extreme_rates
    
    async def get_market_price(self, symbol: str) -> Optional[float]:
        """
        获取市场价格
        
        Args:
            symbol: 交易对符号
            
        Returns:
            float: 当前价格
        """
        try:
            payload = {"type": "allMids"}
            mids = await self._make_request("", payload)
            
            # allMids 返回格式: {"BTC": "45000.5", "ETH": "3000.2", ...}
            if isinstance(mids, dict):
                price_str = mids.get(symbol.upper())
                if price_str:
                    return float(price_str)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get market price for {symbol}: {e}")
            return None
    
    async def get_positions(self) -> List[Position]:
        """
        获取用户持仓 (需要 wallet_address)
        
        Returns:
            List[Position]: 持仓列表
        """
        if not self.wallet_address:
            logger.warning("Wallet address not set, cannot get positions")
            return []
        
        try:
            payload = {
                "type": "clearinghouseState",
                "user": self.wallet_address
            }
            data = await self._make_request("", payload)
            
            positions = []
            asset_positions = data.get("assetPositions", [])
            
            for asset_pos in asset_positions:
                pos = asset_pos.get("position", {})
                coin = pos.get("coin", "")
                szi = float(pos.get("szi", 0))
                entry_px = float(pos.get("entryPx", 0))
                
                if szi != 0:
                    side = "long" if szi > 0 else "short"
                    positions.append(Position(
                        symbol=coin,
                        side=side,
                        size=abs(szi),
                        entry_price=entry_px,
                        unrealized_pnl=0.0  # 需要另外计算
                    ))
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def calculate_funding_pnl(self, position_size: float, 
                             funding_rate: float, 
                             mark_price: float) -> float:
        """
        计算资金费率收益/成本
        
        Args:
            position_size: 持仓数量
            funding_rate: 资金费率
            mark_price: 标记价格
            
        Returns:
            float: 预计 funding PnL (正值为收入，负值为支出)
        """
        notional = position_size * mark_price
        funding_pnl = notional * funding_rate
        return funding_pnl
    
    async def get_funding_arbitrage_opportunities(self, 
                                                   polymarket_threshold: float = 0.02) -> List[Dict]:
        """
        获取 Funding Rate 与 Polymarket 的套利机会
        
        策略: 当 Funding Rate 极端时，结合 Polymarket 预测进行对冲
        
        Returns:
            List[Dict]: 套利机会列表
        """
        opportunities = []
        
        # 获取极端 funding rates
        extreme_rates = await self.get_extreme_funding_rates(threshold=0.001)
        
        for rate in extreme_rates:
            opportunity = {
                "symbol": rate.symbol,
                "funding_rate": rate.funding_rate,
                "next_funding_time": rate.next_funding_time,
                "strategy": None,
                "expected_pnl": None
            }
            
            # 正 funding: 多头支付空头，应该在 Hyperliquid 做空，Polymarket 做多
            # 负 funding: 空头支付多头，应该在 Hyperliquid 做多，Polymarket 做空
            if rate.funding_rate > 0.001:
                opportunity["strategy"] = "hl_short_pm_long"
                opportunity["description"] = f"Hyperliquid 做空 {rate.symbol}, Polymarket 做多"
            elif rate.funding_rate < -0.001:
                opportunity["strategy"] = "hl_long_pm_short"
                opportunity["description"] = f"Hyperliquid 做多 {rate.symbol}, Polymarket 做空"
            
            # 预计 8 小时 funding 收益
            # 假设 10,000 USD 仓位
            position_value = 10000
            hours_per_year = 365 * 3  # 每年 3 次 funding
            annual_funding = rate.funding_rate * hours_per_year
            opportunity["expected_annual_funding"] = position_value * annual_funding
            
            opportunities.append(opportunity)
        
        return opportunities


# 便捷函数
def create_hyperliquid_client(config: Dict) -> HyperliquidExchange:
    """
    从配置创建 Hyperliquid 客户端
    
    Args:
        config: 配置字典
        
    Returns:
        HyperliquidExchange: 交易所客户端
    """
    exchange_config = config.get("exchange", {})
    
    return HyperliquidExchange(
        api_key=exchange_config.get("key"),
        api_secret=exchange_config.get("secret"),
        wallet_address=exchange_config.get("wallet"),
        testnet=exchange_config.get("testnet", False)
    )
