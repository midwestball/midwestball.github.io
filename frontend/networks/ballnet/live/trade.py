import os
import sys
import time
import argparse
import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

import requests

from kalshi_executor import KalshiExecutor, DryRunExecutor
from predictors import LiveGATv2Predictor

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# Prop mapping aligns Kalshi tickers with model features
KALSHI_SERIES = {
    'KXNBAPTS': 'PTS',
    'KXNBAAST': 'AST',
    'KXNBAREB': 'REB',
    'KXNBABLK': 'BLK',
    'KXNBASTL': 'STL',
    'KXNBATO': 'TO'
}

def clean_name(name: str) -> str:
    """Standardizes player names for dictionary matching."""
    return ''.join(c.lower() for c in name if c.isalpha())

class AlertManager:
    """Manages console alerts to prevent spam"""
    def __init__(self, cooldown: int):
        self.cooldown = cooldown
        self.history = {}
        
    def alert(self, msg: str, ticker: str):
        now = time.time()
        if ticker in self.history and (now - self.history[ticker]) < self.cooldown:
            return
        self.history[ticker] = now
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

class LiveOrchestrator:
    """
    Automated NBA player props live trading orchestrator.
    Polls pre-game Kalshi odds, calculates EV using the GATv2 model,
    and executes +EV trades via the TradeExecutor interface.
    """
    
    def __init__(self, predictor: LiveGATv2Predictor, executor, config: Dict[str, Any]):
        self.predictor = predictor
        self.executor = executor
        self.config = config
        
        # Hyperparameters perfectly mirroring the notebook (MIN_TRUE_EV = 2.0¢)
        self.min_ev = config.get('min_ev', 0.02) 
        self.min_edge = config.get('min_edge', 0.03)
        self.kelly_fraction = config.get('kelly_fraction', 0.25)
        self.max_bet_size = config.get('max_bet_size', 50) # dollars
        
        self.alerter = AlertManager(config.get('cooldown_seconds', 300))
        
        # Prepare name normalization index
        self.name2idx = {}
        # In a generic pipeline, we'd need player_ids to names map. We don't have the raw names in the predictor natively.
        # However, the user relies on exact matching in earlier scripts. 
        # We will build a dummy map here or expect it passed in later.
        # As a fallback, we extract names from a hardcoded mapping or try to guess.
        # Actually, let's just use the tracker!
        self.load_player_names()
        
        # Track logged predictions to avoid spamming the CSV with unchanged data
        self.logged_predictions = {}
        
    def load_player_names(self):
        """Loads the player ID to Name mapping from the raw dataset, handling exact Kalshi string matching."""
        import pandas as pd
        from pathlib import Path
        data_dir = self.predictor.data_dir
        path = data_dir / 'raw_boxscores.parquet'
        if path.exists():
            df = pd.read_parquet(path)
            # Take the most recent mapping
            p2n = df.drop_duplicates('PLAYER_ID', keep='last').set_index('PLAYER_ID')['PLAYER_NAME'].to_dict()
            for pid, name in p2n.items():
                if pid in self.predictor.player_ids:
                    idx = self.predictor.player_ids.index(pid)
                    self.name2idx[clean_name(name)] = idx
        else:
            print("WARNING: raw_boxscores.parquet not found. Matchmaking will fail.")

    def log_trade(self, trade_data: Dict[str, Any]):
        """Logs a placed trade to CSV for tracking."""
        import csv
        from pathlib import Path
        log_dir = Path(__file__).resolve().parent / 'live_logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"trades_{datetime.date.today().isoformat()}.csv"
        
        file_exists = log_file.exists()
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=trade_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(trade_data)

    def log_prediction(self, pred_data: Dict[str, Any]):
        """Logs a prediction and market state to CSV for backtesting analysis."""
        import csv
        from pathlib import Path
        log_dir = Path(__file__).resolve().parent
        log_file = log_dir / "predictions.csv"
        
        file_exists = log_file.exists()
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=pred_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(pred_data)

    def fetch_pregame_markets(self) -> List[Dict[str, Any]]:
        """
        Fetches all OPEN player prop markets from Kalshi for games that have NOT yet started.
        """
        open_markets = []
        for series_ticker, stat_col in KALSHI_SERIES.items():
            try:
                r = requests.get(f'{KALSHI_BASE}/events', params={'series_ticker': series_ticker, 'status': 'open', 'limit': 200})
                events = r.json().get('events', [])
                
                for ev in events:
                    mr = requests.get(f'{KALSHI_BASE}/markets', params={'event_ticker': ev['event_ticker'], 'limit': 200})
                    markets = mr.json().get('markets', [])
                    
                    for m in markets:
                        if m.get('status') != 'active' or m.get('in_play', False):
                            continue
                            
                        title = m.get('title', '')
                        if ':' not in title:
                            continue
                            
                        player_name = title.split(':')[0].strip()
                        line = m.get('floor_strike', 0)
                        
                        open_markets.append({
                            'ticker': m['ticker'],
                            'event_ticker': ev['event_ticker'],
                            'player_name': player_name,
                            'stat': stat_col,
                            'threshold': float(line) + 0.5,
                            'yes_ask': m.get('yes_ask'),
                            'no_ask': m.get('no_ask'),
                            'game_title': ev.get('title', '')
                        })
            except Exception as e:
                pass
                
        return open_markets

    def calculate_kelly_bet(self, ev: float, prob: float, ask_price_cents: int, bankroll: float) -> int:
        """Standard Kelly criterion calculation."""
        if ev <= 0 or ask_price_cents <= 0 or ask_price_cents >= 100:
            return 0
            
        b = (100 - ask_price_cents) / ask_price_cents
        q = 1.0 - prob
        f = (b * prob - q) / b
        
        bet_amount = bankroll * f * self.kelly_fraction
        
        # Convert to number of contracts
        num_contracts = int(bet_amount / (ask_price_cents / 100))
        max_contracts = int(self.max_bet_size / (ask_price_cents / 100))
        return min(max(num_contracts, 1), max_contracts)

    def calculate_ev(self, probs: Dict[str, float], yes_ask: int, no_ask: int) -> Dict[str, Any]:
        """Calculates identical Conformal EV to inference_v2.qmd."""
        p_o = probs['p_over']
        p_u = probs['p_under']
        
        ev_yes = (p_o * (100 - yes_ask) - p_u * yes_ask) / 100 if yes_ask else -999
        ev_no  = (p_u * (100 - no_ask) - p_o * no_ask) / 100 if no_ask else -999
        
        best_ev = 0.0
        side = None
        price = 0
        prob = 0.0
        edge = 0.0
        
        if ev_yes >= ev_no and ev_yes > 0:
            side = 'yes'
            best_ev = ev_yes
            price = yes_ask
            prob = p_o
            implied = yes_ask / 100
            edge = p_o - implied
            
        elif ev_no > ev_yes and ev_no > 0:
            side = 'no'
            best_ev = ev_no
            price = no_ask
            prob = p_u
            implied = no_ask / 100
            edge = p_u - implied
            
        return {
            'side': side,
            'ev': best_ev,
            'price_cents': price,
            'prob': prob,
            'edge': edge,
            'ev_yes': ev_yes,
            'ev_no': ev_no
        }

    def run_poll_iteration(self):
        """Single polling and execution iteration."""
        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Polling Kalshi for active PRE-GAME markets...")
        markets = self.fetch_pregame_markets()
        print(f"Found {len(markets)} open pre-game markets.")
        
        bankroll = self.executor.get_balance()
        if bankroll <= 0:
            print("Bankroll <= $0, nothing to do.")
            return

        # Fetch open orders/positions so we don't double dip the same ticker
        open_positions = self.executor.get_positions()
        existing_tickers = {p['ticker'] for p in open_positions}
        
        analyzed_count = 0
        trade_count = 0
        
        for m in markets:
            ticker = m['ticker']
            if ticker in existing_tickers:
                continue
                
            if not m['yes_ask'] or not m['no_ask']:
                continue
                
            c_name = clean_name(m['player_name'])
            if c_name not in self.name2idx:
                continue
                
            pid_index = self.predictor.player_ids[self.name2idx[c_name]]
            analyzed_count += 1
            
            # 1. Get Distribution Probabilities
            probs = self.predictor.predict_conformal_probability(
                player_id=pid_index, 
                stat=m['stat'], 
                threshold=m['threshold']
            )
            
            # 2. Calculate EV
            ev_calcs = self.calculate_ev(probs, m['yes_ask'], m['no_ask'])
            
            # 2.5 Log prediction if the Kalshi line or odds have changed since last loop
            state_key = (m['yes_ask'], m['no_ask'], m['threshold'])
            if self.logged_predictions.get(ticker) != state_key:
                point_estimate = self.predictor.predict_point_estimate(
                    player_id=pid_index, 
                    stat=m['stat']
                )
                pred_data = {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'ticker': ticker,
                    'player': m['player_name'],
                    'stat': m['stat'],
                    'threshold': m['threshold'],
                    'point_estimate': round(point_estimate, 3),
                    'p_over': round(probs['p_over'], 3),
                    'p_under': round(probs['p_under'], 3),
                    'yes_ask': m['yes_ask'],
                    'no_ask': m['no_ask'],
                    'ev_yes': round(ev_calcs['ev_yes'], 3),
                    'ev_no': round(ev_calcs['ev_no'], 3)
                }
                self.log_prediction(pred_data)
                self.logged_predictions[ticker] = state_key
            
            # 3. Filter minimums (ev is calculated in dollars i.e 0.02 = 2 cents)
            if ev_calcs['side'] is None:
                continue
            if ev_calcs['ev'] < self.min_ev: # 0.02 is 2¢
                continue
            if ev_calcs['edge'] < self.min_edge: # 0.03 is 3%
                continue
                
            # 4. Sizing
            contracts = self.calculate_kelly_bet(
                ev_calcs['ev'], 
                ev_calcs['prob'], 
                ev_calcs['price_cents'], 
                bankroll
            )
            
            if contracts > 0:
                msg = f"🔥 +EV FOUND! {m['player_name']} {ev_calcs['side'].upper()} {m['threshold']} {m['stat']} | EV: ${ev_calcs['ev']:.2f} | Edge: {ev_calcs['edge']:.1%}"
                self.alerter.alert(msg, ticker)
                
                # EXECUTE!
                self.executor.place_order(
                    ticker=ticker,
                    side=ev_calcs['side'],
                    quantity=contracts,
                    limit_price=ev_calcs['price_cents'] / 100.0
                )
                
                # Add to local cache instantly so we don't try again right away
                existing_tickers.add(ticker)
                
                trade_data = {
                    'ticker': ticker,
                    'player': m['player_name'],
                    'stat': m['stat'],
                    'threshold': m['threshold'],
                    'side': ev_calcs['side'],
                    'prob': round(ev_calcs['prob'], 3),
                    'edge': round(ev_calcs['edge'], 3),
                    'ev': round(ev_calcs['ev'], 3),
                    'contracts': contracts,
                    'price': ev_calcs['price_cents'],
                    'timestamp': datetime.datetime.now().isoformat()
                }
                self.log_trade(trade_data)
                
                trade_count += 1
                
        print(f"Analyzed {analyzed_count} valid matches. Placed {trade_count} trades.")


def main():
    parser = argparse.ArgumentParser(description="Kalshi Live Trader for ballnet")
    parser.add_argument('--live', action='store_true', help="Enable REAL money live trading.")
    parser.add_argument('--poll-interval', type=int, default=120, help="Seconds between polls")
    args = parser.parse_args()

    from pathlib import Path
    
    # Paths resolved relative to this script's location
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / 'outputs' / 'data'
    model_dir = base_dir / 'outputs' / 'model'
    tracking_dir = base_dir / 'outputs' / 'tracking'
    
    print("Initializing predictor...")
    predictor = LiveGATv2Predictor(
        data_dir=str(data_dir), 
        model_dir=str(model_dir),
        tracking_dir=str(tracking_dir)
    )
    predictor.setup()

    if args.live:
        print("⚠️  DANGER: LIVE TRADING INITIALIZED ⚠️")
        print("Waiting 5 seconds to abort...")
        time.sleep(5)
        api_key_id = os.getenv('KALSHI_API_KEY_ID')
        private_key = os.getenv('KALSHI_PRIVATE_KEY')
        if not api_key_id or not private_key:
            print("ERROR: Must set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY env vars for live trading.")
            sys.exit(1)
            
        executor = KalshiExecutor()
        if not executor.connect(api_key_id, private_key):
            sys.exit(1)
    else:
        print("🟢 DRY RUN MODE (Paper Trading)")
        executor = DryRunExecutor()
        executor.connect("mock", "mock")

    config = {
        'min_ev': 0.02,         # 2.0 cents EV threshold
        'min_edge': 0.03,       # 3.0% edge over implied prob
        'kelly_fraction': 0.25, # Fractional Kelly parameter
        'max_bet_size': 50,     # $50 max risk per bet
        'cooldown_seconds': 300 # Wait 5 minutes before alerting same prop
    }

    orchestrator = LiveOrchestrator(predictor, executor, config)

    try:
        # Initial run right away
        orchestrator.run_poll_iteration()
        print("\nPress Ctrl+C to exit. Continuous polling started.")
        while True:
            time.sleep(args.poll_interval)
            orchestrator.run_poll_iteration()
            
    except KeyboardInterrupt:
        print("\nStopping orchestrator.")

if __name__ == "__main__":
    main()
