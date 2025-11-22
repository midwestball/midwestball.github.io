import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchStats } from '../lib/data';
import PerformanceTable from '../components/PerformanceTable';

export default function Player() {
    const { playerId } = useParams();
    const [playerData, setPlayerData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadData() {
            const allData = await fetchStats();
            if (allData) {
                const player = allData.current_week.find(p => p.player_id === playerId);
                setPlayerData(player);
            }
            setLoading(false);
        }
        loadData();
    }, [playerId]);

    if (loading) {
        return (
            <div className="container" style={{ paddingTop: '40px', textAlign: 'center' }}>
                Loading player data...
            </div>
        );
    }

    if (!playerData) {
        return (
            <div className="container" style={{ paddingTop: '40px', textAlign: 'center' }}>
                <h2>Player not found</h2>
                <Link to="/" style={{ color: 'var(--color-primary)', textDecoration: 'underline' }}>
                    Return to Home
                </Link>
            </div>
        );
    }

    return (
        <div className="container player-page">
            <div className="player-header">
                <Link to="/" className="back-link">← Back to Top Performers</Link>
                <h1>{playerData.player_name}</h1>
                <div className="player-meta">
                    <span className="team-pos">{playerData.team} • {playerData.position}</span>
                    <span className="separator">•</span>
                    <span className="opponent">vs {playerData.opponent}</span>
                    <span className="separator">•</span>
                    <span className="week">Week {playerData.week}</span>
                </div>
            </div>

            <PerformanceTable stats={playerData.stats} />

            <style>{`
        .player-page {
          padding-top: 20px;
          padding-bottom: 40px;
        }
        .player-header {
          margin-bottom: 32px;
        }
        .back-link {
          display: inline-block;
          margin-bottom: 16px;
          color: var(--color-text-secondary);
          font-size: 0.875rem;
          font-weight: 500;
        }
        .back-link:hover {
          color: var(--color-primary);
        }
        .player-header h1 {
          font-size: 2.5rem;
          font-weight: 800;
          color: var(--color-text-main);
          margin: 0 0 8px 0;
          letter-spacing: -1px;
        }
        .player-meta {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--color-text-secondary);
          font-size: 1.125rem;
        }
        .separator {
          color: var(--color-border);
        }
        .team-pos {
          font-weight: 600;
          color: var(--color-text-main);
        }
      `}</style>
        </div>
    );
}
