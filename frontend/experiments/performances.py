"""
NFL Performance Impressiveness Framework
Synthesized from original plan and mathematical critique
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import gaussian_kde
from sklearn.covariance import LedoitWolf
from sklearn.linear_model import LogisticRegression, ElasticNetCV
from typing import Dict, List, Tuple, Any, Optional
import warnings


class ImpressivenessFramework:
    """
    Statistically rigorous framework for quantifying NFL performance impressiveness
    """
    
    def __init__(self, min_games_for_empirical: int = 30):
        """
        Initialize framework with configurable thresholds
        
        Args:
            min_games_for_empirical: Minimum games needed for empirical methods
        """
        self.min_games_for_empirical = min_games_for_empirical
        self.weight_models = {}
        self.context_models = {}
        
    # ==========================================
    # CORE CALCULATION
    # ==========================================
    
    def calculate_impressiveness(
        self,
        player_stats: Dict[str, float],
        player_history: pd.DataFrame,
        peer_data: pd.DataFrame,
        context: Dict[str, float],
        position: str
    ) -> Dict[str, Any]:
        """
        Main impressiveness calculation with synthesized improvements
        
        Args:
            player_stats: Current game statistics
            player_history: Player's historical games
            peer_data: Peer comparison data
            context: Game context variables
            position: Player position
            
        Returns:
            Dictionary with score, components, and diagnostics
        """
        # Step 1: Context adjustment
        adjusted_stats = self._adjust_for_context(
            player_stats, context, peer_data, position
        )
        
        # Step 2: Calculate personal component
        personal_percentiles = self._calculate_personal_percentiles(
            adjusted_stats, player_history, peer_data, position
        )
        
        # Step 3: Calculate comparative component  
        comparative_percentiles = self._calculate_comparative_percentiles(
            adjusted_stats, peer_data, position
        )
        
        # Step 4: Get data-driven weights
        weights = self._derive_weights(position, peer_data)
        
        # Step 5: Aggregate components
        personal_score = self._weighted_average(personal_percentiles, weights) * 100
        comparative_score = self._weighted_average(comparative_percentiles, weights) * 100
        
        # Step 6: Experience-based combination
        n_games = len(player_history)
        alpha = self._calculate_alpha(n_games, player_history, peer_data)
        
        impressiveness = alpha * personal_score + (1 - alpha) * comparative_score
        
        # Step 7: Uncertainty quantification
        ci_lower, ci_upper = self._bootstrap_confidence_interval(
            player_stats, player_history, peer_data, context, position
        )
        
        return {
            "impressiveness_score": impressiveness,
            "confidence_interval": (ci_lower, ci_upper),
            "components": {
                "personal": personal_score,
                "comparative": comparative_score,
                "alpha": alpha
            },
            "percentiles": {
                "personal": personal_percentiles,
                "comparative": comparative_percentiles
            },
            "weights": weights,
            "adjusted_stats": adjusted_stats,
            "sample_sizes": {
                "player_games": n_games,
                "peer_games": len(peer_data)
            }
        }
    
    # ==========================================
    # PERCENTILE CALCULATIONS
    # ==========================================
    
    def _calculate_personal_percentiles(
        self,
        stats: Dict[str, float],
        player_history: pd.DataFrame,
        peer_data: pd.DataFrame,
        position: str
    ) -> Dict[str, float]:
        """
        Calculate percentiles relative to player's own history
        Uses adaptive methods based on sample size
        """
        percentiles = {}
        
        for stat_name, value in stats.items():
            historical_values = player_history[stat_name].dropna().values
            n_historical = len(historical_values)
            
            if n_historical >= self.min_games_for_empirical:
                # Sufficient data: use empirical percentile
                percentile = self._empirical_percentile(value, historical_values)
                
            elif n_historical >= 10:
                # Moderate data: use kernel density estimation
                percentile = self._kde_percentile(value, historical_values)
                
            else:
                # Small sample: Bayesian updating with position prior
                position_values = peer_data[peer_data["position"] == position][stat_name].values
                percentile = self._bayesian_percentile(
                    value, historical_values, position_values
                )
            
            percentiles[stat_name] = percentile
            
        return percentiles
    
    def _calculate_comparative_percentiles(
        self,
        stats: Dict[str, float],
        peer_data: pd.DataFrame,
        position: str
    ) -> Dict[str, float]:
        """
        Calculate percentiles relative to position peers
        """
        percentiles = {}
        position_data = peer_data[peer_data["position"] == position]
        
        for stat_name, value in stats.items():
            peer_values = position_data[stat_name].dropna().values
            
            if len(peer_values) >= 100:
                percentile = self._empirical_percentile(value, peer_values)
            else:
                percentile = self._kde_percentile(value, peer_values)
                
            percentiles[stat_name] = percentile
            
        return percentiles
    
    def _empirical_percentile(self, value: float, data: np.ndarray) -> float:
        """Simple empirical CDF evaluation"""
        return np.mean(data <= value)
    
    def _kde_percentile(self, value: float, data: np.ndarray) -> float:
        """Kernel density estimation for small samples"""
        if len(data) < 2:
            return 0.5
            
        kde = gaussian_kde(data, bw_method = "scott")
        # Integrate KDE from -inf to value
        samples = np.random.normal(data.mean(), data.std(), 10000)
        kde_samples = kde.resample(10000).flatten()
        return np.mean(kde_samples <= value)
    
    def _bayesian_percentile(
        self,
        value: float,
        player_data: np.ndarray,
        position_data: np.ndarray
    ) -> float:
        """
        Bayesian percentile with position prior
        Using normal-normal conjugate for simplicity
        """
        # Prior from position
        mu_0 = np.mean(position_data)
        sigma_0_sq = np.var(position_data)
        
        if len(player_data) == 0:
            # No player data, use prior
            return stats.norm.cdf(value, loc = mu_0, scale = np.sqrt(sigma_0_sq))
        
        # Update with player data
        n = len(player_data)
        x_bar = np.mean(player_data)
        s_sq = np.var(player_data) if n > 1 else sigma_0_sq
        
        # Posterior parameters
        sigma_post_sq = 1 / (1/sigma_0_sq + n/s_sq)
        mu_post = sigma_post_sq * (mu_0/sigma_0_sq + n * x_bar/s_sq)
        
        # Posterior predictive
        var_pred = s_sq + sigma_post_sq
        
        return stats.norm.cdf(value, loc = mu_post, scale = np.sqrt(var_pred))
    
    # ==========================================
    # WEIGHT DERIVATION
    # ==========================================
    
    def _derive_weights(
        self,
        position: str,
        historical_data: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Derive statistic weights using game outcome models
        More practical than EPA/WPA which may not be available
        """
        cache_key = f"{position}_{len(historical_data)}"
        if cache_key in self.weight_models:
            return self.weight_models[cache_key]
        
        # Get position-specific data
        position_data = historical_data[historical_data["position"] == position].copy()
        
        # Define statistics for this position
        if position == "QB":
            stat_cols = ["passing_yards", "passing_tds", "interceptions", "completion_pct"]
        elif position == "RB":
            stat_cols = ["rushing_yards", "rushing_tds", "receptions", "receiving_yards"]
        elif position == "WR":
            stat_cols = ["receptions", "receiving_yards", "receiving_tds", "yards_after_catch"]
        else:
            # Default stats
            stat_cols = [col for col in position_data.columns 
                        if col not in ["player_id", "game_id", "position", "win"]]
        
        # Filter to available columns
        stat_cols = [col for col in stat_cols if col in position_data.columns]
        
        if len(stat_cols) == 0 or "win" not in position_data.columns:
            # Equal weights if no outcome data
            return {col: 1.0/len(stat_cols) for col in stat_cols}
        
        # Prepare data
        X = position_data[stat_cols].fillna(0).values
        y = position_data["win"].values
        
        # Standardize features
        X_mean = X.mean(axis = 0)
        X_std = X.std(axis = 0) + 1e-8
        X_scaled = (X - X_mean) / X_std
        
        # Elastic Net logistic regression for feature importance
        try:
            model = LogisticRegression(
                penalty = "l2",
                C = 1.0,
                max_iter = 1000,
                solver = "lbfgs"
            )
            model.fit(X_scaled, y)
            
            # Extract and normalize coefficients
            coefs = np.abs(model.coef_[0])
            
            # Account for scale differences
            scaled_coefs = coefs * X_std
            
            # Normalize to sum to 1
            if scaled_coefs.sum() > 0:
                weights = scaled_coefs / scaled_coefs.sum()
            else:
                weights = np.ones(len(stat_cols)) / len(stat_cols)
                
        except Exception as e:
            warnings.warn(f"Weight derivation failed: {e}")
            weights = np.ones(len(stat_cols)) / len(stat_cols)
        
        weight_dict = dict(zip(stat_cols, weights))
        self.weight_models[cache_key] = weight_dict
        
        return weight_dict
    
    # ==========================================
    # CONTEXT ADJUSTMENT
    # ==========================================
    
    def _adjust_for_context(
        self,
        stats: Dict[str, float],
        context: Dict[str, float],
        peer_data: pd.DataFrame,
        position: str
    ) -> Dict[str, float]:
        """
        Adjust statistics for game context using matching-based approach
        Falls back to regression when matching fails
        """
        adjusted = {}
        
        for stat_name, value in stats.items():
            # Try matching first
            matched_adjustment = self._matching_adjustment(
                stat_name, value, context, peer_data, position
            )
            
            if matched_adjustment is not None:
                adjusted[stat_name] = matched_adjustment
            else:
                # Fall back to regression
                adjusted[stat_name] = self._regression_adjustment(
                    stat_name, value, context, peer_data, position
                )
        
        return adjusted
    
    def _matching_adjustment(
        self,
        stat_name: str,
        value: float,
        context: Dict[str, float],
        peer_data: pd.DataFrame,
        position: str,
        tolerance: float = 0.1
    ) -> Optional[float]:
        """
        Adjust using matched similar games
        """
        position_data = peer_data[peer_data["position"] == position].copy()
        
        if len(position_data) < 20:
            return None
        
        # Find similar context games
        context_cols = list(context.keys())
        if not all(col in position_data.columns for col in context_cols):
            return None
        
        # Calculate context similarity
        context_array = np.array([context[col] for col in context_cols])
        peer_contexts = position_data[context_cols].values
        
        # Normalize contexts
        context_std = peer_contexts.std(axis = 0) + 1e-8
        context_normalized = context_array / context_std
        peer_normalized = peer_contexts / context_std
        
        # Find similar games (within tolerance)
        distances = np.sqrt(((peer_normalized - context_normalized) ** 2).sum(axis = 1))
        similar_mask = distances <= tolerance
        
        if similar_mask.sum() < 5:
            return None
        
        # Calculate adjustment
        similar_games = position_data[similar_mask]
        neutral_games = position_data[distances <= np.percentile(distances, 50)]
        
        context_mean = similar_games[stat_name].mean()
        neutral_mean = neutral_games[stat_name].mean()
        
        if context_mean > 0:
            adjustment_factor = neutral_mean / context_mean
            return value * adjustment_factor
        else:
            adjustment = neutral_mean - context_mean
            return value + adjustment
    
    def _regression_adjustment(
        self,
        stat_name: str,
        value: float,
        context: Dict[str, float],
        peer_data: pd.DataFrame,
        position: str
    ) -> float:
        """
        Regression-based context adjustment
        """
        position_data = peer_data[peer_data["position"] == position].copy()
        
        context_cols = list(context.keys())
        if not all(col in position_data.columns for col in context_cols):
            return value  # No adjustment if context not available
        
        # Build regression model
        X = position_data[context_cols].fillna(0).values
        y = position_data[stat_name].fillna(0).values
        
        if len(X) < 20 or y.std() == 0:
            return value
        
        try:
            # Simple linear regression
            from sklearn.linear_model import Ridge
            model = Ridge(alpha = 1.0)
            model.fit(X, y)
            
            # Predict effect of current context
            context_array = np.array([context[col] for col in context_cols]).reshape(1, -1)
            context_effect = model.predict(context_array)[0]
            
            # Neutral context (median)
            neutral_context = np.median(X, axis = 0).reshape(1, -1)
            neutral_effect = model.predict(neutral_context)[0]
            
            # Adjust
            return value - context_effect + neutral_effect
            
        except Exception:
            return value
    
    # ==========================================
    # EXPERIENCE WEIGHTING
    # ==========================================
    
    def _calculate_alpha(
        self,
        n_games: int,
        player_history: pd.DataFrame,
        peer_data: pd.DataFrame
    ) -> float:
        """
        Calculate experience-based weight using uncertainty principle
        As player has more games, weight personal component more heavily
        """
        if n_games == 0:
            return 0.0
        
        # Use uncertainty-based weighting
        # k represents "equivalent prior games"
        k = 10  # This could be tuned via cross-validation
        
        # Alternative functional forms could be tested:
        # - Exponential: 1 - exp(-lambda * n_games)
        # - Logistic: 1 / (1 + exp(-beta * (n_games - k)))
        
        # Simple and interpretable
        alpha = n_games / (n_games + k)
        
        return alpha
    
    # ==========================================
    # UNCERTAINTY QUANTIFICATION
    # ==========================================
    
    def _bootstrap_confidence_interval(
        self,
        player_stats: Dict[str, float],
        player_history: pd.DataFrame,
        peer_data: pd.DataFrame,
        context: Dict[str, float],
        position: str,
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Nonparametric bootstrap for confidence intervals
        """
        bootstrap_scores = []
        
        for _ in range(n_bootstrap):
            # Resample historical data
            if len(player_history) > 0:
                player_sample = player_history.sample(
                    n = len(player_history),
                    replace = True
                )
            else:
                player_sample = player_history
            
            # Resample peer data
            peer_sample = peer_data.sample(
                n = len(peer_data),
                replace = True
            )
            
            # Recalculate score
            try:
                result = self.calculate_impressiveness(
                    player_stats,
                    player_sample,
                    peer_sample,
                    context,
                    position
                )
                bootstrap_scores.append(result["impressiveness_score"])
            except Exception:
                continue
        
        if len(bootstrap_scores) < 100:
            return (0, 100)  # Default bounds if bootstrap fails
        
        # Calculate percentiles
        alpha = (1 - confidence_level) / 2
        lower = np.percentile(bootstrap_scores, 100 * alpha)
        upper = np.percentile(bootstrap_scores, 100 * (1 - alpha))
        
        return (lower, upper)
    
    def _weighted_average(
        self,
        values: Dict[str, float],
        weights: Dict[str, float]
    ) -> float:
        """
        Compute weighted average handling missing values
        """
        total_weight = 0
        weighted_sum = 0
        
        for key in values:
            if key in weights:
                weighted_sum += values[key] * weights[key]
                total_weight += weights[key]
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return np.mean(list(values.values()))


# ==========================================
# MULTIVARIATE ANALYSIS
# ==========================================

class MultivariateAnalysis:
    """
    Handle correlated statistics properly
    """
    
    @staticmethod
    def compute_mahalanobis_percentile(
        performance: Dict[str, float],
        historical_data: pd.DataFrame,
        stat_names: List[str]
    ) -> float:
        """
        Compute multivariate percentile using Mahalanobis distance
        """
        # Get data matrices
        current = np.array([performance[stat] for stat in stat_names])
        historical = historical_data[stat_names].values
        
        if len(historical) < len(stat_names):
            # Not enough data for multivariate analysis
            return 0.5
        
        # Compute robust covariance
        if len(historical) > 5 * len(stat_names):
            # Sufficient data for sample covariance
            mu = historical.mean(axis = 0)
            cov = np.cov(historical, rowvar = False)
        else:
            # Use shrinkage estimator
            lw = LedoitWolf()
            lw.fit(historical)
            mu = historical.mean(axis = 0)
            cov = lw.covariance_
        
        # Add regularization
        cov_reg = cov + 1e-6 * np.eye(len(mu))
        
        # Compute Mahalanobis distance
        try:
            inv_cov = np.linalg.inv(cov_reg)
            diff = current - mu
            distance_sq = diff @ inv_cov @ diff
            distance = np.sqrt(max(0, distance_sq))
        except np.linalg.LinAlgError:
            # Fallback to Euclidean distance
            diff = current - mu
            distance = np.linalg.norm(diff)
        
        # Compute percentile
        historical_distances = []
        for row in historical:
            diff = row - mu
            try:
                dist_sq = diff @ inv_cov @ diff
                historical_distances.append(np.sqrt(max(0, dist_sq)))
            except:
                historical_distances.append(np.linalg.norm(diff))
        
        percentile = np.mean(np.array(historical_distances) <= distance)
        return percentile


# ==========================================
# VALIDATION FRAMEWORK
# ==========================================

class ValidationFramework:
    """
    Validate the impressiveness framework
    """
    
    @staticmethod
    def temporal_cross_validation(
        data: pd.DataFrame,
        framework: ImpressivenessFramework,
        n_splits: int = 5
    ) -> Dict[str, float]:
        """
        Time-series aware cross-validation
        """
        # Sort by date
        data_sorted = data.sort_values("game_date")
        fold_size = len(data_sorted) // n_splits
        
        scores = []
        
        for i in range(n_splits):
            train_end = (i + 1) * fold_size
            test_start = train_end
            test_end = min(train_end + fold_size, len(data_sorted))
            
            train_data = data_sorted.iloc[:train_end]
            test_data = data_sorted.iloc[test_start:test_end]
            
            # Evaluate on test set
            for _, test_game in test_data.iterrows():
                player_id = test_game["player_id"]
                
                # Get player history from training data
                player_history = train_data[
                    train_data["player_id"] == player_id
                ]
                
                # Get peer data from training
                peer_data = train_data[
                    train_data["position"] == test_game["position"]
                ]
                
                if len(peer_data) < 10:
                    continue
                
                # Calculate impressiveness
                result = framework.calculate_impressiveness(
                    player_stats = test_game[["passing_yards", "passing_tds"]].to_dict(),
                    player_history = player_history,
                    peer_data = peer_data,
                    context = {"temperature": 70, "wind": 5},
                    position = test_game["position"]
                )
                
                scores.append(result["impressiveness_score"])
        
        return {
            "mean_score": np.mean(scores),
            "std_score": np.std(scores),
            "n_evaluated": len(scores)
        }
    
    @staticmethod
    def concordance_index(
        true_rankings: np.ndarray,
        predicted_scores: np.ndarray
    ) -> float:
        """
        Measure ranking agreement
        """
        n = len(true_rankings)
        concordant = 0
        discordant = 0
        
        for i in range(n):
            for j in range(i + 1, n):
                true_diff = true_rankings[i] - true_rankings[j]
                pred_diff = predicted_scores[i] - predicted_scores[j]
                
                if true_diff * pred_diff > 0:
                    concordant += 1
                elif true_diff * pred_diff < 0:
                    discordant += 1
        
        total_pairs = concordant + discordant
        if total_pairs == 0:
            return 0.5
        
        return concordant / total_pairs