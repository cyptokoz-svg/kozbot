"""
Hyperliquid Freqtrade Adapter
"""

from .exchange import HyperliquidExchange, FundingRate, Position, create_hyperliquid_client
from .funding_monitor import FundingMonitor, FundingSignalGenerator

__version__ = "0.1.0"
__all__ = [
    "HyperliquidExchange",
    "FundingRate", 
    "Position",
    "FundingMonitor",
    "FundingSignalGenerator",
    "create_hyperliquid_client"
]
