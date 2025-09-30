// App.js - Main React Application for NFL Analytics Platform

import React, { useState, useEffect } from "react";
import "./App.css";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Component for displaying individual performance analysis
const PerformanceCard = ({ performance, onAnalyze }) => {
  const getScoreColor = (score) => {
    if (score >= 90) return "#10B981"; // Green
    if (score >= 75) return "#F59E0B"; // Yellow
    if (score >= 60) return "#EF4444"; // Red
    return "#6B7280"; // Gray
  };

  return (
    <div className="performance-card">
      <div className="card-header">
        <div className="player-info">
          <h3>{performance.player_name}</h3>
          <span className="position-badge">{performance.position}</span>
          <span className="team">{performance.team_name}</span>
        </div>
        <div 
          className="impressiveness-score"
          style={{ color: getScoreColor(performance.impressiveness_score) }}
        >
          {performance.impressiveness_score.toFixed(1)}
        </div>
      </div>
      
      <div className="game-info">
        <span>{performance.game_date}</span>
        <span>vs {performance.opponent}</span>
      </div>
      
      <div className="stats-grid">
        {Object.entries(performance.stats).map(([stat, value]) => (
          <div key={stat} className="stat-item">
            <span className="stat-label">{formatStatName(stat)}</span>
            <span className="stat-value">{value}</span>
          </div>
        ))}
      </div>
      
      <button 
        className="analyze-btn"
        onClick={() => onAnalyze(performance)}
      >
        View Analysis
      </button>
    </div>
  );
};

// Component for detailed mathematical analysis
const AnalysisModal = ({ analysis, onClose }) => {
  if (!analysis) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Performance Analysis</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <div className="analysis-content">
          <div className="score-breakdown">
            <div className="main-score">
              <h3>Impressiveness Score</h3>
              <div className="score-value">
                {analysis.impressiveness_score.toFixed(1)}
              </div>
              <div className="confidence">
                Confidence: {(analysis.confidence_score * 100).toFixed(1)}%
              </div>
            </div>
          </div>
          
          <div className="component-scores">
            <div className="component">
              <h4>Personal Improvement</h4>
              <div className="component-score">
                {analysis.personal_percentile.toFixed(1)}%
              </div>
              <div className="z-scores">
                <h5>Z-Scores vs Personal Baseline:</h5>
                {Object.entries(analysis.personal_z_scores).map(([stat, zscore]) => (
                  <div key={stat} className="z-score-item">
                    <span>{formatStatName(stat)}</span>
                    <span className={zscore >= 0 ? "positive" : "negative"}>
                      {zscore >= 0 ? "+" : ""}{zscore.toFixed(2)}σ
                    </span>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="component">
              <h4>Peer Comparison</h4>
              <div className="component-score">
                {analysis.comparative_percentile.toFixed(1)}%
              </div>
              <div className="rankings">
                <h5>Percentile Rankings vs Peers:</h5>
                {Object.entries(analysis.comparative_rankings).map(([stat, percentile]) => (
                  <div key={stat} className="ranking-item">
                    <span>{formatStatName(stat)}</span>
                    <span>{percentile.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          
          <div className="context-info">
            <h4>Analysis Context</h4>
            <p>{analysis.context}</p>
          </div>
          
          <div className="mathematical-explanation">
            <h4>Mathematical Framework</h4>
            <div className="formula-explanation">
              <p><strong>Personal Component:</strong> Z-scores measure how many standard deviations above/below the player's personal average each statistic was.</p>
              <p><strong>Comparative Component:</strong> Percentile rankings show how the performance compares to other players in the same position during similar timeframes.</p>
              <p><strong>Final Score:</strong> I = 0.6 × Personal + 0.4 × Comparative, weighted by position-specific importance of each statistic.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Component for filtering controls
const FilterControls = ({ filters, onFilterChange }) => {
  return (
    <div className="filter-controls">
      <div className="filter-group">
        <label>Position:</label>
        <select 
          value={filters.position} 
          onChange={(e) => onFilterChange({ ...filters, position: e.target.value })}
        >
          <option value="">All Positions</option>
          <option value="QB">Quarterbacks</option>
          <option value="RB">Running Backs</option>
          <option value="WR">Wide Receivers</option>
          <option value="TE">Tight Ends</option>
        </select>
      </div>
      
      <div className="filter-group">
        <label>Timeframe:</label>
        <select 
          value={filters.timeframe} 
          onChange={(e) => onFilterChange({ ...filters, timeframe: e.target.value })}
        >
          <option value="week">This Week</option>
          <option value="month">This Month</option>
          <option value="season">This Season</option>
        </select>
      </div>
    </div>
  );
};

// Main App Component
const App = () => {
  const [performances, setPerformances] = useState([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    position: "",
    timeframe: "month"
  });

  // Fetch top performances
  useEffect(() => {
    fetchTopPerformances();
  }, [filters]);

  const fetchTopPerformances = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filters.position) params.append("position", filters.position);
      params.append("timeframe", filters.timeframe);
      params.append("limit", "20");
      
      const response = await fetch(`${API_BASE_URL}/top-performances?${params}`);
      if (!response.ok) throw new Error("Failed to fetch performances");
      
      const data = await response.json();
      setPerformances(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (performance) => {
    try {
      // For this demo, we'll simulate the detailed analysis
      // In a real app, you'd make another API call to get the full analysis
      const mockAnalysis = {
        impressiveness_score: performance.impressiveness_score,
        personal_percentile: 78.5,
        comparative_percentile: 85.2,
        confidence_score: 0.82,
        personal_z_scores: {
          passing_yards: 1.85,
          passing_touchdowns: 2.12,
          completions: 0.95,
          attempts: 0.67,
          interceptions: -0.45
        },
        comparative_rankings: {
          passing_yards: 88.3,
          passing_touchdowns: 92.1,
          completions: 76.4,
          attempts: 71.2,
          interceptions: 15.8
        },
        context: `Analysis based on 18 historical games and 67 peer comparisons from ${filters.timeframe} timeframe.`
      };
      
      setSelectedAnalysis(mockAnalysis);
    } catch (err) {
      setError("Failed to load detailed analysis");
    }
  };

  const formatStatName = (statName) => {
    return statName
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>NFL Performance Analytics</h1>
        <p>Mathematical analysis of NFL player performances using dual-component impressiveness scoring</p>
      </header>
      
      <main className="main-content">
        <FilterControls filters={filters} onFilterChange={setFilters} />
        
        {loading && <div className="loading">Loading performances...</div>}
        {error && <div className="error">Error: {error}</div>}
        
        {!loading && !error && (
          <div className="performances-grid">
            {performances.length === 0 ? (
              <div className="no-data">No performances found for the selected filters.</div>
            ) : (
              performances.map((performance, index) => (
                <PerformanceCard
                  key={`${performance.player_id}-${performance.game_date}-${index}`}
                  performance={performance}
                  onAnalyze={handleAnalyze}
                />
              ))
            )}
          </div>
        )}
      </main>
      
      {selectedAnalysis && (
        <AnalysisModal
          analysis={selectedAnalysis}
          onClose={() => setSelectedAnalysis(null)}
        />
      )}
      
      <footer className="app-footer">
        <div className="methodology-info">
          <h3>Mathematical Framework</h3>
          <p>
            Our impressiveness score combines personal improvement (60%) with peer comparison (40%). 
            Personal improvement uses z-score analysis against each player's historical baseline. 
            Peer comparison uses percentile rankings against position-matched players in similar timeframes.
          </p>
        </div>
      </footer>
    </div>
  );
};

// Utility function (moved outside component to avoid re-creation)
const formatStatName = (statName) => {
  return statName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

export default App;