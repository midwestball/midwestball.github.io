import re

with open('networks/ballnet/inference_v2.qmd', 'r') as f:
    text = f.read()

# Replace Phase 15 saving logic
p15_find = """        # Save to file
        sheet_path = TRACKING_DIR / f'conf_bet_sheet_{today_str}.json'
        filtered.to_json(sheet_path, orient='records', indent=2)
        print(f'\\n  Saved → {sheet_path}')"""

p15_repl = """        # Save to file
        sheet_path = TRACKING_DIR / f'conf_bet_sheet_{today_str}.json'
        filtered.to_json(sheet_path, orient='records', indent=2)
        print(f'\\n  Saved → {sheet_path}')

        # Save FULL augmented EV analysis with naive + conformal
        full_analysis_path = TRACKING_DIR / f'full_ev_analysis_{today_str}.json'
        df_conf.to_json(full_analysis_path, orient='records', indent=2)
        print(f'  Saved full analysis (Naive+Conformal) → {full_analysis_path}')"""

text = text.replace(p15_find, p15_repl)

# Replace Phase 11
p11_find = """## 11 · Post-Game: Grade Results & Append to Tracking Log"""
p11_end = """## 12 · Lifetime Tracking Dashboard"""

new_p11 = """## 11 · Post-Game: Grade EV Strategies

**Run this cell after all games have finished.**
We grade the expected value strategies by evaluating the true ROI% for both naive EV and conformal EV independently.

```{python}
log_path = TRACKING_DIR / 'results_log.jsonl'

# Load existing graded tickers
existing_tickers = set()
if log_path.exists():
    with open(log_path) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                existing_tickers.add(entry.get('kalshi_ticker', ''))

today = date.today()
recent_dates = [(today - timedelta(days=i)).isoformat() for i in range(5)]
pending_preds = []

# Load full EV analysis files
for d in recent_dates:
    full_path = TRACKING_DIR / f'full_ev_analysis_{d}.json'
    if full_path.exists():
        with open(full_path) as f:
            preds = json.load(f)
            for p in preds:
                if 'kalshi_ticker' in p and p['kalshi_ticker'] not in existing_tickers:
                    pending_preds.append(p)

unique_pending = {p['kalshi_ticker']: p for p in pending_preds}
pending_preds = list(unique_pending.values())

if not pending_preds:
    print('No pending predictions to grade from the last 5 days.')
else:
    print(f'Checking {len(pending_preds)} pending predictions for Kalshi settlement…')
    
    graded = []
    wins, losses, still_pending = 0, 0, 0
    
    for pred in pending_preds:
        ticker = pred['kalshi_ticker']
        try:
            r = requests.get(f'{KALSHI_BASE}/markets/{ticker}')
            if r.status_code == 200:
                m = r.json().get('market', {})
                result = m.get('result', '')  # 'yes', 'no', or ''
                if result in ('yes', 'no'):
                    actual_over = (result == 'yes')
                    pred['kalshi_result'] = result
                    pred['actual_result'] = 'over' if actual_over else 'under'

                    # Grade Naive EV Pick
                    naive_action = pred.get('best_action', 'NO EDGE')
                    pred['naive_bet_made'] = ('YES' in naive_action or 'NO' in naive_action) and pred.get('best_ev', 0) >= MIN_TRUE_EV
                    if pred['naive_bet_made']:
                        if 'YES' in naive_action:
                            pred['naive_cost'] = pred.get('yes_ask', 0)
                            pred['naive_won'] = actual_over
                        else:
                            pred['naive_cost'] = pred.get('no_ask', 0)
                            pred['naive_won'] = not actual_over
                        pred['naive_return'] = 100 if pred['naive_won'] else 0
                        pred['naive_profit'] = pred['naive_return'] - pred['naive_cost']

                    # Grade Conformal EV Pick
                    conf_action = pred.get('conf_action', 'NO EDGE')
                    pred['conf_bet_made'] = ('YES' in conf_action or 'NO' in conf_action) and pred.get('conf_best_ev', 0) >= MIN_TRUE_EV
                    if pred['conf_bet_made']:
                        if 'YES' in conf_action:
                            pred['conf_cost'] = pred.get('yes_ask', 0)
                            pred['conf_won'] = actual_over
                        else:
                            pred['conf_cost'] = pred.get('no_ask', 0)
                            pred['conf_won'] = not actual_over
                        pred['conf_return'] = 100 if pred['conf_won'] else 0
                        pred['conf_profit'] = pred['conf_return'] - pred['conf_cost']
                        
                else:
                    pred['kalshi_result'] = 'pending'
                    still_pending += 1
            else:
                pred['kalshi_result'] = f'error_{r.status_code}'
                still_pending += 1
        except Exception as e:
            pred['kalshi_result'] = f'error: {e}'
            still_pending += 1
            
        graded.append(pred)
    
    new_entries = 0
    with open(log_path, 'a') as f:
        for g in graded:
            if g.get('kalshi_result') in ('yes', 'no'):
                f.write(json.dumps(g) + '\\n')
                existing_tickers.add(g['kalshi_ticker'])
                new_entries += 1
    
    print(f'\\n── Grading Results ──')
    print(f'  Newly Graded:  {new_entries}')
    print(f'  Still Pending: {still_pending}')
    if still_pending > 0:
        print('\\n⚠ Games may not have finished yet. Re-run this cell later to grade UNDER markets.')

```

"""

text = re.sub(r'## 11 · Post-Game: Grade Results.*?## 12 · Lifetime Tracking Dashboard', new_p11 + '## 12 · Lifetime Tracking Dashboard', text, flags=re.DOTALL)

# Replace Phase 16
p16_find = """## 16 · Conformal Bet Tracking Dashboard"""
p16_end = """## ✅ All Done!"""

new_p16 = """## 16 · EV Strategy ROI Comparison

Compare the win rate and actual ROI% between the Naive EV strategy and the Conformal EV strategy.

```{python}
import pandas as pd
import json

log_path = TRACKING_DIR / 'results_log.jsonl'

if not log_path.exists():
    print('Missing results log. Run the pipeline for a few days first.')
else:
    results = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    df_results = pd.DataFrame(results)
    
    if len(df_results) == 0:
        print('Not enough data to compare yet.')
    else:
        # Naive Strategy Stats
        naive_bets = df_results[df_results['naive_bet_made'] == True]
        if len(naive_bets) > 0:
            naive_wins = naive_bets['naive_won'].sum()
            naive_total = len(naive_bets)
            naive_winrate = naive_wins / naive_total
            naive_cost = naive_bets['naive_cost'].sum()
            naive_profit = naive_bets['naive_profit'].sum()
            naive_roi = naive_profit / naive_cost if naive_cost > 0 else 0
        else:
            naive_wins, naive_total, naive_winrate, naive_cost, naive_profit, naive_roi = 0, 0, 0.0, 0, 0, 0.0
            
        # Conformal Strategy Stats
        conf_bets = df_results[df_results['conf_bet_made'] == True]
        if len(conf_bets) > 0:
            conf_wins = conf_bets['conf_won'].sum()
            conf_total = len(conf_bets)
            conf_winrate = conf_wins / conf_total
            conf_cost = conf_bets['conf_cost'].sum()
            conf_profit = conf_bets['conf_profit'].sum()
            conf_roi = conf_profit / conf_cost if conf_cost > 0 else 0
        else:
            conf_wins, conf_total, conf_winrate, conf_cost, conf_profit, conf_roi = 0, 0, 0.0, 0, 0, 0.0
            
        print(f'── EV Strategy Comparison Dashboard ──\\n')
        
        print(f'【 NAIVE EV STRATEGY 】')
        print(f'Total Bets:  {naive_total}')
        print(f'Win Rate:    {naive_wins}/{naive_total} ({naive_winrate*100:.1f}%)')
        print(f'Total Spend: {naive_cost:.0f}¢')
        print(f'Total PnL:   {naive_profit:+.0f}¢')
        print(f'Actual ROI:  {naive_roi*100:+.1f}%\\n')
        
        print(f'【 CONFORMAL EV STRATEGY 】')
        print(f'Total Bets:  {conf_total}')
        print(f'Win Rate:    {conf_wins}/{conf_total} ({conf_winrate*100:.1f}%)')
        print(f'Total Spend: {conf_cost:.0f}¢')
        print(f'Total PnL:   {conf_profit:+.0f}¢')
        print(f'Actual ROI:  {conf_roi*100:+.1f}%\\n')

```

"""
text = re.sub(r'## 16 · Conformal Bet Tracking Dashboard.*?## ✅ All Done!', new_p16 + '## ✅ All Done!', text, flags=re.DOTALL)

with open('networks/ballnet/inference_v2.qmd', 'w') as f:
    f.write(text)
