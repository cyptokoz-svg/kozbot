#!/usr/bin/env python3
"""
Polymarket Machine Learning Training Script
- Reads paper_trades.jsonl (historical data)
- Trains a Random Forest Classifier to predict WIN/LOSS
- Saves the model to be used by V4 bot
"""

import json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

DATA_FILE = "polymarket-bot/paper_trades.jsonl"
MODEL_FILE = "polymarket-bot/ml_model_v1.pkl"

def load_data():
    if not os.path.exists(DATA_FILE):
        print(f"No data file found at {DATA_FILE}")
        return None
        
    data = []
    with open(DATA_FILE, "r") as f:
        for line in f:
            try:
                record = json.loads(line)
                # We only want SETTLED records which have a result
                if record.get("type") == "SETTLED":
                    data.append(record)
            except:
                pass
    
    if not data:
        print("No settled trades found to train on.")
        return None
        
    df = pd.DataFrame(data)
    return df

def feature_engineering(df):
    """
    Convert raw trade data into ML features
    Target: 1 if WIN, 0 if LOSS
    """
    # Create target variable
    df['target'] = df['result'].apply(lambda x: 1 if x == 'WIN' else 0)
    
import pandas_ta as ta

def feature_engineering(df):
    """
    Convert raw trade data into ML features (Updated for V5: Technical Indicators)
    """
    # Create target variable
    df['target'] = df['result'].apply(lambda x: 1 if x == 'WIN' else 0)
    
    # 1. Basic Features
    df['direction_code'] = df['direction'].apply(lambda x: 1 if x == 'UP' else 0)
    df['datetime'] = pd.to_datetime(df['time'])
    df['hour'] = df['datetime'].dt.hour
    df['dayofweek'] = df['datetime'].dt.dayofweek
    
    # 2. Advanced Technical Indicators
    # We need a continuous price series to calculate RSI/Bollinger accurately.
    # Since 'df' is a list of trades (discrete), we can't calculate RSI directly on it.
    # Workaround: We use 'prev_trend' as a proxy for momentum, and add Volatility.
    
    if 'prev_trend' not in df.columns: df['prev_trend'] = 0.0
    df['prev_trend'] = df['prev_trend'].fillna(0.0)
    
    # Feature: Momentum Strength (Abs Trend)
    df['momentum_strength'] = df['prev_trend'].abs()
    
    # Feature: Contrarian Indicator (Is it huge drop/pump?)
    # If trend is > 1% or < -1%, it might mean "Overbought/Oversold"
    df['is_overbought'] = df['prev_trend'].apply(lambda x: 1 if x > 0.005 else 0)
    df['is_oversold'] = df['prev_trend'].apply(lambda x: 1 if x < -0.005 else 0)
    
    # Select features for training
    features = [
        'entry_price', 'direction_code', 'hour', 'dayofweek', 
        'prev_trend', 'momentum_strength', 'is_overbought', 'is_oversold'
    ]
    
    X = df[features]
    y = df['target']
    
    return X, y, features

def train_model():
    print("Loading data...")
    df = load_data()
    if df is None: return
    
    print(f"Found {len(df)} records.")
    
    print("Engineering features...")
    X, y, feature_names = feature_engineering(df)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest (with Grid Search)...")
    
    # Simple Grid Search
    best_score = 0
    best_clf = None
    
    for n_est in [50, 100, 200]:
        for max_depth in [None, 5, 10, 20]:
            clf = RandomForestClassifier(n_estimators=n_est, max_depth=max_depth, random_state=42)
            clf.fit(X_train, y_train)
            score = clf.score(X_test, y_test)
            if score > best_score:
                best_score = score
                best_clf = clf
                
    print(f"Best Params found. Valid Score: {best_score:.2%}")
    
    # Evaluate
    y_pred = best_clf.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Feature Importance
    importances = best_clf.feature_importances_
    indices = np.argsort(importances)[::-1]
    print("\n📊 Feature Importance:")
    for f in range(X_train.shape[1]):
        print(f"{f+1}. {feature_names[indices[f]]}: {importances[indices[f]]:.4f}")
    
    # Save
    print(f"Saving model to {MODEL_FILE}...")
    joblib.dump(best_clf, MODEL_FILE)
    print("✅ Done.")

if __name__ == "__main__":
    train_model()
