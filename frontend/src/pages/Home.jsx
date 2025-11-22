import React, { useEffect, useState } from 'react';
import { fetchStats } from '../lib/data';
import PlayerCard from '../components/PlayerCard';

export default function Home() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadData() {
            const stats = await fetchStats();
            setData(stats);
            setLoading(false);
        }
        loadData();
    }, []);

    if (loading) {
        return (
            <div className="container" style={{ paddingTop: '40px', textAlign: 'center' }}>
                Loading stats...
            </div>
        );
    }

    if (!data) {
        return (
            <div className="container" style={{ paddingTop: '40px', textAlign: 'center', color: 'red' }}>
                Failed to load data. Please try again.
            </div>
        );
    }

    // Group players by position
    const positions = ['QB', 'WR', 'RB', 'TE', 'K', 'DST'];
    const playersByPosition = positions.reduce((acc, pos) => {
        acc[pos] = data.current_week
            .filter(p => p.position === pos)
            .sort((a, b) => b.composite_score - a.composite_score);
        return acc;
    }, {});

    return (
        <div className="container home-page">
            <header className="page-header">
                <h1>Top Performers of the Week</h1>
                <p className="subtitle">Week {data.current_week[0]?.week} • Ranked by Composite Percentile Score</p>
            </header>

            <div className="position-columns">
                {positions.map(pos => (
                    <div key={pos} className="position-column">
                        <h2 className="position-title">{pos}</h2>
                        <div className="players-list">
                            {playersByPosition[pos].map((player, index) => (
                                <PlayerCard key={player.player_id} player={player} rank={index + 1} />
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <style>{`
        .home-page {
          padding-top: 20px;
          padding-bottom: 40px;
        }
        .page-header {
          margin-bottom: 32px;
          text-align: center;
        }
        .page-header h1 {
          font-size: 2.5rem;
          font-weight: 800;
          color: var(--color-text-main);
          margin-bottom: 8px;
          letter-spacing: -1px;
        }
        .subtitle {
          color: var(--color-text-secondary);
          font-size: 1.125rem;
        }
        .position-columns {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 24px;
        }
        .position-column {
          background: #f8fafc;
          border-radius: 12px;
          padding: 16px;
          border: 1px solid var(--color-border);
        }
        .position-title {
          font-size: 1.5rem;
          font-weight: 800;
          color: var(--color-text-main);
          margin-bottom: 16px;
          padding-bottom: 8px;
          border-bottom: 2px solid var(--color-primary);
          display: inline-block;
        }
        .players-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
      `}</style>
        </div>
    );
}
