# Kalshi Walk-Forward Backtesting Framework

This directory contains the framework for walk-forward backtesting of player prop predictions against historical Kalshi market data.

## Purpose
The primary goal is to evaluate different betting strategies—specifically, comparing a **Naive Point-Estimate Strategy** vs. a **Conformal Calibration (Empirical Residuals) Strategy**. This framework allows us to simulate exactly how these strategies would have performed historically by strictly using only information available prior to tip-off for each game.

## Architecture

### `models.py`
Defines the `AbstractPredictor` interface. If you are developing a new, more calibrated model (e.g., using a different architecture, different features, or better uncertainty quantification), you simply need to create a class that inherits from `AbstractPredictor` and implements the required methods:
- `predict(player, stat, game_date, ...)`
- `get_empirical_residuals(stat, date)`

This ensures the backtesting engine can blindly evaluate any model using the same strict rules.

### Building New Predictors
To integrate a new model, implement the `AbstractPredictor` class:

```python
from networks.ballnet.backtesting.models import AbstractPredictor

class AwesomeModelPredictor(AbstractPredictor):
    def predict_point_estimate(self, player, stat, date):
        # ... logic ...
        return 15.5
        
    def predict_conformal_probability(self, player, stat, threshold, date):
        # ... logic ...
        return {'conf_p_over': 0.60, 'conf_p_under': 0.40}
        
    def setup(self):
        # Optional: Load data into memory once
        pass
```

> [!CAUTION]
> **Dictionary Key Collisions in Tracking**
> When building predictors that rely on loading outputs from JSON dictionaries (like `PrecalculatedPredictor`), you MUST include the `threshold` in the dictionary lookup key! 
> *(e.g. `key = (player, stat, threshold)`)*
> Players frequently have multiple tracking lines on Kalshi for the exact same stat on the same day (e.g., *LeBron James: 15+ Points* going against *LeBron James: 20+ Points*). If the threshold is omitted from the key, the lines will overwrite each other and cause missing bets!
### `backtest.py`
The main engine for running the backtest. It performs the following steps iteratively over historical days:
1. **Data Loading:** Efficiently loads historical Kalshi lines (at game start) and actual player results.
2. **Prediction:** Queries the model for its point-estimate and conformal probability for a given prop.
3. **Edge Calculation:** Computes the Naive Edge and Conformal Edge.
4. **Bet Simulation:** Simulates placing bets based on defined thresholds (e.g., EV > 0 or EV > 2%).
5. **Grading & Evaluation:** Grades the simulated bets against the true box-score outcomes to calculate metrics like Return on Investment (ROI), Win Rate, and Total Profit & Loss (PnL).

## Usage
To evaluate the current GATv2TCN model on the historical JSON tracking dumps, run:
```bash
uv run python networks/ballnet/backtesting/backtest.py
```

## Key Concepts & Learnings
As agents iterate on this pipeline, keep the following statistical principles in mind:

### 1. The Market "Vig" Exceeds Point-Estimate Confidence
A common fallacy is assuming: *"If the line is 15.5 Points, and my model predicts exactly 15.0 Points, I should take the Under."* 
This logic fails because of Kalshi's spread (or "vig"). The `Yes` and `No` share prices combined frequently total *more* than 100¢ (e.g., Yes=50¢, No=55¢). 
Even if a model computes a 59% chance of the player hitting the Under, if the market's 'No' side costs 60¢, the Expected Value (EV) is negative. The backtester mathematically enforces `EV > 0.0` to filter out these traps, verifying that we only bet when our confidence strictly exceeds the market's implied price.

### 2. Conformal Calibration Outperforms Naive Estimates
Over the 900+ logged props from January and February 2026, the **Conformal Calibration Strategy** drastically outperformed the standard **Naive Estimation Strategy** (which simply used a static standard normal distribution over the RMSE):
- **Naive ROI:** +171.70%
- **Conformal ROI:** +198.73%

By utilizing empirical residual distributions, the model successfully avoids placing overconfident naive bets, identifying cheaper and safer edges in the market.

### 3. Preventing Look-Ahead Data Leakage
When debugging or modifying the backtester, it is critical that future test data does not contaminate the simulation:
1. **Kalshi Market Odds:** Do not fetch 'finalized' odds from the main `/markets` endpoint. The model must simulate executions using actual pre-game odds prior to tip-off (3-4 hours before the `expected_expiration_time` via the Kalshi `/candlesticks` API with an offset). Utilizing final closing odds introduces massive look-ahead bias as prices always collapse to either 0¢ or 100¢.
2. **Conformal Calibration:** The `conformal_residuals.pkl` file determines confidence intervals. It must only be calculated from empirical errors observed purely on chronological validation data (e.g. `X_va`), never test data (`X_te`), to maintain strict out-of-sample guarantees.
3. **Normalization Leakage:** Global Z-scoring parameters `mu_per_day` and `sd_per_day` must operate causally. In this pipeline, these metrics scale backward locally but lock completely after October 2023. You must ensure any new data pipelines updating these parameters do not peek into the future to normalize the past.
