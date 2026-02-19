import React from 'react';
import { BarChart, Bar, XAxis, YAxis, ReferenceLine, ResponsiveContainer, Tooltip, Cell } from 'recharts';

export default function Histogram({ historicalValues, currentValue, percentile, sampleSize, lowerIsBetter = false }) {
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

    // Helper to interpolate color
    const getColor = (value) => {
        // Normalize value between min and max
        let t = (value - min) / (max - min);
        if (max === min) t = 0.5; // Handle single value case

        // Invert t if lower is better
        if (lowerIsBetter) {
            t = 1 - t;
        }

        // Clamp t
        t = Math.max(0, Math.min(1, t));

        // Interpolate: Red (0) -> Yellow (0.5) -> Green (1)
        // Red: #ef4444 (239, 68, 68)
        // Yellow: #eab308 (234, 179, 8)
        // Green: #22c55e (34, 197, 94)

        let r, g, b;

        if (t < 0.5) {
            // Red to Yellow
            const p = t * 2;
            r = Math.round(239 + (234 - 239) * p);
            g = Math.round(68 + (179 - 68) * p);
            b = Math.round(68 + (8 - 68) * p);
        } else {
            // Yellow to Green
            const p = (t - 0.5) * 2;
            r = Math.round(234 + (34 - 234) * p);
            g = Math.round(179 + (197 - 179) * p);
            b = Math.round(8 + (94 - 8) * p);
        }

        return `rgb(${r}, ${g}, ${b})`;
    };

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
                                fill={getColor(entry.binCenter)}
                                stroke={getColor(entry.binCenter)}
                                strokeWidth={0.5}
                                fillOpacity={0.8}
                            />
                        ))}
                    </Bar>
                    <ReferenceLine
                        x={currentValue}
                        stroke="#1e293b"
                        strokeWidth={2.5}
                        strokeDasharray="4 2"
                    />
                </BarChart>
            </ResponsiveContainer>
            <div className="percentile-info">
                <span className="percentile-text">{Math.round(percentile * 100)}th percentile</span>
                <span className="sample-size">n = {sampleSize}</span>
            </div>

            <style>{`
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
        </div>
    );
}
