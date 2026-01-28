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
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

# Load environment
load_dotenv()

from logging.handlers import RotatingFileHandler

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('polymarket-bot/bot.log', maxBytes=5*1024*1024, backupCount=3) # 5MB limit, keep 3 backups
    ]
)
logger = logging.getLogger(__name__)

# Constants
CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
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
        if self.book_up.best_ask <= 0: return 0.03 # Fallback max
        
        spread = self.book_up.best_ask - self.book_up.best_bid
        fee = spread / self.book_up.best_ask
        
        # Cap at 3% as per user knowledge, but allow lower if spread is tight
        return max(0.001, min(0.05, fee))

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
        Get Order Book Imbalance (OBI).
        Ratio = Bids Volume / Asks Volume
        > 1.0 : Buyers stronger
        < 1.0 : Sellers stronger
        """
        try:
            url = "https://api.binance.com/api/v3/depth"
            params = {"symbol": symbol, "limit": limit}
            resp = requests.get(url, params=params, timeout=2)
            data = resp.json()
            
            bids = sum([float(x[1]) for x in data.get("bids", [])])
            asks = sum([float(x[1]) for x in data.get("asks", [])])
            
            if asks == 0: return 999.0
            return bids / asks
        except:
            return 1.0 # Neutral on error

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
        self.volatility_per_min = 25.0  # Conservative BTC vol/min in USD (approx)
        # TODO: Calculate dynamic vol
    
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

import joblib

# ... imports ...

class PolymarketBotV3:
    def __init__(self):
        self.running = True
        self.paper_trade = True
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
        
        self.performance_history = [] 
        
        # Load ML Model
        self.ml_model = None
        if os.path.exists("polymarket-bot/ml_model_v1.pkl"):
            try:
                self.ml_model = joblib.load("polymarket-bot/ml_model_v1.pkl")
                logger.info("🧠 ML Model Loaded: Random Forest v1")
            except Exception as e:
                logger.error(f"Failed to load ML model: {e}")

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
                    logger.info(f"⚙️ 配置已加载: SL {self.stop_loss_pct:.0%} | Edge {self.min_edge:.0%} | OBI {self.obi_threshold}x")
            else:
                logger.warning("⚠️ 配置文件未找到，使用默认参数")
                # Defaults already set in init? No, setting them now if missing
                if not hasattr(self, 'stop_loss_pct'): self.stop_loss_pct = 0.35
                if not hasattr(self, 'safety_margin_pct'): self.safety_margin_pct = 0.0006
                if not hasattr(self, 'min_edge'): self.min_edge = 0.08
                if not hasattr(self, 'fee_pct'): self.fee_pct = 0.03
                if not hasattr(self, 'obi_threshold'): self.obi_threshold = 1.5
        except Exception as e:
            logger.error(f"Config load error: {e}")

    def analyze_performance(self):
        """Self-Correction: Adjust parameters based on recent performance"""
        try:
            if not os.path.exists("paper_trades.jsonl"): return
            
            # File Size Protection: If > 10MB, rotate it
            if os.path.getsize("paper_trades.jsonl") > 10 * 1024 * 1024:
                logger.info("维护: paper_trades.jsonl 过大，进行归档清理...")
                os.rename("paper_trades.jsonl", f"paper_trades_{int(time.time())}.jsonl")
            
            wins = 0
            losses = 0
            gross_profit = 0.0
            gross_loss = 0.0
            recent_trades = []
            
            with open("paper_trades.jsonl", "r") as f:
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
                # Run augment script
                proc = await asyncio.create_subprocess_shell("python3 polymarket-bot/augment_data.py")
                await proc.wait()
                
                # Run train script
                proc = await asyncio.create_subprocess_shell("python3 polymarket-bot/train_ml.py")
                await proc.wait()
                
                # Reload model
                if os.path.exists("polymarket-bot/ml_model_v1.pkl"):
                    self.ml_model = joblib.load("polymarket-bot/ml_model_v1.pkl")
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
                
            time_left = market.time_remaining.total_seconds() / 60.0 # minutes
            
            # 2. Calculate Fair Value
            prob_up = self.strategy.calculate_prob_up(current_btc, market.strike_price, time_left)
            prob_down = 1.0 - prob_up
            
            # 3. AI Prediction Boost
            if self.ml_model:
                try:
                    hour = datetime.now(timezone.utc).hour
                    # Simple prediction based on market structure
                    # If AI predicts WIN for UP, we boost prob_up
                    # Warning: This is a simplified integration
                    X = [[market.up_price, 1, hour]]
                    if self.ml_model.predict(X)[0] == 1:
                        prob_up += 0.05
                except: pass

            # 3. Compare with Market
            # Market prices from WS
            mkt_up = market.up_price
            mkt_down = market.down_price
            
            # 4. Decision
            # Calculate dynamic Safety Margin to account for Binance vs Chainlink deviation
            # using percentage (0.05%) instead of fixed amount
            safety_margin = market.strike_price * self.safety_margin_pct
            
            diff = current_btc - market.strike_price
            
            # Check Stop Loss for existing positions
            await self.check_stop_loss(market)

            # If within safety margin (ambiguous zone), force neutral probability or skip
            if abs(diff) < safety_margin:
                logger.info(f"价格差异 ${diff:.1f} 在安全边际(${safety_margin:.1f}, {self.safety_margin_pct:.2%})内 - 跳过")
                await asyncio.sleep(2)
                continue
            
            # Only trade if we don't have a position in this market yet (Simple mode)
            has_position = any(p['market_slug'] == market.slug for p in self.positions)
            
            if not has_position and abs(diff) >= safety_margin:
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
                    f"Prob UP: {prob_up:.1%} | OBI: {obi:.2f}x | Edge: {edge_up:+.1%}"
                )
                
                # Only log every 10s
                if int(time.time()) % 10 == 0:
                    logger.info(log_msg)
                
                # Execute Trade (With OBI Filter)
                # UP: Need Edge + OBI > 1 / Threshold (Don't buy into heavy sell wall)
                if edge_up > self.min_edge:
                    if obi > (1 / self.obi_threshold): 
                        await self.execute_trade(market, "UP", 0.05)
                    else:
                        logger.info(f"🛑 拦截 UP 信号: 卖压太重 (OBI {obi:.2f} < {1/self.obi_threshold:.2f})")
                        
                # DOWN: Need Edge + OBI < Threshold (Don't sell into heavy buy wall)
                elif edge_down > self.min_edge:
                    if obi < self.obi_threshold:
                        await self.execute_trade(market, "DOWN", 0.05)
                    else:
                        logger.info(f"🛑 拦截 DOWN 信号: 买盘太强 (OBI {obi:.2f} > {self.obi_threshold:.2f})")
                        
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

    async def settle_positions(self, market, final_price):
        """Settle open positions for paper trading"""
        if not self.paper_trade: return
        
        strike = market.strike_price
        if not strike: return
        
        # Determine Winner
        # "Up" if Final >= Strike
        winner = "UP" if final_price >= strike else "DOWN"
        logger.info(f"🏆 结算结果: {winner} (Strike: {strike} vs Final: {final_price})")
        
        # Iterate remaining positions for this market
        for p in list(self.positions):
            if p["market_slug"] != market.slug: continue
            
            payout = 1.0 if p["direction"] == winner else 0.0
            pnl_amt = payout - p["entry_price"]
            pnl_pct = pnl_amt / p["entry_price"]
            
            logger.info(f"💰 结算归档: {p['direction']} -> PnL: {pnl_pct:.1%}")
            
            with open("paper_trades.jsonl", "a") as f:
                f.write(json.dumps({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "type": "SETTLED",
                    "market": market.slug,
                    "direction": p["direction"],
                    "entry_price": p["entry_price"],
                    "exit_price": payout, # 1.0 or 0.0
                    "pnl": pnl_pct,
                    "result": "WIN" if payout > 0 else "LOSS"
                }) + "\n")
            
            self.positions.remove(p)

    async def check_stop_loss(self, market: Market15m):
        """Check if any position needs to be stopped out"""
        # Copy list to modify safe
        for p in list(self.positions):
            if p["market_slug"] != market.slug: continue
            
            current_price = market.up_price if p["direction"] == "UP" else market.down_price
            entry_price = p["entry_price"]
            
            # PnL calculation
            pnl_pct = (current_price - entry_price) / entry_price
            
            if pnl_pct < -self.stop_loss_pct:
                logger.warning(f"🛑 止损触发! {p['direction']} @ {current_price:.2f} (Entry: {entry_price:.2f}, PnL: {pnl_pct:.1%})")
                
                if self.paper_trade:
                    with open("paper_trades.jsonl", "a") as f:
                        f.write(json.dumps({
                            "time": datetime.now(timezone.utc).isoformat(),
                            "type": "STOP_LOSS",
                            "market": market.slug,
                            "direction": p["direction"],
                            "exit_price": current_price,
                            "pnl": pnl_pct
                        }) + "\n")
                else:
                    # Real sell logic would go here
                    pass
                
                self.positions.remove(p)

    async def execute_trade(self, market, direction, size):
        # Double check to prevent duplicates
        if any(p['market_slug'] == market.slug for p in self.positions):
            logger.warning(f"⚠️ 忽略重复下单请求: {market.slug}")
            return

        # Simple limit order logic
        price = market.up_price if direction == "UP" else market.down_price
        # Cap price
        price = min(0.99, max(0.01, price))
        
        if self.paper_trade:
             logger.info(f"🔥 SIGNAL: BUY {direction} @ {price:.2f} (Paper Trade)")
             
             # Record Position
             self.positions.append({
                 "market_slug": market.slug,
                 "direction": direction,
                 "entry_price": price,
                 "size": size,
                 "timestamp": datetime.now(timezone.utc).isoformat()
             })

             with open("paper_trades.jsonl", "a") as f:
                 f.write(json.dumps({
                     "time": datetime.now().isoformat(),
                     "type": "V3_SMART",
                     "direction": direction,
                     "price": price,
                     "strike": market.strike_price,
                     "fee": self.fee_pct # Record fee assumption
                 }) + "\n")
             await asyncio.sleep(10) # Cooldown
        else:
            # Real execution code here
            pass

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
