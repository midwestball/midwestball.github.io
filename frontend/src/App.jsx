import React from "react";
import { BarChart, Bar, XAxis, YAxis, ReferenceLine, ResponsiveContainer, Tooltip, Cell } from "recharts";

function RechartsBarDistribution({ historicalValues, currentValue, percentile, sampleSize, color = "#3b82f6" }) {
  if (!historicalValues || historicalValues.length < 5) {
    return (
      <div className="insufficient-data">
        Need {5 - (historicalValues?.length || 0)} more games
      </div>
    );
  }
  
  const numBins = 12;
  const min = Math.min(...historicalValues, currentValue);
  const max = Math.max(...historicalValues, currentValue);
  
  const isDiscrete = historicalValues.every(v => Number.isInteger(v)) && (max - min) < 20;
  
  let histData;
  
  if (isDiscrete) {
    const valueCounts = {};
    for (let i = min; i <= max; i++) {
      valueCounts[i] = 0;
    }
    
    historicalValues.forEach(v => {
      if (v >= min && v <= max) {
        valueCounts[v]++;
      }
    });
    
    histData = Object.keys(valueCounts).map(val => {
      const numVal = parseInt(val);
      return {
        binStart: numVal,
        binEnd: numVal,
        binCenter: numVal,
        count: valueCounts[val],
        isBelowCurrent: numVal < currentValue
      };
    });
  } else {
    const padding = (max - min) * 0.1;
    const binWidth = (max - min + 2 * padding) / numBins;
    
    histData = Array.from({ length: numBins }, (_, i) => {
      const binStart = min - padding + i * binWidth;
      const binEnd = binStart + binWidth;
      const count = historicalValues.filter(v => v >= binStart && v < binEnd).length;
      
      return {
        binStart: Math.round(binStart),
        binEnd: Math.round(binEnd),
        binCenter: Math.round(binStart + binWidth / 2),
        count: count,
        isBelowCurrent: binEnd <= currentValue
      };
    });
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const binStart = payload[0].payload.binStart;
      const binEnd = payload[0].payload.binEnd;
      return (
        <div style={{
          backgroundColor: "white",
          padding: "8px 12px",
          border: "1px solid #e2e8f0",
          borderRadius: "6px",
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
        }}>
          <p style={{ margin: 0, fontSize: "12px", fontWeight: 600, color: "#334155" }}>
            {binStart === binEnd ? `Value: ${binStart}` : `Range: ${binStart} - ${binEnd}`}
          </p>
          <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#64748b" }}>
            Count: {payload[0].value}
          </p>
        </div>
      );
    }
    return null;
  };
  
  const maxCount = Math.max(...histData.map(d => d.count));
  
  return (
    <div className="distribution-container">
      <ResponsiveContainer width={220} height={120}>
        <BarChart data={histData} margin={{ top: 8, right: 8, bottom: 25, left: 8 }}>
          <XAxis 
            dataKey="binCenter"
            type="number"
            domain={isDiscrete ? [min - 0.5, max + 0.5] : [min - (max - min) * 0.1, max + (max - min) * 0.1]}
            ticks={isDiscrete && (max - min) <= 10 ? Array.from({ length: max - min + 1 }, (_, i) => min + i) : [Math.round(min), Math.round((min + max) / 2), Math.round(max)]}
            fontSize={9}
            stroke="#64748b"
            tickLine={{ stroke: "#64748b" }}
          />
          <YAxis hide domain={[0, maxCount * 1.1]} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0, 0, 0, 0.05)" }} />
          <Bar dataKey="count" radius={[2, 2, 0, 0]} minPointSize={3}>
            {histData.map((entry, index) => (
              <Cell 
                key={`cell-${index}`}
                fill={entry.isBelowCurrent ? color : "#e2e8f0"}
                stroke={entry.isBelowCurrent ? color : "#cbd5e1"}
                strokeWidth={0.5}
              />
            ))}
          </Bar>
          <ReferenceLine 
            x={currentValue} 
            stroke="#ef4444" 
            strokeWidth={2.5}
            strokeDasharray="4 2"
          />
        </BarChart>
      </ResponsiveContainer>
      <div className="percentile-info">
        <span className="percentile-text">{percentile}th percentile</span>
        <span className="sample-size">n = {sampleSize}</span>
      </div>
    </div>
  );
}

function PerformanceTableRechartsBar({ performance }) {
  return (
    <div className="performance-view">
      <div className="header">
        <h1>{performance.player_name} vs {performance.opponent}</h1>
        <p className="game-info">{performance.game_date} • {performance.position}</p>
      </div>
      
      <table className="stats-table">
        <thead>
          <tr>
            <th className="stat-name-col">Statistic</th>
            <th className="value-col">Value</th>
            <th className="dist-col">Personal Distribution</th>
            <th className="dist-col">Positional Distribution</th>
          </tr>
        </thead>
        <tbody>
          {performance.stats.map(stat => (
            <tr key={stat.stat_name} className={stat.is_notable_personal || stat.is_notable_positional ? "notable-row" : ""}>
              <td className="stat-name">{formatStatName(stat.stat_name)}</td>
              <td className="stat-value">{stat.value}</td>
              <td>
                <RechartsBarDistribution
                  historicalValues={performance.player_history[stat.stat_name]}
                  currentValue={stat.value}
                  percentile={Math.round(stat.personal_percentile * 100)}
                  sampleSize={stat.personal_sample_size}
                  color="#3b82f6"
                />
              </td>
              <td>
                <RechartsBarDistribution
                  historicalValues={performance.peer_data[stat.stat_name]}
                  currentValue={stat.value}
                  percentile={Math.round(stat.positional_percentile * 100)}
                  sampleSize={stat.positional_sample_size}
                  color="#22c55e"
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatStatName(name) {
  return name
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const mockPerformance = {
  player_name: "Patrick Mahomes",
  opponent: "Buffalo Bills",
  game_date: "2024-11-10",
  position: "QB",
  stats: [
    {
      stat_name: "passing_yards",
      value: 450,
      personal_percentile: 0.95,
      personal_sample_size: 89,
      positional_percentile: 0.82,
      positional_sample_size: 1247,
      is_notable_personal: true,
      is_notable_positional: false
    },
    {
      stat_name: "passing_tds",
      value: 4,
      personal_percentile: 0.78,
      personal_sample_size: 89,
      positional_percentile: 0.71,
      positional_sample_size: 1247,
      is_notable_personal: false,
      is_notable_positional: false
    },
    {
      stat_name: "interceptions",
      value: 2,
      personal_percentile: 0.22,
      personal_sample_size: 89,
      positional_percentile: 0.35,
      positional_sample_size: 1247,
      is_notable_personal: false,
      is_notable_positional: false
    }
  ],
  player_history: {
    passing_yards: Array.from({ length: 89 }, () => 250 + Math.random() * 150),
    passing_tds: Array.from({ length: 89 }, () => Math.floor(Math.random() * 5)),
    interceptions: Array.from({ length: 89 }, () => Math.floor(Math.random() * 3))
  },
  peer_data: {
    passing_yards: Array.from({ length: 1247 }, () => 220 + Math.random() * 180),
    passing_tds: Array.from({ length: 1247 }, () => Math.floor(Math.random() * 5)),
    interceptions: Array.from({ length: 1247 }, () => Math.floor(Math.random() * 3))
  }
};

export default function App() {
  return (
    <>
      <style>{`
        .performance-view {
          max-width: 1400px;
          margin: 0 auto;
          padding: 20px;
          font-family: system-ui, -apple-system, sans-serif;
        }
        .header {
          margin-bottom: 30px;
        }
        .header h1 {
          font-size: 28px;
          font-weight: 700;
          color: #1e293b;
          margin: 0 0 8px 0;
        }
        .game-info {
          font-size: 14px;
          color: #64748b;
          margin: 0;
        }
        .stats-table {
          width: 100%;
          border-collapse: separate;
          border-spacing: 0;
          background: white;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .stats-table thead {
          background: #f8fafc;
        }
        .stats-table th {
          padding: 12px 16px;
          text-align: left;
          font-size: 12px;
          font-weight: 600;
          color: #475569;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          border-bottom: 2px solid #e2e8f0;
        }
        .stats-table td {
          padding: 16px;
          border-bottom: 1px solid #f1f5f9;
        }
        .stats-table tbody tr:hover {
          background: #f8fafc;
        }
        .stats-table tbody tr.notable-row {
          background: #fef3c7;
        }
        .stats-table tbody tr.notable-row:hover {
          background: #fde68a;
        }
        .stat-name {
          font-weight: 500;
          color: #334155;
        }
        .stat-value {
          font-size: 20px;
          font-weight: 700;
          color: #0f172a;
          text-align: center;
        }
        .stat-name-col {
          width: 20%;
        }
        .value-col {
          width: 12%;
        }
        .dist-col {
          width: 34%;
        }
        .distribution-container {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .percentile-info {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          color: #64748b;
          padding: 0 4px;
        }
        .percentile-text {
          font-weight: 600;
          color: #475569;
        }
        .sample-size {
          color: #94a3b8;
        }
        .insufficient-data {
          padding: 20px;
          text-align: center;
          color: #94a3b8;
          font-size: 12px;
          font-style: italic;
        }
      `}</style>
      <PerformanceTableRechartsBar performance={mockPerformance} />
    </>
  );
}