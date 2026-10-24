"""Frozen direct ROS forest settings, matching the research F0 model."""

POSITIONS = ("QB", "RB", "WR", "TE")
CUTOFF_WEEKS = (0, 4, 8, 12)
FOREST_PARAMS = {
    "n_estimators": 200,
    "min_samples_leaf": 20,
    "max_features": 0.7,
    "max_samples": 0.8,
    "random_state": 0,
    "n_jobs": -1,
}
