import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from typing import List, Dict, Any, Tuple
from tqdm import tqdm
import random
from scipy.stats import norm
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from networks.ballnet.backtesting.models import AbstractPredictor
except ImportError:
    from models import AbstractPredictor

# Directories
TRACKING_DIR = Path('networks/ballnet/outputs/tracking')
DATA_DIR = Path('networks/ballnet/outputs/data')
BACKTEST_DIR = Path('networks/ballnet/backtesting')

def load_actual_results() -> pd.DataFrame:
    parquet_path = DATA_DIR / 'raw_boxscores.parquet'
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing boxscores file: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    df['PLAYER_NAME_NORM'] = df['PLAYER_NAME'].str.lower().str.replace('[^a-z]', '', regex=True)
    return df

def get_actual_stat(df_boxscores: pd.DataFrame, game_date: str, player_name: str, stat_type: str):
    from datetime import datetime, timedelta
    norm_name = str(player_name).lower().replace('.', '').replace('-', '').replace(' ', '')
    d = datetime.strptime(game_date, "%Y-%m-%d")
    next_day = (d + timedelta(days=1)).strftime("%Y-%m-%d")
    for check_date in [game_date, next_day]:
        match = df_boxscores[
            (df_boxscores['GAME_DATE'] == check_date) & 
            (df_boxscores['PLAYER_NAME_NORM'].str.contains(norm_name, na=False))
        ]
        if len(match) > 0:
            row = match.iloc[0]
            val = row.get(stat_type)
            if pd.notna(val):
                return float(val), str(row.get('GAME_ID'))
    return None, None

def get_naive_probs(point_estimate: float, target_line: float, rmse: float = 2.18):
    z_score = (target_line - point_estimate) / rmse
    p_over = 1 - norm.cdf(z_score)
    p_under = 1 - p_over
    return p_over, p_under

def calc_ev(p_over: float, p_under: float, yes_ask: float, no_ask: float):
    ev_y = (p_over * (100 - yes_ask) - p_under * yes_ask) if yes_ask is not None and yes_ask > 0 else -999
    ev_n = (p_under * (100 - no_ask) - p_over * no_ask) if no_ask is not None and no_ask > 0 else -999
    return ev_y, ev_n

def extract_opportunities(predictor: AbstractPredictor) -> pd.DataFrame:
    print("Loading actual boxscore results...")
    df_boxscores = load_actual_results()
    
    historical_dir = TRACKING_DIR / 'kalshi_data'
    historical_files = sorted(historical_dir.glob('historical_*.json'))
    if not historical_files:
        raise ValueError("No historical Kalshi line data found.")
        
    print(f"Found {len(historical_files)} days of historical odds.")
    predictor.setup()
    
    opportunities = []
    stat_map = {'points': 'PTS','assists': 'AST','rebounds': 'REB','steals': 'STL','blocks': 'BLK','turnovers': 'TO'}
    
    for file_path in historical_files:
        game_date = file_path.stem.split('_')[1]
        with open(file_path, 'r') as f: 
            props = json.load(f)
            
        for prop in tqdm(props, desc=f"Ops for {game_date}", leave=False):
            title = prop.get('title', '')
            if ':' not in title: continue
            
            parts = title.split(':')
            player = parts[0].strip()
            rest = parts[1].strip().lower()
            import re
            match = re.search(r'([\d\.]+)\+?\s+([a-z]+)', rest)
            if not match: continue
            
            val_str, stat_word = match.groups()
            threshold = float(val_str)
            stat = stat_map.get(stat_word, stat_word.upper())
            yes_ask = prop.get('yes_ask')
            no_ask = prop.get('no_ask')
            if yes_ask is None or no_ask is None: continue
            
            actual_val, game_id = get_actual_stat(df_boxscores, game_date, player, stat)
            if actual_val is None: continue
            actual_over = actual_val >= threshold
            
            from datetime import datetime, timedelta
            d = datetime.strptime(game_date, "%Y-%m-%d")
            next_day = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            
            point_est = predictor.predict_point_estimate(player, stat, game_date) or predictor.predict_point_estimate(player, stat, next_day)
            conf_probs = predictor.predict_conformal_probability(player, stat, threshold, game_date) or predictor.predict_conformal_probability(player, stat, threshold, next_day)
            
            if point_est is None: continue
            
            naive_p_over, naive_p_under = get_naive_probs(point_est, threshold)
            naive_ev_y, naive_ev_n = calc_ev(naive_p_over, naive_p_under, yes_ask, no_ask)
            
            conf_ev_y, conf_ev_n, conf_p_over, conf_p_under = -999, -999, None, None
            if conf_probs:
                conf_p_over = conf_probs['p_over']
                conf_p_under = conf_probs['p_under']
                conf_ev_y, conf_ev_n = calc_ev(conf_p_over, conf_p_under, yes_ask, no_ask)
                
            opportunities.append({
                'date': game_date, 'player': player, 'stat': stat, 'game_id': game_id,
                'threshold': threshold, 'yes_ask': yes_ask, 'no_ask': no_ask,
                'actual_over': actual_over,
                'naive_p_over': naive_p_over, 'naive_p_under': naive_p_under,
                'naive_ev_y': naive_ev_y, 'naive_ev_n': naive_ev_n,
                'conf_p_over': conf_p_over, 'conf_p_under': conf_p_under,
                'conf_ev_y': conf_ev_y, 'conf_ev_n': conf_ev_n
            })
            
    return pd.DataFrame(opportunities)

def calc_kelly_fraction(p_win, cost):
    if pd.isna(p_win) or pd.isna(cost) or cost == 0: return 0.0
    b = (100 - cost) / cost
    f_star = p_win - ((1 - p_win) / b)
    if f_star < 0: return 0.0
    return f_star

def run_simulation(ops_df: pd.DataFrame, config: dict, strategy: str = 'conformal') -> Tuple[pd.DataFrame, dict]:
    init_bankroll = config.get('initial_bankroll', 10000.0)
    kelly_frac = config.get('kelly_frac', 0.25)
    max_ask = config.get('max_ask', 75.0)
    min_ev_over = config.get('min_ev_over', 0.0)
    min_ev_under = config.get('min_ev_under', 0.0)
    max_game_pct = config.get('max_game_bankroll_pct', 1.0)
    max_bets_over = config.get('max_bets_over', 999)
    max_bets_under = config.get('max_bets_under', 999)
    is_baseline = config.get('is_baseline', False)
    
    bankroll = init_bankroll
    executed_bets = []
    
    # Process day by day chronologically
    days = sorted(ops_df['date'].unique())
    daily_stats = []
    
    for day in days:
        day_ops = ops_df[ops_df['date'] == day]
        if day_ops.empty: continue
            
        potential_bets = []
        
        for _, row in day_ops.iterrows():
            if strategy == 'conformal' and pd.notna(row['conf_p_over']):
                ev_y = row['conf_ev_y']
                ev_n = row['conf_ev_n']
                p_over = row['conf_p_over']
                p_under = row['conf_p_under']
            elif strategy == 'naive':
                ev_y = row['naive_ev_y']
                ev_n = row['naive_ev_n']
                p_over = row['naive_p_over']
                p_under = row['naive_p_under']
            else:
                continue

            # Check YES Edge
            if ev_y >= min_ev_over and ev_y >= ev_n and row['yes_ask'] <= max_ask:
                k = calc_kelly_fraction(p_over, row['yes_ask']) * kelly_frac
                if k > 0:
                    potential_bets.append({
                        'date': day, 'player': row['player'], 'stat': row['stat'], 'game_id': row['game_id'],
                        'side': 'YES', 'ev': ev_y, 'cost': row['yes_ask'], 'k_frac': k, 
                        'won': row['actual_over'], 'p': p_over
                    })
            # Check NO Edge
            elif ev_n >= min_ev_under and ev_n > ev_y and row['no_ask'] <= max_ask:
                k = calc_kelly_fraction(p_under, row['no_ask']) * kelly_frac
                if k > 0:
                    potential_bets.append({
                        'date': day, 'player': row['player'], 'stat': row['stat'], 'game_id': row['game_id'],
                        'side': 'NO', 'ev': ev_n, 'cost': row['no_ask'], 'k_frac': k, 
                        'won': not row['actual_over'], 'p': p_under
                    })

        if not potential_bets:
            daily_stats.append({'date': day, 'bankroll': bankroll, 'bets_placed': 0, 'daily_pnl': 0.0, 'daily_cost': 0.0})
            continue

        if is_baseline:
            valid_bets_after_player_limits = potential_bets
        else:
            player_groups = defaultdict(list)
            for b in potential_bets: player_groups[b['player']].append(b)
            
            valid_bets_after_player_limits = []
            for player, bets in player_groups.items():
                yes_bets = [b for b in bets if b['side'] == 'YES']
                no_bets = [b for b in bets if b['side'] == 'NO']
                
                yes_bets.sort(key=lambda x: x['ev'], reverse=True)
                no_bets.sort(key=lambda x: x['ev'], reverse=True)
                
                valid_bets_after_player_limits.extend(yes_bets[:max_bets_over])
                valid_bets_after_player_limits.extend(no_bets[:max_bets_under])

            valid_bets_after_player_limits.sort(key=lambda x: x['ev'], reverse=True)
        
        game_allocations = defaultdict(float)
        
        daily_pnl = 0.0
        bets_placed = 0
        daily_cost = 0.0
        
        for b in valid_bets_after_player_limits:
            if is_baseline:
                wager = b['cost']  # Risk exactly the ask price
                b['wager'] = wager
                profit = (100 - b['cost']) if b['won'] else -b['cost']
                daily_pnl += profit
                daily_cost += wager
                bets_placed += 1
                b['profit'] = profit
                executed_bets.append(b)
            else:
                g_id = b['game_id']
                allowed_remaining = max_game_pct - game_allocations[g_id]
                if allowed_remaining <= 0: continue
                    
                actual_k_frac = min(b['k_frac'], allowed_remaining)
                game_allocations[g_id] += actual_k_frac
                
                wager = bankroll * actual_k_frac
                if wager < 1.0: # min wager 1 cent to avoid rounding-to-zero micro bets
                    continue
                    
                profit = (wager * (100 - b['cost']) / b['cost']) if b['won'] else -wager
                daily_pnl += profit
                daily_cost += wager
                bets_placed += 1
                
                b['wager'] = wager
                b['profit'] = profit
                executed_bets.append(b)
                
        bankroll += daily_pnl
        daily_stats.append({'date': day, 'bankroll': bankroll, 'bets_placed': bets_placed, 'daily_pnl': daily_pnl, 'daily_cost': daily_cost})

    if not daily_stats:
        return pd.DataFrame(), {'roi': 0.0, 'sharpe': 0.0, 'total_profit': 0.0, 'final_bankroll': init_bankroll}
        
    df_daily = pd.DataFrame(daily_stats)
    df_bets = pd.DataFrame(executed_bets)
    
    total_profit = bankroll - init_bankroll
    
    # Accurate ROI: Baseline ROI is total profit over total cost wagered over time.
    total_wagered = df_daily['daily_cost'].sum()
    if is_baseline:
        roi = total_profit / total_wagered if total_wagered > 0 else 0.0
    else:
        roi = total_profit / init_bankroll if init_bankroll > 0 else 0.0
    
    df_daily['daily_return'] = df_daily['daily_pnl'] / (df_daily['bankroll'] - df_daily['daily_pnl']).replace(0, 1)
    daily_returns = df_daily['daily_return'].fillna(0)
    avg_ret = daily_returns.mean()
    std_ret = daily_returns.std(ddof=1)
    sharpe = 0.0
    if std_ret > 0:
        sharpe = (avg_ret / std_ret) * np.sqrt(252)
        
    summary = {
        'config_id': config.get('config_id', 0),
        'total_profit': total_profit,
        'final_bankroll': bankroll,
        'roi': roi,
        'sharpe': sharpe,
        'total_bets': len(df_bets),
        'win_rate': len(df_bets[df_bets['profit'] > 0])/len(df_bets) if len(df_bets) > 0 else 0.0,
        **config
    }
    return df_bets, summary

def generate_random_configs(n=20) -> List[dict]:
    configs = []
    
    # Always include a conservative baseline config to compare
    configs.append({
        'config_id': 0, 'initial_bankroll': 10000.0,
        'kelly_frac': 0.1, 'max_ask': 70.0, 'min_ev_over': 2.0, 'min_ev_under': 2.0,
        'max_game_bankroll_pct': 0.05, 'max_bets_over': 1, 'max_bets_under': 1
    })
    
    for i in range(1, n):
        c = {
            'config_id': i,
            'initial_bankroll': 10000.0,
            'kelly_frac': random.uniform(0.0625, 1.0), # 1/16 to 1/2
            'max_ask': random.uniform(50.0, 99.0),
            'min_ev_over': random.uniform(5.0, 50.0),
            'min_ev_under': random.uniform(5.0, 50.0),
            'max_game_bankroll_pct': random.uniform(0.02, 0.99), # 2% to 10%
            'max_bets_over': random.randint(1, 4),
            'max_bets_under': random.randint(1, 4)
        }
        configs.append(c)
    return configs

class PrecalculatedPredictor(AbstractPredictor):
    def __init__(self):
        self.data = {}
        
    def setup(self):
        print("Loading precalculated tracked data...")
        for file_path in TRACKING_DIR.glob('full_ev_analysis_*.json'):
            date = file_path.stem.split('_')[-1]
            if date not in self.data:
                self.data[date] = {}
            with open(file_path, 'r') as f:
                props = json.load(f)
                for p in props:
                    key = (p['player'], p['stat'], float(p['threshold']))
                    self.data[date][key] = p
                    
    def predict_point_estimate(self, player_id: str, stat: str, date: str) -> float:
        if date in self.data:
            for key, p in self.data[date].items():
                if key[0] == player_id and key[1] == stat:
                    return p.get('mc_mean', p.get('model_prediction', None))
        return None
        
    def predict_conformal_probability(self, player_id: str, stat: str, threshold: float, date: str) -> dict:
        key = (player_id, stat, float(threshold))
        if date in self.data and key in self.data[date]:
            res = self.data[date][key]
            if 'conf_p_over' in res and 'conf_p_under' in res:
                if abs(res['threshold'] - threshold) < 0.1:
                    return {'p_over': res['conf_p_over'], 'p_under': res['conf_p_under']}
        return None

if __name__ == '__main__':
    predictor = PrecalculatedPredictor()
    print("Extracting all historical opportunities...")
    ops_df = extract_opportunities(predictor)
    
    if ops_df.empty:
        print("No opportunities extracted. Exiting.")
        sys.exit(0)
        
    # First, run the exact same baseline logic as the original script for comparison
    print("\n" + "="*50)
    print("RUNNING BASELINE STRATEGY (No Kelly, No Limits, Flat 100 Cent Size)")
    print("="*50)
    
    baseline_config = {
        'config_id': -1,
        'initial_bankroll': 0.0,
        'min_ev_over': 0.0, 'min_ev_under': 0.0,
        'max_ask': 99.0, 'is_baseline': True
    }
    baseline_bets, baseline_summary = run_simulation(ops_df, baseline_config, strategy='conformal')
    
    print(f"[BASELINE] PnL: {baseline_summary['total_profit']:+.0f}¢ | ROI: {baseline_summary['roi']*100:.2f}% | Win Rate: {baseline_summary['win_rate']*100:.1f}%")
    print(f"[BASELINE] Total Bets Placed: {baseline_summary['total_bets']}")
    
    NUM_SAMPLES = 50
    print(f"\nGenerating {NUM_SAMPLES} random configurations for optimization...")
    configs = generate_random_configs(NUM_SAMPLES)
    
    all_bets_list = [baseline_bets]
    all_summaries = [baseline_summary]
    
    for config in tqdm(configs, desc="Testing Configs"):
        bets_df, summary = run_simulation(ops_df, config, strategy='conformal') 
        if not bets_df.empty:
            bets_df['config_id'] = config['config_id']
            all_bets_list.append(bets_df)
            
        all_summaries.append(summary)
        
    df_summaries = pd.DataFrame(all_summaries)
    
    print("\n" + "="*50)
    print("BACKTEST OPTIMIZATION RESULTS (Top 5 by Sharpe)")
    print("="*50)
    
    # Filter out baseline for top 5 comparison if desired, but good to include
    top_5 = df_summaries[df_summaries['is_baseline'] != True].sort_values(by='sharpe', ascending=False).head(5)
    for idx, row in top_5.iterrows():
        print(f"[{row['config_id']:>2}] Sharpe: {row['sharpe']:.2f} | PnL: {row['total_profit']:+.0f}¢ | ROI: {row['roi']*100:.2f}% | Win Rate: {row['win_rate']*100:.1f}%")
        print(f"      Kelly Frac: {row['kelly_frac']:.3f} | Max Game %: {row['max_game_bankroll_pct']*100:.1f} | Min EV (O/U): {row['min_ev_over']:.1f}/{row['min_ev_under']:.1f}")
        print(f"      Max Bets (O/U): {row['max_bets_over']}/{row['max_bets_under']} | Max Ask: {row['max_ask']:.1f}")
        print("-" * 50)
        
    if all_bets_list:
        df_all_bets = pd.concat(all_bets_list, ignore_index=True)
        bets_file = BACKTEST_DIR / "backtest_all_bets.parquet"
        df_all_bets.to_parquet(bets_file, index=False)
        print(f"\n[Export] Saved ALL granular bets to: {bets_file.name}")
        
    summaries_file = BACKTEST_DIR / "backtest_config_summaries.parquet"
    df_summaries.to_parquet(summaries_file, index=False)
    print(f"[Export] Saved all config summaries to: {summaries_file.name}")
