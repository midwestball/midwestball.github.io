import React from 'react';
import Histogram from './Histogram';
import { formatStatName } from '../lib/data';

export default function PerformanceTable({ stats }) {
  return (
    <div className="performance-table-container">
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
          {stats.map(stat => (
            <tr key={stat.stat_name}>
              <td className="stat-name">{formatStatName(stat.stat_name)}</td>
              <td className="stat-value">{stat.display_value || stat.value}</td>
              <td>
                <Histogram
                  historicalValues={stat.personal_history}
                  currentValue={stat.value}
                  percentile={stat.personal_percentile}
                  sampleSize={stat.personal_history?.length || 0}
                  color="#3b82f6"
                  lowerIsBetter={stat.lower_is_better}
                />
              </td>
              <td>
                <Histogram
                  historicalValues={stat.positional_history}
                  currentValue={stat.value}
                  percentile={stat.positional_percentile}
                  sampleSize={stat.positional_history?.length || 0}
                  color="#22c55e"
                  lowerIsBetter={stat.lower_is_better}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <style>{`
        .performance-table-container {
          overflow-x: auto;
        }
        .stats-table {
          width: 100%;
          border-collapse: separate;
          border-spacing: 0;
          background: white;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
          min-width: 800px;
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
          vertical-align: middle;
        }
        .stats-table tbody tr:hover {
          background: #f8fafc;
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
      `}</style>
    </div>
  );
}
