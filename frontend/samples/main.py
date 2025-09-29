# main.py - FastAPI Backend for NFL Analytics Platform

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import sqlite3
import json
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title = "NFL Analytics API", version = "1.0.0")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:3000", "https://your-vercel-app.vercel.app"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

# Database connection management
DATABASE_PATH = "nfl_analytics.db"

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Pydantic models for API requests/responses
class GameStats(BaseModel):
    passing_yards: int = 0
    passing_touchdowns: int = 0
    interceptions: int = 0
    rushing_yards: int = 0
    rushing_touchdowns: int = 0
    completions: int = 0
    attempts: int = 0
    receiving_yards: int = 0
    receiving_touchdowns: int = 0
    receptions: int = 0
    targets: int = 0

class AnalysisRequest(BaseModel):
    player_id: int
    game_id: int
    stats: GameStats

class ImpressivenessResult(BaseModel):
    impressiveness_score: float
    personal_percentile: float
    comparative_percentile: float
    confidence_score: float
    personal_z_scores: Dict[str, float]
    comparative_rankings: Dict[str, float]
    context: str
    historical_rank: Optional[int] = None
    peer_rank: Optional[int] = None

class PlayerPerformance(BaseModel):
    player_id: int
    player_name: str
    position: str
    team_name: str
    game_date: str
    opponent: str
    impressiveness_score: float
    stats: Dict[str, Any]

# Position-specific statistical configurations
POSITION_CONFIGS = {
    "QB": {
        "key_stats": ["passing_yards", "passing_touchdowns", "interceptions", "completions", "attempts"],
        "weights": {
            "passing_touchdowns": 0.35,
            "passing_yards": 0.30,
            "completions": 0.15,
            "attempts": 0.10,
            "interceptions": -0.10
        },
        "comparison_timeframe": 14  # days
    },
    "RB": {
        "key_stats": ["rushing_yards", "rushing_touchdowns", "receiving_yards", "receiving_touchdowns"],
        "weights": {
            "rushing_touchdowns": 0.35,
            "rushing_yards": 0.30,
            "receiving_yards": 0.20,
            "receiving_touchdowns": 0.15
        },
        "comparison_timeframe": 14
    },
    "WR": {
        "key_stats": ["receiving_yards", "receiving_touchdowns", "receptions", "targets"],
        "weights": {
            "receiving_touchdowns": 0.40,
            "receiving_yards": 0.30,
            "receptions": 0.20,
            "targets": 0.10
        },
        "comparison_timeframe": 14
    }
}

class NFLAnalyticsEngine:
    """
    Core analytics engine implementing the mathematical impressiveness framework
    """
    
    def __init__(self):
        self.alpha = 0.6  # Weight for personal vs comparative component
        
    def calculate_personal_z_scores(self, stats: Dict[str, float], 
                                  historical_stats: List[Dict[str, float]], 
                                  position: str) -> Dict[str, float]:
        """
        Calculate z-scores for current performance vs player's historical baseline
        
        For each statistic i:
        z_i = (current_value - historical_mean) / historical_std
        """
        if len(historical_stats) < 3:
            # Insufficient historical data
            return {stat: 0.0 for stat in POSITION_CONFIGS[position]["key_stats"]}
        
        z_scores = {}
        config = POSITION_CONFIGS[position]
        
        for stat in config["key_stats"]:
            historical_values = [game_stats.get(stat, 0) for game_stats in historical_stats]
            
            if len(historical_values) == 0:
                z_scores[stat] = 0.0
                continue
                
            mean_val = np.mean(historical_values)
            std_val = np.std(historical_values)
            
            # Avoid division by zero
            if std_val == 0:
                z_scores[stat] = 0.0
            else:
                current_val = stats.get(stat, 0)
                z_scores[stat] = (current_val - mean_val) / std_val
                
        return z_scores
    
    def calculate_comparative_rankings(self, stats: Dict[str, float],
                                     peer_stats: List[Dict[str, float]],
                                     position: str) -> Dict[str, float]:
        """
        Calculate percentile rankings vs peer performances
        
        For each statistic i:
        percentile_i = rank(current_value) / total_peer_performances
        """
        if len(peer_stats) == 0:
            return {stat: 50.0 for stat in POSITION_CONFIGS[position]["key_stats"]}
        
        rankings = {}
        config = POSITION_CONFIGS[position]
        
        for stat in config["key_stats"]:
            peer_values = [game_stats.get(stat, 0) for game_stats in peer_stats]
            current_val = stats.get(stat, 0)
            
            # Calculate percentile rank
            percentile = stats.percentileofscore(peer_values, current_val, kind = "rank")
            rankings[stat] = percentile
            
        return rankings
    
    def calculate_impressiveness_score(self, personal_z_scores: Dict[str, float],
                                     comparative_rankings: Dict[str, float],
                                     position: str) -> float:
        """
        Combine personal and comparative components into final impressiveness score
        
        I = α * Σ(w_i * Φ(z_i)) + (1-α) * Σ(w_i * r_i)
        where Φ is the standard normal CDF
        """
        config = POSITION_CONFIGS[position]
        weights = config["weights"]
        
        # Personal component: Convert z-scores to percentiles using normal CDF
        personal_component = 0
        weight_sum = 0
        
        for stat, weight in weights.items():
            if stat in personal_z_scores:
                z_score = personal_z_scores[stat]
                percentile = stats.norm.cdf(z_score) * 100
                personal_component += weight * percentile
                weight_sum += abs(weight)
        
        personal_component = personal_component / weight_sum if weight_sum > 0 else 0
        
        # Comparative component: Weighted average of peer rankings
        comparative_component = 0
        weight_sum = 0
        
        for stat, weight in weights.items():
            if stat in comparative_rankings:
                ranking = comparative_rankings[stat]
                comparative_component += weight * ranking
                weight_sum += abs(weight)
        
        comparative_component = comparative_component / weight_sum if weight_sum > 0 else 0
        
        # Combine components
        final_score = self.alpha * personal_component + (1 - self.alpha) * comparative_component
        
        # Clamp to valid range
        return max(0.0, min(100.0, final_score))
    
    def calculate_confidence_score(self, historical_count: int, peer_count: int) -> float:
        """
        Calculate confidence in the analysis based on available data
        """
        # Confidence increases with more historical and peer data
        historical_factor = min(1.0, historical_count / 10.0)  # Saturate at 10 games
        peer_factor = min(1.0, peer_count / 50.0)  # Saturate at 50 peer games
        
        return (historical_factor + peer_factor) / 2.0

def get_player_position(player_id: int) -> str:
    """Get player position from database"""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT position FROM players WHERE id = ?", 
            (player_id,)
        )
        result = cursor.fetchone()
        return result["position"] if result else "QB"

def get_player_historical_stats(player_id: int, before_date: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get player's historical game statistics"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT pgs.stats, g.game_date
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.id
            WHERE pgs.player_id = ? AND g.game_date < ?
            ORDER BY g.game_date DESC
            LIMIT ?
        """, (player_id, before_date, limit))
        
        results = []
        for row in cursor.fetchall():
            stats = json.loads(row["stats"]) if row["stats"] else {}
            results.append(stats)
        
        return results

def get_peer_stats(position: str, game_date: str, timeframe_days: int = 14) -> List[Dict[str, Any]]:
    """Get peer statistics for comparison"""
    start_date = (datetime.strptime(game_date, "%Y-%m-%d") - timedelta(days = timeframe_days)).strftime("%Y-%m-%d")
    end_date = (datetime.strptime(game_date, "%Y-%m-%d") + timedelta(days = timeframe_days)).strftime("%Y-%m-%d")
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT pgs.stats
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.id
            JOIN players p ON pgs.player_id = p.id
            WHERE p.position = ? AND g.game_date BETWEEN ? AND ?
        """, (position, start_date, end_date))
        
        results = []
        for row in cursor.fetchall():
            stats = json.loads(row["stats"]) if row["stats"] else {}
            results.append(stats)
        
        return results

# API Endpoints

@app.post("/analyze", response_model = ImpressivenessResult)
async def analyze_performance(request: AnalysisRequest):
    """
    Analyze a player's performance using the mathematical impressiveness framework
    """
    try:
        engine = NFLAnalyticsEngine()
        
        # Get player position
        position = get_player_position(request.player_id)
        
        # Get game date for temporal context
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT game_date FROM games WHERE id = ?", 
                (request.game_id,)
            )
            game_result = cursor.fetchone()
            if not game_result:
                raise HTTPException(status_code = 404, detail = "Game not found")
            game_date = game_result["game_date"]
        
        # Convert stats to dictionary
        stats_dict = request.stats.dict()
        
        # Get historical and peer data
        historical_stats = get_player_historical_stats(request.player_id, game_date)
        peer_stats = get_peer_stats(position, game_date)
        
        # Calculate components
        personal_z_scores = engine.calculate_personal_z_scores(stats_dict, historical_stats, position)
        comparative_rankings = engine.calculate_comparative_rankings(stats_dict, peer_stats, position)
        
        # Calculate final scores
        impressiveness_score = engine.calculate_impressiveness_score(personal_z_scores, comparative_rankings, position)
        confidence_score = engine.calculate_confidence_score(len(historical_stats), len(peer_stats))
        
        # Calculate percentiles for components
        personal_percentile = np.mean([stats.norm.cdf(z) * 100 for z in personal_z_scores.values()])
        comparative_percentile = np.mean(list(comparative_rankings.values()))
        
        # Generate context description
        context = f"Analysis based on {len(historical_stats)} historical games and {len(peer_stats)} peer comparisons"
        
        # Store analysis results
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO performance_analysis 
                (player_id, game_id, personal_z_scores, personal_percentile, 
                 comparative_rankings, comparative_percentile, impressiveness_score, 
                 confidence_score, performance_context, baseline_games_count, comparison_pool_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.player_id, request.game_id, 
                json.dumps(personal_z_scores), personal_percentile,
                json.dumps(comparative_rankings), comparative_percentile,
                impressiveness_score, confidence_score, context,
                len(historical_stats), len(peer_stats)
            ))
            conn.commit()
        
        return ImpressivenessResult(
            impressiveness_score = impressiveness_score,
            personal_percentile = personal_percentile,
            comparative_percentile = comparative_percentile,
            confidence_score = confidence_score,
            personal_z_scores = personal_z_scores,
            comparative_rankings = comparative_rankings,
            context = context
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code = 500, detail = f"Analysis failed: {str(e)}")

@app.get("/top-performances", response_model = List[PlayerPerformance])
async def get_top_performances(
    position: Optional[str] = None,
    timeframe: str = "month",
    limit: int = 20
):
    """
    Get top performances based on impressiveness scores
    """
    try:
        # Calculate date filter
        if timeframe == "week":
            start_date = (datetime.now() - timedelta(days = 7)).strftime("%Y-%m-%d")
        elif timeframe == "month":
            start_date = (datetime.now() - timedelta(days = 30)).strftime("%Y-%m-%d")
        else:  # season
            start_date = (datetime.now() - timedelta(days = 120)).strftime("%Y-%m-%d")
        
        # Build query
        query = """
            SELECT 
                pa.player_id, pa.impressiveness_score,
                p.name as player_name, p.position,
                t.name as team_name,
                g.game_date,
                pgs.stats,
                CASE 
                    WHEN g.home_team_id = p.team_id THEN away_t.name
                    ELSE home_t.name
                END as opponent
            FROM performance_analysis pa
            JOIN players p ON pa.player_id = p.id
            JOIN teams t ON p.team_id = t.id
            JOIN games g ON pa.game_id = g.id
            JOIN teams home_t ON g.home_team_id = home_t.id
            JOIN teams away_t ON g.away_team_id = away_t.id
            JOIN player_game_stats pgs ON pa.player_id = pgs.player_id AND pa.game_id = pgs.game_id
            WHERE g.game_date >= ? AND pa.confidence_score >= 0.5
        """
        
        params = [start_date]
        
        if position:
            query += " AND p.position = ?"
            params.append(position)
        
        query += " ORDER BY pa.impressiveness_score DESC LIMIT ?"
        params.append(limit)
        
        with get_db_connection() as conn:
            cursor = conn.execute(query, params)
            results = []
            
            for row in cursor.fetchall():
                stats = json.loads(row["stats"]) if row["stats"] else {}
                
                results.append(PlayerPerformance(
                    player_id = row["player_id"],
                    player_name = row["player_name"],
                    position = row["position"],
                    team_name = row["team_name"],
                    game_date = row["game_date"],
                    opponent = row["opponent"],
                    impressiveness_score = row["impressiveness_score"],
                    stats = stats
                ))
            
            return results
            
    except Exception as e:
        logger.error(f"Top performances error: {str(e)}")
        raise HTTPException(status_code = 500, detail = f"Failed to get top performances: {str(e)}")

@app.get("/players")
async def get_players(position: Optional[str] = None):
    """Get list of players, optionally filtered by position"""
    try:
        query = """
            SELECT p.id, p.name, p.position, p.jersey_number, t.name as team_name, t.abbreviation
            FROM players p
            JOIN teams t ON p.team_id = t.id
            WHERE p.active = 1
        """
        
        params = []
        if position:
            query += " AND p.position = ?"
            params.append(position)
        
        query += " ORDER BY p.name"
        
        with get_db_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
    except Exception as e:
        logger.error(f"Get players error: {str(e)}")
        raise HTTPException(status_code = 500, detail = f"Failed to get players: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host = "0.0.0.0", port = 8000)