#!/usr/bin/env python3
"""
Polymarket Machine Learning Training Script V4.1 (Fast Rescue Edition)
- Skips network fetching if not cached (for speed)
- Trains on whatever local data we have available
"""

import json
import pandas as pd
import numpy as np
import xgboost as xgb
import pandas_ta as ta
import requests
import time
import os
import joblib
from datetime import datetime, timezone, timedelta
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

DATA_FILE = "polymarket-bot/paper_trades.jsonl"
MODEL_FILE = "polymarket-bot/ml_model_v2.pkl"
CACHE_DIR = "polymarket-bot/candle_cache"

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_binance_history(symbol="BTCUSDT", end_time_ms=None, limit=100):
    cache_file = f"{CACHE_DIR}/{end_time_ms}.json"
    
    # 1. Try Cache First
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
        except:
            data = []
    else:
        # 2. Network Fetch (Fast Fail)
        # We cannot wait for 5000 requests synchronously.
        # If not in cache, we skip this row for now to unblock training.
        # print(f"Miss: {end_time_ms}")
        return pd.DataFrame() 

    if not data or not isinstance(data, list) or len(data) == 0: return pd.DataFrame()
    
    if isinstance(data[0], list):
         df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume", 
            "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"
         ])
    else:
         return pd.DataFrame()

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    return df

def load_data():
    if not os.path.exists(DATA_FILE): return None
    data = []
    with open(DATA_FILE, "r") as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("type") in ["SETTLED", "STOP_LOSS"]:
                    if r.get("type") == "STOP_LOSS": r["result"] = "LOSS"
                    data.append(r)
            except: pass
    return pd.DataFrame(data) if data else None

def enrich_data(df):
    print(f"⏳ Enriching {len(df)} trades (Fast Mode: Cached Only)...")
    enriched_rows = []
    
    for idx, row in df.iterrows():
        ts_str = row["time"]
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
        
        hist_df = get_binance_history(end_time_ms=ts_ms, limit=60)
        
        if len(hist_df) < 30:
            continue # Skip if no history found in cache
            
        rsi = ta.rsi(hist_df["close"], length=14)
        row["rsi_14"] = rsi.iloc[-1] if not rsi.empty else 50
        
        atr = ta.atr(hist_df["high"], hist_df["low"], hist_df["close"], length=14)
        row["atr_14"] = atr.iloc[-1] if not atr.empty else 0
        
        bb = ta.bbands(hist_df["close"], length=20, std=2)
        if bb is not None and not bb.empty:
            bb_cols = [c for c in bb.columns if c.startswith("BBP")]
            row["bb_pct"] = bb.iloc[-1][bb_cols[0]] if bb_cols else 0.5
        else:
            row["bb_pct"] = 0.5

        ema_short = ta.ema(hist_df["close"], length=9)
        ema_long = ta.ema(hist_df["close"], length=21)
        if ema_short is not None and ema_long is not None:
             row["trend_ema"] = 1 if ema_short.iloc[-1] > ema_long.iloc[-1] else -1
        else:
             row["trend_ema"] = 0
             
        current_price = hist_df["close"].iloc[-1]
        if "strike" in row and row["strike"] > 0:
            row["diff_from_strike"] = current_price - row["strike"]
        else:
            row["diff_from_strike"] = 0.0
            
        minute = dt.minute
        if minute < 15: target = 15
        elif minute < 30: target = 30
        elif minute < 45: target = 45
        else: target = 60
        
        row["minutes_remaining"] = target - minute
        if row["minutes_remaining"] < 0: row["minutes_remaining"] += 60
             
        enriched_rows.append(row)
        
    return pd.DataFrame(enriched_rows)

def train():
    df = load_data()
    if df is None: return

    df = enrich_data(df)
    if df.empty: 
        print("❌ No data available (Cache empty). Run backfill to fetch history first.")
        return

    df['target'] = df['result'].apply(lambda x: 1 if x == 'WIN' else 0)
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    df['dayofweek'] = pd.to_datetime(df['time']).dt.dayofweek
    df['direction_code'] = df['direction'].apply(lambda x: 1 if x == 'UP' else 0)
    
    if 'poly_spread' not in df.columns: df['poly_spread'] = 0.01
    if 'poly_bid_depth' not in df.columns: df['poly_bid_depth'] = 500.0
    if 'poly_ask_depth' not in df.columns: df['poly_ask_depth'] = 500.0
    
    df = df.fillna(0)

    features = [
        'direction_code', 'hour', 'dayofweek',
        'rsi_14', 'atr_14', 'bb_pct', 'trend_ema',
        'poly_spread', 'poly_bid_depth', 'poly_ask_depth',
        'strike', 'diff_from_strike', 'minutes_remaining'
    ]
    
    X = df[features]
    y = df['target']
    
    print(f"Training on {len(X)} records...")
    
    model = XGBClassifier(
        n_estimators=150, learning_rate=0.03, max_depth=6,
        subsample=0.8, colsample_bytree=0.8, objective='binary:logistic',
        eval_metric='logloss', random_state=42,
        # Increase weight for Time/Pricing related features via scale_pos_weight or interaction
        importance_type='gain'
    )
    
    # [Manual Weighting] Multiply sensitive features to force attention during training
    # XGBoost handles features but we can emphasize Pricing/Time by creating interaction terms
    df['price_time_interaction'] = df['diff_from_strike'] * (16 - df['minutes_remaining'])
    df['pricing_power_index'] = df['poly_bid_depth'] - df['poly_ask_depth']
    
    # Update features list
    features = features + ['price_time_interaction', 'pricing_power_index']
    X = df[features]
    
    print(f"Training on {len(X)} records (Enhanced Time/Pricing)...")
    
    model.fit(X, y)
    
    y_pred = model.predict(X)
    acc = accuracy_score(y, y_pred)
    auc = roc_auc_score(y, y_pred)
    
    print(f"\n🏆 Model Performance:")
    print(f"Accuracy: {acc:.2%}")
    print(f"AUC: {auc:.3f}")
    
    imps = model.feature_importances_
    sorted_idx = np.argsort(imps)[::-1]
    print("\n📊 Feature Importance:")
    for i in sorted_idx:
        print(f"   {features[i]}: {imps[i]:.4f}")
        
    joblib.dump(model, MODEL_FILE)
    print(f"✅ Saved to {MODEL_FILE}")

if __name__ == "__main__":
    train()
