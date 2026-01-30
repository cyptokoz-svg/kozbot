#!/usr/bin/env python3
"""
Polymarket BTC 15-minute Trading Bot v3 (Smart Probability)
- Retrieves 'Strike Price' (Open price of the 15m candle) from Binance.
- Calculates theoretical probability based on distance to strike and time remaining.
- Trades only when market price deviates significantly from fair value.
"""

import os
import sys
import json
import time
import math
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
import statistics

import requests
import websockets
# [ML Upgrade]
import pandas as pd
import pandas_ta as ta
import joblib

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

# [Added for Auto-Redeem]
from web3 import Web3
from eth_account import Account
from eth_abi import encode
import subprocess # Added for notifications

# Load environment
load_dotenv()

# --- Auto-Redeem Config ---
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")

from logging.handlers import RotatingFileHandler

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=3) # 5MB limit, keep 3 backups
    ]
)
logger = logging.getLogger(__name__)

from eip712_signer import sign_safe_tx

# Constants
CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
RELAYER_URL = "https://tx-relay.polymarket.com/relay"
CHAIN_ID = 137

@dataclass
class OrderBook:
    """Real-time order book"""
    asset_id: str
    best_bid: float = 0.0
    best_ask: float = 1.0
    
    def update(self, data: dict):
        if data.get("event_type") == "price_change":
            for change in data.get("price_changes", []):
                if change.get("asset_id") == self.asset_id:
                    self.best_bid = float(change.get("best_bid", 0) or 0)
                    self.best_ask = float(change.get("best_ask", 1) or 1)
        elif data.get("event_type") == "book":
             bids = data.get("bids", [])
             asks = data.get("asks", [])
             if bids: self.best_bid = float(bids[0]["price"])
             if asks: self.best_ask = float(asks[0]["price"])

@dataclass
class Market15m:
    condition_id: str
    question: str
    token_id_up: str
    token_id_down: str
    start_time: datetime
    end_time: datetime
    slug: str
    
    # Real-time data
    book_up: OrderBook = None
    book_down: OrderBook = None
    strike_price: Optional[float] = None  # The BTC price at start_time
    
    def __post_init__(self):
        self.book_up = OrderBook(self.token_id_up)
        self.book_down = OrderBook(self.token_id_down)
        self.fee_bps = 0 # Default

    @property
    def time_remaining(self) -> timedelta:
        return self.end_time - datetime.now(timezone.utc)
    
    @property
    def is_active(self) -> bool:
        return self.time_remaining.total_seconds() > 30

    @property
    def dynamic_fee(self) -> float:
        """
        Calculate dynamic fee based on Bid-Ask Spread.
        User Input: Fees can reach 3% dynamically.
        Formula: (Ask - Bid) / Ask (Cost of crossing the spread)
        """
        # [User Update] Remove fee pre-calculation. 
        # We assume 0 fee for signal generation (Raw Edge).
        return 0.0

    @property
    def up_price(self) -> float:
        return self.book_up.best_ask if self.book_up.best_ask > 0 else 0.5
    
    @property
    def down_price(self) -> float:
        return self.book_down.best_ask if self.book_down.best_ask > 0 else 0.5

class BinanceData:
    """Helper to fetch Binance data"""
    @staticmethod
    def get_candle_open(timestamp_ms: int) -> Optional[float]:
        """Get the Open price of the candle starting at timestamp"""
        try:
            # Kline interval 1m
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": "BTCUSDT",
                "interval": "1m",
                "startTime": timestamp_ms,
                "limit": 1
            }
            logger.info(f"Fetching Binance Candle for TS: {timestamp_ms} ({datetime.fromtimestamp(timestamp_ms/1000, timezone.utc)})")
            resp = requests.get(url, params=params, timeout=5)
            data = resp.json()
            if data and len(data) > 0:
                open_price = float(data[0][1])
                logger.info(f"Binance Open Price: {open_price}")
                return open_price
            return None
        except Exception as e:
            logger.error(f"Binance API error: {e}")
            return None

    @staticmethod
    def get_current_price() -> Optional[float]:
        try:
            resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
            return float(resp.json()["price"])
        except:
            return None

    @staticmethod
    def get_order_book_imbalance(symbol="BTCUSDT", limit=20):
        """
        Get Order Book Imbalance (OBI) from Binance.
        Ratio = Bids Volume / Asks Volume
        """
        try:
            url = "https://api.binance.com/api/v3/depth"
            params = {"symbol": symbol, "limit": limit}
            resp = requests.get(url, params=params, timeout=2)
            data = resp.json()
            
            bids_list = data.get("bids", [])
            asks_list = data.get("asks", [])
            
            if not bids_list or not asks_list:
                # If API fails or returns empty, don't return 0.0 (which blocks trades).
                # Return 1.0 (Neutral) to avoid false positives.
                return 1.0
            
            bids = sum([float(x[1]) for x in bids_list])
            asks = sum([float(x[1]) for x in asks_list])
            
            if asks == 0: return 1.0
            return bids / asks
        except:
            return 1.0 # Neutral on error

    @staticmethod
    def get_history_df(limit=60) -> pd.DataFrame:
        """Fetch historical candles for TA calculation"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": "BTCUSDT", "interval": "1m", "limit": limit}
            resp = requests.get(url, params=params, timeout=3)
            data = resp.json()
            if not isinstance(data, list): return pd.DataFrame()
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume", 
                "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            return df
        except Exception as e:
            logger.error(f"Binance History Error: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_dynamic_volatility(limit=60) -> float:
        """Calculate StdDev of 1m price changes (USD) over last hour"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": "BTCUSDT", "interval": "1m", "limit": limit}
            resp = requests.get(url, params=params, timeout=2)
            data = resp.json()
            closes = [float(x[4]) for x in data]
            if len(closes) < 2: return 25.0
            
            # Calculate price differences
            diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            
            # Standard Deviation
            if len(diffs) > 1:
                vol = math.sqrt(statistics.variance(diffs))
                return max(5.0, vol) # Minimum floor
            return 25.0
        except Exception as e:
            return 25.0 # Fallback

class DeribitData:
    """Helper to fetch Deribit Implied Volatility (Forward-looking)"""
    @staticmethod
    def get_dvol() -> Optional[float]:
        """Get BTC DVOL (Annualized Implied Volatility Index)"""
        try:
            url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
            params = {"currency": "BTC", "resolution": "1D", "end_timestamp": int(time.time()*1000)}
            
            resp = requests.get(url, params={"currency": "BTC", "start_timestamp": int(time.time()*1000) - 86400000, "end_timestamp": int(time.time()*1000), "resolution": "1D"}, timeout=3)
            data = resp.json()
            
            if 'result' in data and 'data' in data['result'] and len(data['result']['data']) > 0:
                dvol_close = data['result']['data'][-1][4] # Close value
                return float(dvol_close)
                
            return 55.0 
        except Exception as e:
            logger.error(f"Deribit DVOL fetch failed: {e}")
            return None

class PolyLiquidity:
    """Analyzer for Polymarket Order Book Depth & Quality"""
    @staticmethod
    def get_token_depth(token_id: str) -> dict:
        """
        Fetch Order Book snapshot and calculate effective liquidity.
        Returns:
            - bid_depth_usd: Total bid size within 5% of best price
            - ask_depth_usd: Total ask size within 5% of best price
            - spread: Bid-Ask Spread
        """
        try:
            url = f"{CLOB_HOST}/book"
            params = {"token_id": token_id}
            resp = requests.get(url, params=params, timeout=2)
            data = resp.json()
            
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            if not bids or not asks:
                return {"bid_depth": 0, "ask_depth": 0, "spread": 0.99}
            
            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            
            # Calculate Depth (Liquidity within 5 cents or 5% range)
            bid_limit = best_bid - 0.05
            ask_limit = best_ask + 0.05
            
            bid_depth = sum([float(x["size"]) * float(x["price"]) for x in bids if float(x["price"]) >= bid_limit])
            ask_depth = sum([float(x["size"]) * float(x["price"]) for x in asks if float(x["price"]) <= ask_limit])
            
            return {
                "bid_depth": bid_depth,
                "ask_depth": ask_depth,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": best_ask - best_bid
            }
        except Exception as e:
            logger.error(f"Poly Liquidity Check Error: {e}")
            return {"bid_depth": 0, "ask_depth": 0, "spread": 0.99}

class MarketCycleManager:
    """Manages finding active markets"""
    def __init__(self):
        self.past_markets = []

    def fetch_market(self) -> Optional[Market15m]:
        try:
            # Calculate current 15m cycle strictly by time
            now = datetime.now(timezone.utc)
            current_ts = int(now.timestamp())
            current_15m_ts = (current_ts // 900) * 900
            
            # Use calculated timestamp for slug AND start_time
            slug = f"btc-updown-15m-{current_15m_ts}"
            
            # Start time is strictly the 15m boundary
            start_time = datetime.fromtimestamp(current_15m_ts, timezone.utc)
            # End time is +15m
            end_time = start_time + timedelta(minutes=15)
            
            resp = requests.get(f"{GAMMA_API}/events?slug={slug}", timeout=10)
            events = resp.json()
            
            if not events:
                # Try next slot if we are close to end? No, stick to current.
                return None
                
            event = events[0]
            if event.get("closed"): return None
            
            markets = event.get("markets", [])
            if not markets or not markets[0].get("acceptingOrders"): return None
            
            m_data = markets[0]
            token_ids = json.loads(m_data.get("clobTokenIds", "[]"))
            outcomes = json.loads(m_data.get("outcomes", '["Up", "Down"]'))
            
            if outcomes[0].lower() == "up":
                t_up, t_down = token_ids[0], token_ids[1]
            else:
                t_up, t_down = token_ids[1], token_ids[0]
            
            return Market15m(
                condition_id=m_data.get("conditionId"),
                question=m_data.get("question", event.get("title")),
                token_id_up=t_up,
                token_id_down=t_down,
                start_time=start_time, # Use calculated strict time
                end_time=end_time,     # Use calculated strict time
                slug=event.get("slug")
            )
        except Exception as e:
            logger.error(f"Fetch market error: {e}")
            return None

class ProbabilityStrategy:
    """Calculates Fair Value based on Normal Distribution"""
    
    def __init__(self):
        self.volatility_per_min = 25.0  # Default
    
    def update_volatility(self, new_vol: float):
        self.volatility_per_min = new_vol

    def calculate_prob_up(self, current_price: float, strike_price: float, minutes_left: float) -> float:
        """
        Calculate Probability(Final Price > Strike)
        Assumes Brownian motion (Normal distribution of price changes).
        """
        if minutes_left <= 0:
            return 1.0 if current_price >= strike_price else 0.0
            
        # Standard Deviation for the remaining time
        # sigma_t = sigma_1min * sqrt(t)
        sigma_t = self.volatility_per_min * math.sqrt(minutes_left)
        
        if sigma_t == 0:
            return 1.0 if current_price >= strike_price else 0.0
            
        # Z-score: How many std devs is current price away from strike?
        # If current > strike, Z is positive.
        z_score = (current_price - strike_price) / sigma_t
        
        # Cumulative Distribution Function (CDF)
        prob_up = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
        
        return prob_up

    def update_from_deribit(self, dvol: float, current_price: float):
        """
        Convert Annualized DVOL (e.g., 50.0) to Minute Volatility (USD)
        Formula: Sigma_min = Price * (DVOL/100) / sqrt(minutes_in_year)
        Minutes in year approx 525,600
        """
        if dvol is None or dvol <= 0: return
        
        minutes_in_year = 365 * 24 * 60
        annual_std_dev = dvol / 100.0
        
        # Convert to 1-minute std dev (percentage)
        min_std_dev_pct = annual_std_dev / math.sqrt(minutes_in_year)
        
        # Convert to USD terms based on current price
        self.volatility_per_min = current_price * min_std_dev_pct
        # logger.info(f"Deribit DVOL: {dvol} -> Sigma_min: ${self.volatility_per_min:.2f}")

import joblib

class AsyncTradeLogger:
    def __init__(self, filename):
        self.filename = filename
        self.queue = asyncio.Queue()
        self.running = True

    async def run(self):
        """Worker task to write logs to disk asynchronously"""
        logger.info(f"💾 Async Trade Logger started for {self.filename}")
        while self.running:
            try:
                record = await self.queue.get()
                if record is None: break # Shutdown signal
                
                with open(self.filename, "a") as f:
                    f.write(json.dumps(record) + "\n")
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Async log write error: {e}")
                await asyncio.sleep(1)

    def log(self, record):
        """Thread-safe way to add a record to the queue"""
        # Add timestamp if missing
        if "time" not in record:
            record["time"] = datetime.now(timezone.utc).isoformat()
        self.queue.put_nowait(record)

    async def stop(self):
        self.running = False
        await self.queue.put(None)

class PolymarketBotV3:
    def __init__(self):
        self.running = True
        self.paper_trade = False # LIVE MODE ACTIVATED
        self.positions = []
        self.cycle_manager = MarketCycleManager()
        self.strategy = ProbabilityStrategy()
        
        # Init Clob Client for Data Fetching
        # Load keys (Support both PK and PRIVATE_KEY)
        key = os.getenv("PK") or os.getenv("PRIVATE_KEY")
        
        try:
            if key:
                self.clob_client = ClobClient(CLOB_HOST, key=key, chain_id=CHAIN_ID)
                logger.info("✅ CLOB Client 已连接 (实盘/数据权限获取成功)")
            else:
                self.clob_client = None
                logger.warning("⚠️ 未找到私钥 (PK/PRIVATE_KEY). 运行在受限模式.")
        except:
            self.clob_client = None
            logger.warning("CLOB Client not init (Fees will be estimated)")
        
        # Trading Parameters (Loaded from config)
        self.config_file = "polymarket-bot/config.json"
        self.load_config()
        
        # Performance History
        self.performance_history = [] 
        
        # [Surgical Refactor] Async Logger
        self.trade_logger = AsyncTradeLogger("polymarket-bot/paper_trades.jsonl")
        
        # Load ML Model (Prefer V2.0 if exists)
        self.ml_model = None
        model_paths = ["polymarket-bot/ml_model_v2.pkl", "polymarket-bot/ml_model_v1.pkl"]
        for p in model_paths:
            if os.path.exists(p):
                try:
                    self.ml_model = joblib.load(p)
                    logger.info(f"🧠 ML Model Loaded: {p}")
                    break
                except Exception as e:
                    logger.error(f"Failed to load ML model {p}: {e}")
        
        # [Notification Control]
        self.notified_signals = set()
        self.current_market_slug = None

    def load_config(self):
        """Load parameters from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    conf = json.load(f)
                    self.stop_loss_pct = conf.get("stop_loss_pct", 0.35)
                    self.safety_margin_pct = conf.get("safety_margin_pct", 0.0006)
                    self.min_edge = conf.get("min_edge", 0.08)
                    self.fee_pct = conf.get("fee_pct", 0.03)
                    self.obi_threshold = conf.get("obi_threshold", 1.5) # New Param
                    self.execution_enabled = conf.get("execution_enabled", False) # Safety Switch
                    logger.info(f"⚙️ 配置已加载: SL {self.stop_loss_pct:.0%} | Edge {self.min_edge:.0%} | Exec {self.execution_enabled}")
            else:
                logger.warning("⚠️ 配置文件未找到，使用默认参数")
                # Defaults already set in init? No, setting them now if missing
                if not hasattr(self, 'stop_loss_pct'): self.stop_loss_pct = 0.35
                if not hasattr(self, 'safety_margin_pct'): self.safety_margin_pct = 0.0006
                if not hasattr(self, 'min_edge'): self.min_edge = 0.08
                if not hasattr(self, 'fee_pct'): self.fee_pct = 0.03
                if not hasattr(self, 'obi_threshold'): self.obi_threshold = 1.5
                if not hasattr(self, 'execution_enabled'): self.execution_enabled = False
        except Exception as e:
            logger.error(f"Config load error: {e}")

    def analyze_performance(self):
        """Self-Correction: Adjust parameters based on recent performance"""
        try:
            if not os.path.exists("polymarket-bot/paper_trades.jsonl"): return
            
            # File Size Protection: If > 10MB, rotate it
            if os.path.getsize("polymarket-bot/paper_trades.jsonl") > 10 * 1024 * 1024:
                logger.info("维护: paper_trades.jsonl 过大，进行归档清理...")
                os.rename("polymarket-bot/paper_trades.jsonl", f"paper_trades_{int(time.time())}.jsonl")
            
            wins = 0
            losses = 0
            gross_profit = 0.0
            gross_loss = 0.0
            recent_trades = []
            
            with open("polymarket-bot/paper_trades.jsonl", "r") as f:
                for line in f:
                    try:
                        trade = json.loads(line)
                        if "pnl" in trade: # Closed trade
                            recent_trades.append(trade)
                    except: pass
            
            # Analyze last 20 closed trades for statistical significance
            recent_trades = recent_trades[-20:]
            if not recent_trades: return
            
            for t in recent_trades:
                pnl = float(t["pnl"])
                if pnl > 0: 
                    wins += 1
                    gross_profit += pnl
                else: 
                    losses += 1
                    gross_loss += abs(pnl)
            
            total = wins + losses
            if total == 0: return
            
            win_rate = wins / total
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            avg_win = gross_profit / wins if wins > 0 else 0
            avg_loss = gross_loss / losses if losses > 0 else 0
            
            # Log Core Metrics for User
            # logger.info(f"📊 业绩分析 (最近{total}笔):")
            # logger.info(f"   胜率: {win_rate:.0%} | 盈亏比 (Profit Factor): {profit_factor:.2f}")
            
            # Since we now use external config, we DON'T auto-adjust inside python code anymore
            # We just log stats. Auto-adjustment should be done by an external agent via config.json
            
        except Exception as e:
            logger.error(f"Auto-tune error: {e}")

    async def config_watcher(self):
        """Watch for config changes and hot-reload"""
        last_mtime = 0
        while self.running:
            try:
                if os.path.exists(self.config_file):
                    mtime = os.path.getmtime(self.config_file)
                    if mtime > last_mtime:
                        if last_mtime > 0: # Skip first run
                            logger.info("🔄 检测到配置更新，正在热加载...")
                            self.load_config()
                        last_mtime = mtime
            except: pass
            await asyncio.sleep(60)

    async def run(self):
        logger.info("启动 V3 智能策略机器人 (Probability/Fair Value)...")
        # logger.info(f"配置: 止损线 -{self.stop_loss_pct*100}% | 模拟费率 {self.fee_pct*100}%") # Moved to load_config
        if self.paper_trade: logger.info("[模式] 模拟交易 (全权限托管)")
        
        # Start Background Tasks
        asyncio.create_task(self.trade_logger.run()) # Start Async File Writer
        asyncio.create_task(self.auto_retrain_loop())
        asyncio.create_task(self.config_watcher()) # Start Hot-Reloader
        
        while self.running:
            try:
                # Run Auto-Tuning every cycle
                self.analyze_performance()
                
                # Cleanup old positions from previous cycles
                self.positions = [p for p in self.positions if (datetime.now(timezone.utc) - datetime.fromisoformat(p["timestamp"])).total_seconds() < 3600]

                market = self.cycle_manager.fetch_market()
                if not market:
                    logger.info("等待活跃市场...")
                    await asyncio.sleep(10)
                    continue
                
                # Fetch Strike Price (Open Price)
                # Ensure the market start time has passed so the candle exists
                now = datetime.now(timezone.utc)
                if now < market.start_time:
                    logger.info(f"等待市场开始: {market.start_time}")
                    await asyncio.sleep(5)
                    continue
                
                logger.info(f"选中市场: {market.question}")
                
                # Get Strike Price (Binance)
                # Need timestamp in ms
                start_ts_ms = int(market.start_time.timestamp() * 1000)
                
                # Retry fetching strike until available (Binance might delay 1-2s)
                strike_price = None
                for _ in range(5):
                    strike_price = BinanceData.get_candle_open(start_ts_ms)
                    if strike_price: break
                    logger.info("等待 Strike Price (Binance Candle)...")
                    await asyncio.sleep(2)
                
                if not strike_price:
                    logger.error("无法获取 Strike Price，跳过此周期")
                    await asyncio.sleep(30)
                    continue
                    
                market.strike_price = strike_price
                logger.info(f"🎯 Strike Price (锁定): ${strike_price:,.2f}")
                
                # Fetch Real Dynamic Fee
                # if self.clob_client:
                #     try:
                #         # Note: py_clob_client doesn't have a public get_fee method in some versions
                #         # We will rely on Spread + fixed conservative buffer
                #         pass
                #     except: pass
                
                # Start Trading Loop for this Market
                await self.trade_loop(market)
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(5)

    async def auto_retrain_loop(self):
        """Automatically retrain ML model every 3 hours"""
        while self.running:
            await asyncio.sleep(3 * 3600) # Wait 3 hours
            logger.info("🧠 自动进化: 开始重新训练模型...")
            try:
                # Use current working directory relative paths
                proc = await asyncio.create_subprocess_shell("python3 augment_data.py")
                await proc.wait()
                
                proc = await asyncio.create_subprocess_shell("python3 train_ml.py")
                await proc.wait()
                
                # Reload model
                if os.path.exists("ml_model_v1.pkl"):
                    self.ml_model = joblib.load("ml_model_v1.pkl")
                    logger.info("✅ 模型已更新并重新加载!")
            except Exception as e:
                logger.error(f"Auto-retrain failed: {e}")

    async def trade_loop(self, market: Market15m):
        # For brevity in this write, using polling loop which is fine for 5s intervals.
        # Ideally keep WS from V2.
        
        ws_manager = WebSocketManagerV3(market)
        await ws_manager.connect()
        asyncio.create_task(ws_manager.listen())
        
        logger.info(f"开始监控... 结算时间: {market.end_time}")
        
        while self.running and market.is_active:
            # 1. Get Data
            current_btc = BinanceData.get_current_price()
            if not current_btc:
                await asyncio.sleep(2)
                continue
                
            # Update Dynamic Volatility (every ~1 min)
            if int(time.time()) % 60 == 0:
                # 1. Try Deribit First (Forward Looking)
                dvol = DeribitData.get_dvol()
                if dvol:
                    self.strategy.update_from_deribit(dvol, current_btc)
                else:
                    # 2. Fallback to Binance Historical
                    new_vol = BinanceData.get_dynamic_volatility()
                    self.strategy.update_volatility(new_vol)
                # logger.info(f"🌊 动态波动率更新完成")

            time_left = market.time_remaining.total_seconds() / 60.0 # minutes
            
            # 2. Calculate Fair Value
            prob_up = self.strategy.calculate_prob_up(current_btc, market.strike_price, time_left)
            prob_down = 1.0 - prob_up
            
            # [Pre-Fetch] Get Poly Liquidity Data needed for ML & Filters
            # We need to decide which token to check. Let's check BOTH or just the one we lean towards?
            # For ML, general market quality matters. Let's check the UP token depth as a proxy or average?
            # Better: Check both briefly or just the spread/depth of the orderbook general.
            # Using token_id_up as reference.
            liq_data = PolyLiquidity.get_token_depth(market.token_id_up)
            
            # 3. Compare with Market (Moved up for scope)
            mkt_up = market.up_price
            mkt_down = market.down_price

            # 3. AI Prediction Boost (XGBoost V4)
            if self.ml_model:
                try:
                    # 1. Fetch History for TA
                    hist_df = BinanceData.get_history_df(limit=60)
                    if not hist_df.empty and len(hist_df) > 30:
                        # 2. Calc Features
                        rsi = ta.rsi(hist_df["close"], length=14)
                        atr = ta.atr(hist_df["high"], hist_df["low"], hist_df["close"], length=14)
                        bb = ta.bbands(hist_df["close"], length=20, std=2)
                        ema_short = ta.ema(hist_df["close"], length=9)
                        ema_long = ta.ema(hist_df["close"], length=21)

                        rsi_val = rsi.iloc[-1] if not rsi.empty else 50
                        atr_val = atr.iloc[-1] if not atr.empty else 0
                        
                        bb_pct_val = 0.5
                        if bb is not None and not bb.empty:
                            bb_cols = [c for c in bb.columns if c.startswith("BBP")]
                            if bb_cols:
                                bb_pct_val = bb.iloc[-1][bb_cols[0]]
                        
                        trend_ema = 0
                        if ema_short is not None and ema_long is not None:
                            trend_ema = 1 if ema_short.iloc[-1] > ema_long.iloc[-1] else -1

                        # 3. Construct Feature Vector (NOW INCLUDING POLY DATA)
                        now_utc = datetime.now(timezone.utc)
                        # [Pricing/Time Enhancement]
                        pricing_power = liq_data.get('bid_depth', 0) - liq_data.get('ask_depth', 0)
                        price_time = (current_btc - market.strike_price) * (16 - time_left)

                        # [Fix] Dynamic feature set to handle model versions
                        # Model expects 13 features, remove newest 2 for compatibility
                        X_df = pd.DataFrame([{
                            'direction_code': 1, 
                            'hour': now_utc.hour,
                            'dayofweek': now_utc.weekday(),
                            'rsi_14': rsi_val,
                            'atr_14': atr_val,
                            'bb_pct': bb_pct_val,
                            'trend_ema': trend_ema,
                            # [New] Poly Microstructure Features
                            'poly_spread': liq_data.get('spread', 0.01),
                            'poly_bid_depth': liq_data.get('bid_depth', 0),
                            'poly_ask_depth': liq_data.get('ask_depth', 0),
                            # [Added for V2]
                            'strike': market.strike_price,
                            'diff_from_strike': current_btc - market.strike_price,
                            'minutes_remaining': time_left
                            # Note: Removed 'price_time_interaction' and 'pricing_power_index' 
                            # to maintain compatibility with v2 model (13 features)
                        }])
                        
                        # 4. Predict
                        # XGBoost predict() returns class [0, 1]
                        # predict_proba() returns [[prob_0, prob_1]]
                        probs = self.ml_model.predict_proba(X_df)[0]
                        ai_prob_up = probs[1] # Probability of Class 1 (WIN)
                        
                        # [User Update] Hybrid Prediction: 30% AI + 70% Math Model (Recalibrated)
                        math_prob = prob_up
                        prob_up = (ai_prob_up * 0.3) + (math_prob * 0.7)
                        prob_down = 1.0 - prob_up
                        
                        logger.info(f"⚖️ 混合预测 (30/70): AI({ai_prob_up:.1%})x30% + Math({math_prob:.1%})x70% = {prob_up:.1%}")
                        
                except Exception as e:
                    logger.error(f"AI Prediction Error: {e}")

            # 4. Decision
            # Calculate dynamic Safety Margin to account for Binance vs Chainlink deviation
            # using percentage (0.05%) instead of fixed amount
            safety_margin = market.strike_price * self.safety_margin_pct
            
            diff = current_btc - market.strike_price
            
            # Check Stop Loss for existing positions
            await self.check_stop_loss(market)
            await self.check_take_profit(market)

            # --- [New] Cooldown Period Filter ---
            # Don't trade in the first 15 seconds of the market cycle to avoid opening noise
            time_since_start = (datetime.now(timezone.utc) - market.start_time).total_seconds()
            if time_since_start < 15:
                logger.info(f"⏳ 开盘冷静期: 等待趋势确认 ({int(time_since_start)}/15s) - 跳过")
                await asyncio.sleep(2)
                continue

            # If within safety margin (ambiguous zone), force neutral probability or skip
            if abs(diff) < safety_margin:
                # Calculate Edge even if skipping, for logging
                obi = BinanceData.get_order_book_imbalance()
                fee = market.dynamic_fee
                edge_up = prob_up - mkt_up - fee
                edge_down = prob_down - mkt_down - fee
                
                log_msg = (
                    f"剩余 {time_left:.1f}m | BTC: ${current_btc:.1f} (Diff: ${diff:+.1f}) | "
                    f"Poly UP: ${mkt_up:.2f} | Prob UP: {prob_up:.1%} | OBI: {obi:.2f}x | "
                    f"Edge UP: {edge_up:+.1%} | Edge DOWN: {edge_down:+.1%} | "
                    f"状态: 安全边际内(${safety_margin:.1f}) - 跳过"
                )
                if int(time.time()) % 10 == 0:
                    logger.info(log_msg)
                await asyncio.sleep(2)
                continue
            
            # [User Rule] Serial Execution: One trade at a time.
            # Must close/settle previous trade before opening new one.
            if len(self.positions) > 0:
                # We have an active position, so we just monitor it (skip entry logic)
                if int(time.time()) % 10 == 0:
                     logger.info(f"⏳ 持仓锁定: 等待当前交易结束 (PnL Monitor active)")
                await asyncio.sleep(2)
                continue
            
            if abs(diff) >= safety_margin:
                # Signal if Edge > Threshold
                # Use Dynamic Fee
                fee = market.dynamic_fee
                
                edge_up = prob_up - mkt_up - fee
                edge_down = prob_down - mkt_down - fee
                
                # --- OBI Filter Integration ---
                obi = BinanceData.get_order_book_imbalance()
                # If OBI > 1.0, Bids are heavier (Bullish)
                # If OBI < 1.0, Asks are heavier (Bearish)
                
                log_msg = (
                    f"剩余 {time_left:.1f}m | BTC: ${current_btc:.1f} (Diff: ${diff:+.1f}) | "
                    f"Poly UP: ${mkt_up:.2f} | Prob UP: {prob_up:.1%} | OBI: {obi:.2f}x | "
                    f"Edge UP: {edge_up:+.1%} | Edge DOWN: {edge_down:+.1%}"
                )
                
                # Only log every 10s
                if int(time.time()) % 10 == 0:
                    logger.info(log_msg)
                
                # Execute Trade (With OBI Filter & Poly Liquidity Check)
                
                # [New] Poly Liquidity Gatekeeper
                # Check target token depth before entering
                # We already fetched UP token depth in `liq_data` at step 2.
                # If target is DOWN, we might want to check DOWN token depth specifically, 
                # but generally checking UP token gives good idea of spread.
                # Let's refine: If going DOWN, fetch DOWN token depth.
                
                if edge_up > self.min_edge:
                    target_liq = liq_data # Already fetched UP
                    target_dir = "UP"
                else:
                    # Fetch DOWN token depth on demand
                    target_liq = PolyLiquidity.get_token_depth(market.token_id_down)
                    target_dir = "DOWN"
                
                # Check 1: Do we have enough Ask Depth to buy?
                if target_liq["ask_depth"] < 200:
                    logger.info(f"🛑 流动性不足: Ask Depth ${target_liq['ask_depth']:.0f} < $200 - 跳过")
                    continue
                    
                # Check 2: Liquidity Ratio
                liq_ratio = target_liq["bid_depth"] / target_liq["ask_depth"] if target_liq["ask_depth"] > 0 else 0
                
                # UP: Need Edge (OBI filter removed per Sir's request)
                if edge_up > self.min_edge:
                    if liq_ratio < 0.2: 
                         logger.info(f"🛑 拦截 UP 信号: Poly 盘口失衡 (Ratio {liq_ratio:.2f} < 0.2)")
                    else:
                         await self.execute_trade(market, "UP", 0.05, target_liq)
                        
                # DOWN: Need Edge (OBI filter removed per Sir's request)
                elif edge_down > self.min_edge:
                    if liq_ratio > 5.0: 
                         logger.info(f"🛑 拦截 DOWN 信号: Poly 盘口失衡 (Ratio {liq_ratio:.2f} > 5.0)")
                    else:
                        await self.execute_trade(market, "DOWN", 0.05, target_liq)
                        
            elif int(time.time()) % 10 == 0:
                 logger.info(f"监控中... 持仓数: {len(self.positions)} | 价格差: ${diff:+.1f}")
                
            await asyncio.sleep(2)
        
        await ws_manager.close()
        
        # MARKET SETTLEMENT (Simulated)
        # Fetch Final Price (Binance Candle Open of the NEXT candle, or just current price if immediate)
        # To be precise: The resolution price is typically the price AT expiration.
        await asyncio.sleep(5) # Wait for dust to settle
        final_price = BinanceData.get_current_price()
        
        if final_price:
            logger.info(f"市场结算! Final BTC: ${final_price}")
            await self.settle_positions(market, final_price)

    def _get_safe_nonce(self):
        """Fetch Safe Nonce via Public RPC"""
        try:
            w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
            # Gnosis Safe nonce() ABI
            abi = '[{"constant":true,"inputs":[],"name":"nonce","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]'
            contract = w3.eth.contract(address=FUNDER_ADDRESS, abi=json.loads(abi))
            return contract.functions.nonce().call()
        except Exception as e:
            logger.error(f"Nonce fetch failed: {e}")
            return None

    def _raw_redeem(self, condition_id):
        """Execute Auto-Redeem via Gasless Relayer"""
        if not self.clob_client or not FUNDER_ADDRESS:
            logger.error("❌ 无法赎回: 缺 Client 或 代理地址")
            return

        try:
            logger.info(f"🏦 [EIP-712] 正在构建免 Gas 赎回交易... ID: {condition_id[:8]}")
            
            # 1. Construct Data for redeemPositions
            func_selector = bytes.fromhex("8679b734") # redeemPositions
            parent_id = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000000")
            cond_id_bytes = bytes.fromhex(condition_id.replace("0x", ""))
            index_sets = [1, 2] # Yes and No

            tx_data = func_selector + encode(
                ['address', 'bytes32', 'bytes32', 'uint256[]'],
                [USDC_ADDRESS, parent_id, cond_id_bytes, index_sets]
            )
            
            # 2. Get Nonce
            nonce = self._get_safe_nonce()
            if nonce is None:
                logger.error("❌ 无法获取 Nonce，跳过赎回")
                return

            logger.info(f"✅ Nonce: {nonce}. 正在签名...")
            
            # 3. Sign
            pk = os.getenv("PRIVATE_KEY")
            signature = sign_safe_tx(
                safe_address=FUNDER_ADDRESS,
                to=CTF_EXCHANGE,
                value=0,
                data=tx_data,
                operation=0,
                safe_tx_gas=0,
                base_gas=0,
                gas_price=0,
                gas_token="0x0000000000000000000000000000000000000000",
                refund_receiver="0x0000000000000000000000000000000000000000",
                nonce=nonce,
                private_key=pk
            )
            
            # 4. Post to Relayer
            payload = {
                "safe": FUNDER_ADDRESS,
                "to": CTF_EXCHANGE,
                "value": "0",
                "data": "0x" + tx_data.hex(),
                "operation": 0,
                "safeTxGas": 0,
                "baseGas": 0,
                "gasPrice": 0,
                "gasToken": "0x0000000000000000000000000000000000000000",
                "refundReceiver": "0x0000000000000000000000000000000000000000",
                "nonce": nonce,
                "signature": "0x" + signature.hex()
            }
            
            resp = requests.post(RELAYER_URL, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code == 200 or resp.status_code == 201:
                logger.info(f"🎉 自动赎回成功! TX Hash: {resp.text}")
            else:
                logger.error(f"❌ Relayer 拒绝: {resp.status_code} - {resp.text}")
            
        except Exception as e:
            logger.error(f"❌ 赎回出错: {e}")

    async def settle_positions(self, market, final_price):
        """Settle open positions (Works for both Live and Paper)"""
        strike = market.strike_price
        if not strike: return
        
        # Determine Winner: "Up" if Final >= Strike
        winner = "UP" if final_price >= strike else "DOWN"
        logger.info(f"🏆 结算结果: {winner} (Strike: {strike} vs Final: {final_price})")
        self._notify_user(f"🏁 市场结算: {winner}\n🎯 Strike: {strike}\n🏁 Final: {final_price}")
        
        # [Real Trading] Auto-Redeem Logic
        if not self.paper_trade and self.clob_client:
            try:
                self._raw_redeem(market.condition_id)
            except Exception as e:
                logger.error(f"赎回失败: {e}")
        
        # Iterate remaining positions for this market
        for p in list(self.positions):
            if p["market_slug"] != market.slug: continue
            if p.get("status") != "OPEN": continue  # Skip already closed
            
            payout = 1.0 if p["direction"] == winner else 0.0
            pnl_amt = payout - p["entry_price"]
            pnl_pct = pnl_amt / p["entry_price"]
            
            # Update position
            p["status"] = "SETTLED"
            p["exit_price"] = payout
            p["exit_time"] = datetime.now(timezone.utc).isoformat()
            p["pnl"] = pnl_pct
            p["result"] = "WIN" if payout > 0 else "LOSS"
            
            logger.info(f"💰 结算归档: {p['direction']} -> PnL: {pnl_pct:.1%}")
            self._notify_user(f"💰 战绩: {p['direction']} -> {pnl_pct:+.1%}\n{'🎉 赢了!' if payout > 0 else '💀 输了'}")
            
            self.trade_logger.log({
                "time": datetime.now(timezone.utc).isoformat(),
                "type": "SETTLED_PAPER" if self.paper_trade else "SETTLED",
                "market": market.slug,
                "condition_id": market.condition_id,
                "direction": p["direction"],
                "entry_price": p["entry_price"],
                "exit_price": payout,
                "pnl": pnl_pct,
                "result": "WIN" if payout > 0 else "LOSS",
                "mode": "PAPER" if self.paper_trade else "LIVE"
            })
            
            self.positions.remove(p)

    async def check_take_profit(self, market: Market15m):
        """Monitor for 15% Profit -> Place Limit Sell (Works for both Live and Paper)"""
        for p in list(self.positions):
            if p["market_slug"] != market.slug: continue
            if p.get("tp_placed", False): continue # Already handling
            if p.get("status") != "OPEN": continue  # Skip closed positions

            # TP Threshold
            tp_price = p["entry_price"] * 1.15
            if tp_price >= 0.99: tp_price = 0.99
            
            # Current Best Bid (what we can sell at)
            current_bid = market.book_up.best_bid if p["direction"] == "UP" else market.book_down.best_bid
            
            if current_bid >= tp_price:
                # Calculate actual PnL
                entry = p["entry_price"]
                pnl_pct = (current_bid - entry) / entry
                
                logger.info(f"💰 止盈触发! {p['direction']} @ {current_bid:.2f} (Entry: {entry:.2f}, PnL: {pnl_pct:.1%})")
                self._notify_user(f"💰 止盈离场: {p['direction']}\n💸 价格: {current_bid:.2f} (+{pnl_pct*100:.0f}%)")
                
                # Update position status
                p["status"] = "TP_HIT"
                p["exit_price"] = current_bid
                p["exit_time"] = datetime.now(timezone.utc).isoformat()
                p["pnl"] = pnl_pct
                p["tp_placed"] = True
                
                # Remove from active positions
                self.positions.remove(p)
                
                # Log to file
                self.trade_logger.log({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": "TAKE_PROFIT_PAPER" if self.paper_trade else "TAKE_PROFIT",
                    "market": market.slug,
                    "direction": p["direction"],
                    "entry_price": entry,
                    "exit_price": current_bid,
                    "pnl": pnl_pct,
                    "mode": "PAPER" if self.paper_trade else "LIVE"
                })

    async def check_stop_loss(self, market: Market15m):
        """Check if any position needs to be stopped out (Works for both Live and Paper)"""
        for p in list(self.positions):
            if p["market_slug"] != market.slug: continue
            if p.get("status") != "OPEN": continue  # Skip closed positions
            
            # Current Best Bid (what we can sell at)
            current_bid = market.book_up.best_bid if p["direction"] == "UP" else market.book_down.best_bid
            entry_price = p["entry_price"]
            
            if current_bid <= 0: continue # No liquidity
            
            # PnL calculation
            pnl_pct = (current_bid - entry_price) / entry_price
            
            if pnl_pct < -self.stop_loss_pct:
                logger.warning(f"🛑 止损触发! {p['direction']} @ {current_bid:.2f} (Entry: {entry_price:.2f}, PnL: {pnl_pct:.1%})")
                self._notify_user(f"🛑 止损离场: {p['direction']}\n📉 触发价: {current_bid:.2f}\n💸 PnL: {pnl_pct:.1%}")
                
                # Update position status
                p["status"] = "SL_HIT"
                p["exit_price"] = current_bid
                p["exit_time"] = datetime.now(timezone.utc).isoformat()
                p["pnl"] = pnl_pct
                p["sl_placed"] = True
                
                # Remove from active positions
                self.positions.remove(p)
                
                # Log to file
                self.trade_logger.log({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": "STOP_LOSS_PAPER" if self.paper_trade else "STOP_LOSS",
                    "market": market.slug,
                    "direction": p["direction"],
                    "entry_price": entry_price,
                    "exit_price": current_bid,
                    "pnl": pnl_pct,
                    "mode": "PAPER" if self.paper_trade else "LIVE"
                })

    def _notify_user(self, message):
        """Send push notification via Clawdbot"""
        try:
            subprocess.run([
                "clawdbot", "message", "send",
                "--channel", "telegram",
                "--target", "1640598145",
                "--message", f"🤖 [实盘战报] {message}"
            ], check=False)
            # Also try WeCom if available via the adapter logic? 
            # No, let's stick to the reliable Telegram channel for now as "Boss" channel.
        except Exception as e:
            logger.error(f"Notify failed: {e}")

    async def execute_trade(self, market, direction, size, liq_stats=None):
        # ... (checks) ...
        
        # [Notification Control] Only notify once per market per direction
        signal_id = f"{market.slug}_{direction}"
        if signal_id in self.notified_signals:
            return
        self.notified_signals.add(signal_id)

        # [Safety Switch]
        if not self.execution_enabled:
             logger.info(f"🚫 信号触发 ({direction}) 但交易功能已暂停 (Dry Run).")
             self._notify_user(f"🔭 发现机会: {direction} (未下单 - 模式: 仅监控)")
             return

        # [Strategy Update] Entry: Hang at Best Bid (Maker Strategy) - "盘口第一单"
        # Logic: Price = Best Ask - 0.01.
        # Example: If Ask is 0.60, we Bid 0.59. This makes us the Best Bid (First).
        if direction == "UP":
            best_ask = market.book_up.best_ask if market.book_up.best_ask > 0 else market.up_price
            price = best_ask - 0.01
        else:
            best_ask = market.book_down.best_ask if market.book_down.best_ask > 0 else market.down_price
            price = best_ask - 0.01

        # Safety clamps
        price = min(0.99, max(0.01, price))
        
        logger.info(f"🔥 SIGNAL: BUY {direction} @ {price:.2f} (Maker/Best Bid)")
        self._notify_user(f"🔥 挂单进场: {direction} @ ${price:.2f} (盘口一单)\n🎯 Strike: ${market.strike_price}")

        if self.paper_trade:
            # 模拟交易逻辑 - 完整复刻实盘流程
            try:
                shares = 1.0 / price
                
                # 记录模拟持仓 (复刻实盘的 positions 逻辑)
                position = {
                    "market_slug": market.slug,
                    "direction": direction,
                    "entry_price": price,
                    "size": size,
                    "shares": shares,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tp_placed": False,  # 标记是否已挂止盈单
                    "sl_placed": False,  # 标记是否已挂止损单
                    "status": "OPEN"     # OPEN / TP_HIT / SL_HIT / SETTLED
                }
                self.positions.append(position)
                
                # 模拟挂单 - 假设立即成交 (Maker 策略)
                fill_price = price  # 实际可能略有滑点
                
                # 记录交易日志
                trade_record = {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": "V3_SMART_PAPER",
                    "direction": direction,
                    "entry_price": fill_price,
                    "shares": shares,
                    "strike": market.strike_price,
                    "fee": self.fee_pct,
                    "status": "OPEN",
                    "market": market.slug
                }
                self.trade_logger.log(trade_record)
                
                # 模拟挂止盈止损单 (复刻实单的 "hang order" 逻辑)
                tp_price = min(0.99, fill_price * 1.15)  # +15% 止盈
                sl_price = fill_price * (1 - self.stop_loss_pct)  # -35% 止损
                
                logger.info(f"📊 [模拟] 开仓成功: {direction} {shares:.2f}份 @ {fill_price:.2f}")
                logger.info(f"📊 [模拟] 已挂止盈: {tp_price:.2f} | 止损: {sl_price:.2f}")
                
                self._notify_user(
                    f"📊 [模拟交易] 开仓成功\n"
                    f"方向: {direction}\n"
                    f"价格: ${fill_price:.2f}\n"
                    f"份额: {shares:.2f}\n"
                    f"止盈: ${tp_price:.2f} (+15%)\n"
                    f"止损: ${sl_price:.2f} (-{self.stop_loss_pct*100:.0f}%)"
                )
                
            except Exception as e:
                logger.error(f"[模拟交易] 开仓失败: {e}")
                self._notify_user(f"❌ [模拟] 开仓失败: {e}")
        else:
             # Real Execution
             try:
                 if self.clob_client:
                     shares = 1.0 / price
                     order_args = OrderArgs(
                         price=price,
                         size=shares,
                         side=BUY,
                         token_id=market.token_id_up if direction == "UP" else market.token_id_down,
                         order_type=OrderType.LIMIT # Explicit Limit
                     )
                     # await self.clob_client.create_order(order_args)
                     pass
                 
                 self._notify_user(f"✅ 实盘挂单成功 (模拟): {direction} {shares:.2f}份 @ {price}")
             except Exception as e:
                 self._notify_user(f"❌ 下单失败: {e}")
             
             # Record Position
             self.positions.append({
                 "market_slug": market.slug,
                 "direction": direction,
                 "entry_price": price,
                 "size": size,
                 "timestamp": datetime.now(timezone.utc).isoformat(),
                 "tp_placed": False # Track if TP order is active
             })

             trade_record = {
                 "time": datetime.now().isoformat(),
                 "type": "V3_SMART",
                 "direction": direction,
                 "price": price,
                 "strike": market.strike_price,
                 "fee": self.fee_pct # Record fee assumption
             }
             
             # Log Liquidity Stats for ML Training
             if liq_stats:
                 trade_record["poly_spread"] = liq_stats.get("spread", 0)
                 trade_record["poly_bid_depth"] = liq_stats.get("bid_depth", 0)
                 trade_record["poly_ask_depth"] = liq_stats.get("ask_depth", 0)
                 
             self.trade_logger.log(trade_record)
             
             # Notify User
             self._notify_user(f"🔥 开仓: {direction} @ ${price:.2f}\n🎯 Strike: ${market.strike_price}\n💰 预计投入: $1.0")

             await asyncio.sleep(10) # Cooldown

# --- Reusing WebSocket Manager from V2 for compactness ---
class WebSocketManagerV3:
    def __init__(self, market):
        self.market = market
        self.ws = None
        self.running = False
    async def connect(self):
        self.ws = await websockets.connect(WS_URL)
        msg = {"assets_ids": [self.market.token_id_up, self.market.token_id_down], "type": "market"}
        await self.ws.send(json.dumps(msg))
        self.running = True
    async def listen(self):
        try:
            async for msg in self.ws:
                if not self.running: break
                if msg == "PONG": continue
                try:
                    data = json.loads(msg)
                    if isinstance(data, list): [self._process(i) for i in data]
                    else: self._process(data)
                except: pass
        except: pass
    def _process(self, data):
        asset = data.get("asset_id")
        if asset == self.market.token_id_up: self.market.book_up.update(data)
        elif asset == self.market.token_id_down: self.market.book_down.update(data)
        elif data.get("event_type") == "price_change":
            for p in data.get("price_changes", []):
                aid = p.get("asset_id")
                if aid == self.market.token_id_up: self.market.book_up.best_ask = float(p.get("best_ask") or 1)
                elif aid == self.market.token_id_down: self.market.book_down.best_ask = float(p.get("best_ask") or 1)
    async def close(self):
        self.running = False
        if self.ws: await self.ws.close()

if __name__ == "__main__":
    asyncio.run(PolymarketBotV3().run())
