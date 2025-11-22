import React from 'react';
import { Link } from 'react-router-dom';

export default function PlayerCard({ player, rank }) {
    return (
        <Link to={`/player/${player.player_id}`} className="player-card">
            <div className="rank">#{rank}</div>
            <div className="player-info">
                <h3 className="player-name">{player.player_name}</h3>
                <p className="player-details">{player.position} • {player.team}</p>
            </div>
            <div className="score-container">
                <div className="score-label">Composite Score</div>
                <div className="score-value">{(player.composite_score * 100).toFixed(1)}</div>
            </div>
            <div className="matchup">
                vs {player.opponent}
            </div>

            <style>{`
        .player-card {
          display: flex;
          align-items: center;
          background: white;
          border: 1px solid var(--color-border);
          border-radius: 12px;
          padding: 16px;
          gap: 16px;
          transition: transform 0.2s, box-shadow 0.2s;
          text-decoration: none;
          color: inherit;
        }
        .player-card:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow-md);
          border-color: var(--color-primary);
        }
        .rank {
          font-size: 1.5rem;
          font-weight: 800;
          color: var(--color-text-secondary);
          opacity: 0.5;
          width: 40px;
          text-align: center;
        }
        .player-info {
          flex: 1;
        }
        .player-name {
          font-size: 1.125rem;
          font-weight: 700;
          color: var(--color-text-main);
          margin: 0;
        }
        .player-details {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
          margin: 4px 0 0 0;
        }
        .score-container {
          text-align: right;
          padding: 0 16px;
          border-left: 1px solid var(--color-border);
          border-right: 1px solid var(--color-border);
        }
        .score-label {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
        }
        .score-value {
          font-size: 1.5rem;
          font-weight: 800;
          color: var(--color-primary);
        }
        .matchup {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
          font-weight: 500;
          width: 100px;
          text-align: right;
        }
      `}</style>
        </Link>
    );
}
