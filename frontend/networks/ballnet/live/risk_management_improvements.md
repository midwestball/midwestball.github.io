# Risk Management Improvements

### 1. Adopt a Strict Fractional Kelly Sizing Model

Since you have a quantifiable edge and calibrated probabilities, the mathematically optimal way to size your bets is the Kelly Criterion. The basic formula for the optimal fraction of your bankroll to wager is:

Where: f* = (p(b + 1) - 1) / b

* f* = Fraction of current bankroll to wager
* p = Probability of a win (your calibrated model output)
* b = The decimal odds minus 1 (the profit on a winning $1 bet)

**The Catch:** Full Kelly is incredibly aggressive and assumes zero uncertainty in your edge. Given your 37.6% win rate and extreme variance, betting full Kelly guarantees massive, stomach-churning drawdowns. I will scale this down to a **Fractional Kelly**, specifically a 1/16 fractional Kelly due to the extreme variance of the model.

### 2. Manage the Covariance of Simultaneous Bets

Looking at your numbers, you placed 917 bets over what looks like roughly a 30-day period (based on your total PnL and average daily PnL). That means you are placing around 30 bets a day.

In sports prediction markets (like NBA games or player props), these events are rarely independent. If you have 10 bets on different NBA overs, and the league as a whole plays at a slower pace that night, you could lose all 10.

* **Cap Market Exposure:** Never risk more than a set percentage of your bankroll on a single game or highly correlated cluster of bets, regardless of what the Kelly formula says. A common cap is 2% to 5% of your total bankroll per cluster.
* **Covariance Adjustments:** If you are running multiple overlapping positions, you essentially need a multivariate Kelly approach, or at minimum, a manual haircut to your bet sizes when you are heavy on one side of a correlated outcome.

### 3. Stress Test with Monte Carlo Simulations

Before scaling up from micro-stakes (it looks like your average bet size was around 12.5¢), you need to know what your worst-case scenario looks like.

* Take your empirical distribution of the 917 trades from the Conformal Calibration backtest.
* Run 10,000 simulated paths of a 30-day betting month by sampling from this distribution with replacement.
* Track the **Maximum Drawdown (MaxDD)** and the **Risk of Ruin** (probability of hitting -100% bankroll) for different fractional Kelly multipliers.

Because your win rate is ~38%, you are relying on larger payouts (implied odds of roughly +200 or greater based on your ROI) to generate profit. This means long losing streaks are a mathematical certainty, not an anomaly. You must size your bankroll so that a 15-bet losing streak does not trigger a margin call or emotional tilt.

### 4. Implement Daily Circuit Breakers

Algorithms can have blind spots (e.g., failing to account for late-breaking injury news or a structural change in the market). Set a hard, automated circuit breaker. If your daily PnL hits  or  (e.g., losing ~3800¢ or 5700¢ in your current scale), the system stops placing bets for the day. This prevents a localized model failure from blowing up the entire account while you investigate.

## Priorities

1. Kelly Criterion (simply do a 1/16 kelly bet size)
2. Circuit Breakers (simply stop betting if PnL hits -$50 for the day)
3. Covariance Adjustments (simply cap at 5% of bankroll per game)
4. Monte Carlo Simulations
