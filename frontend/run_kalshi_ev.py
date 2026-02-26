import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
import requests
import numpy as np
import pickle
import json
from scipy.stats import norm

# ==========================================
# 1. HARDWARE & DIRECTORY SETUP
# ==========================================
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Hardware backend: {DEVICE}")

# Pathing down from your root directory into the networks folder
DATA_DIR = 'networks/models'
MODEL_DIR = 'networks/models'

# Add the gatv2tcn source directory to sys.path so we can import the real architecture
GATV2TCN_DIR = os.path.join(os.path.dirname(__file__), 'networks', 'NBA-GNN-prediction')
sys.path.insert(0, GATV2TCN_DIR)

# ==========================================
# 2. ARCHITECTURE DEFINITION
# ==========================================
# Import the EXACT GATv2TCN class that was used during training
from gatv2tcn import GATv2TCN

# ==========================================
# 3. LOAD MODELS & HISTORICAL SCALING
# ==========================================
print("\nLoading models and normalization parameters...")

# Reconstruct the model with the EXACT same hyperparameters used during training.
# From the saved state_dict we can infer:
#   _gatv2conv_attention: GATv2Conv(in=17, out=32, heads=4, concat=True) -> output dim = 128
#   _time_convolution:    Conv2d(128, 64, kernel_size=(1,1))
#   _residual_convolution: Conv2d(17, 64, kernel_size=(1,1))
#   _layer_norm:          LayerNorm(64)
#   _final_conv:          Conv2d(10, 6, kernel_size=(1,64))
model = GATv2TCN(
    in_channels=17,
    out_channels=6,
    len_input=10,
    len_output=1,
    temporal_filter=64,
    out_gatv2conv=32,
    dropout_tcn=0.5,
    dropout_gatv2conv=0.5,
    head_gatv2conv=4,
).to(DEVICE)

# Embedding layers — dimensions must match the saved .pth files
team_emb = nn.Linear(30, 2).to(DEVICE)   # team_emb.pth: weight(2,30), bias(2)
pos_emb  = nn.Linear(3, 2).to(DEVICE)    # pos_emb.pth:  weight(2,3),  bias(2)

model.load_state_dict(torch.load(f'{MODEL_DIR}/model.pth', map_location=DEVICE))
team_emb.load_state_dict(torch.load(f'{MODEL_DIR}/team_emb.pth', map_location=DEVICE))
pos_emb.load_state_dict(torch.load(f'{MODEL_DIR}/pos_emb.pth', map_location=DEVICE))

model.eval(); team_emb.eval(); pos_emb.eval()
print("✅ All model weights loaded successfully.")

# Load historical daily parameters (Needed for un-normalizing current predictions)
mu_per_day = np.load(f'{DATA_DIR}/mu_per_day.npy')
sd_per_day = np.load(f'{DATA_DIR}/sd_per_day.npy')

with open(f'{DATA_DIR}/date_to_day_index.pkl', 'rb') as f:
    date_to_day_index = pickle.load(f)

# Load actual test metrics from the training run
with open(f'{DATA_DIR}/test_metrics_raw.json', 'r') as f:
    raw_metrics = json.load(f)

# Global RMSE from test evaluation (un-normalized scale)
GLOBAL_RMSE = raw_metrics["RMSE"]  # ~2.18

# Per-stat RMSE: we only have a single global RMSE from the checkpoint.
# Using it uniformly as a conservative approximation for all stat types.
STAT_NAMES = ["PTS", "AST", "REB", "STL", "BLK", "TO"]
HISTORICAL_RMSE = {stat: GLOBAL_RMSE for stat in STAT_NAMES}
print(f"   Using global test RMSE = {GLOBAL_RMSE:.3f} for EV calculations.")

# ==========================================
# 4. KALSHI API & EV LOGIC
# ==========================================
KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

def get_live_kalshi_markets(series_ticker="NBA"):
    """Fetches unauthenticated live market data from Kalshi API."""
    print(f"\nFetching live markets from Kalshi for {series_ticker}...")
    url = f"{KALSHI_BASE_URL}/markets?series_ticker={series_ticker}&status=open"
    
    response = requests.get(url)
    if response.status_code != 200:
        print(f"API Error: {response.status_code}")
        return []
        
    return response.json().get('markets', [])

def calculate_ev(predicted_stat, target_line, stat_type, yes_price_cents):
    """Calculates model probability and Expected Value ($) per contract."""
    rmse = HISTORICAL_RMSE.get(stat_type, GLOBAL_RMSE)
    
    # Calculate Probability of going OVER
    z_score = (target_line - predicted_stat) / rmse
    model_prob_over = 1 - norm.cdf(z_score)
    
    potential_profit = 100 - yes_price_cents
    prob_loss = 1 - model_prob_over
    
    ev = (model_prob_over * potential_profit) - (prob_loss * yes_price_cents)
    return model_prob_over, ev

# ==========================================
# 5. INFERENCE & EXECUTION
# ==========================================
def run_pipeline():
    # 1. MOCK TENSOR: Generating Live 10-Day Features
    # TODO: Replace this mock tensor with an active `nba_api` script that 
    # builds the live `X_live`, `G_live` graph for today's active rosters.
    print("\n--- MOCK INFERENCE RUN ---")
    print("Generating simulated graph forward pass...")
    
    # Simulating a prediction for a single player (e.g., Luka Doncic)
    mock_prediction = {"PTS": 33.2, "AST": 10.1, "REB": 9.4}
    player_name = "Luka Doncic"
    
    # 2. Fetch live Kalshi pricing
    markets = get_live_kalshi_markets(series_ticker="KXNBAP") # NBA Player Props ticker
    
    if not markets:
        print("No open Kalshi NBA player prop markets found right now. Using mock line.")
        markets = [{'title': 'Luka Doncic to score 33+ points?', 'yes_bid': 55, 'subtitle': 'PTS'}]
        
    # 3. Test EV Against Markets
    print(f"\nEvaluating Kalshi Lines for {player_name}:")
    for market in markets:
        # Simple filter for the specific player in this mock run
        if player_name.split()[0] in market.get('title', ''):
            stat_type = "PTS" if "points" in market.get('title', '').lower() else "AST"
            line = 32.5 # Extracted from market title in production
            yes_price = market.get('yes_bid', 50)
            
            if yes_price <= 0: continue
            
            prob, ev = calculate_ev(mock_prediction[stat_type], line, stat_type, yes_price)
            
            print(f"▶ {market.get('title')}")
            print(f"  Model Predicted {stat_type}: {mock_prediction[stat_type]:.1f}")
            print(f"  Market Price (Implied Prob): {yes_price}%")
            print(f"  Model Probability (Over):    {prob*100:.1f}%")
            print(f"  Expected Value (Per Share):  ${ev/100:.3f}")
            if ev > 0:
                print("  🔥 PROFITABLE EDGE DETECTED")
            else:
                print("  ❌ NEGATIVE EV - DO NOT BET")

if __name__ == "__main__":
    run_pipeline()