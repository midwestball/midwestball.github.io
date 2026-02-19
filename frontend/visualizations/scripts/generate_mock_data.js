
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const POSITIONS = ['QB', 'WR', 'RB', 'TE', 'K', 'DST'];
const TEAMS = ['KC', 'BUF', 'PHI', 'SF', 'BAL', 'CIN', 'MIA', 'DET', 'DAL', 'NYJ'];

const PLAYERS = [
    { id: 'p1', name: 'Patrick Mahomes', position: 'QB', team: 'KC' },
    { id: 'p2', name: 'Josh Allen', position: 'QB', team: 'BUF' },
    { id: 'p3', name: 'Jalen Hurts', position: 'QB', team: 'PHI' },
    { id: 'p4', name: 'Tyreek Hill', position: 'WR', team: 'MIA' },
    { id: 'p5', name: 'Justin Jefferson', position: 'WR', team: 'MIN' },
    { id: 'p6', name: 'Christian McCaffrey', position: 'RB', team: 'SF' },
    { id: 'p7', name: 'Travis Kelce', position: 'TE', team: 'KC' },
    { id: 'p8', name: 'Lamar Jackson', position: 'QB', team: 'BAL' },
    { id: 'p9', name: 'Joe Burrow', position: 'QB', team: 'CIN' },
    { id: 'p10', name: 'CeeDee Lamb', position: 'WR', team: 'DAL' },
    { id: 'p11', name: 'Justin Tucker', position: 'K', team: 'BAL' },
    { id: 'p12', name: 'Harrison Butker', position: 'K', team: 'KC' },
    { id: 'p13', name: '49ers DST', position: 'DST', team: 'SF' },
    { id: 'p14', name: 'Ravens DST', position: 'DST', team: 'BAL' },
];

// Helper to generate random normal distribution
function randomNormal(mean, stdDev) {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return mean + stdDev * Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function generateStats(position) {
    const stats = {};

    if (position === 'QB') {
        stats.passing_yards = Math.max(0, Math.round(randomNormal(240, 60)));
        stats.passing_tds = Math.max(0, Math.round(randomNormal(1.8, 1.2)));
        stats.interceptions = Math.max(0, Math.round(randomNormal(0.8, 0.8)));
        stats.completion_pct = Math.min(100, Math.max(40, Math.round(randomNormal(65, 8))));
    } else if (position === 'WR' || position === 'TE') {
        stats.receiving_yards = Math.max(0, Math.round(randomNormal(60, 35)));
        stats.receptions = Math.max(0, Math.round(randomNormal(4.5, 2.5)));
        stats.receiving_tds = Math.max(0, Math.round(randomNormal(0.4, 0.6)));
    } else if (position === 'RB') {
        const yds = Math.max(0, Math.round(randomNormal(70, 40)));
        const att = Math.max(1, Math.round(randomNormal(15, 6))); // Ensure at least 1 attempt
        stats.rushing_yards = yds;
        stats.rushing_attempts = att;
        stats.rushing_tds = Math.max(0, Math.round(randomNormal(0.5, 0.7)));
    } else if (position === 'K') {
        const made = Math.max(0, Math.round(randomNormal(2, 1)));
        const att = Math.max(made, Math.round(randomNormal(2.2, 1)));
        const xpMade = Math.max(0, Math.round(randomNormal(2.5, 1)));
        const xpAtt = Math.max(xpMade, Math.round(randomNormal(2.6, 1)));

        stats.field_goals_made = made;
        stats.field_goals_attempted = att;
        stats.extra_points_made = xpMade;
        stats.extra_points_attempted = xpAtt;
    } else if (position === 'DST') {
        stats.sacks = Math.max(0, Math.round(randomNormal(2.5, 1.5)));
        stats.interceptions = Math.max(0, Math.round(randomNormal(0.8, 0.8)));
        stats.points_allowed = Math.max(0, Math.round(randomNormal(21, 10)));
        stats.defensive_tds = Math.max(0, Math.round(randomNormal(0.1, 0.3)));
    }

    return stats;
}

// Helper to process stats and add derived ones
function processStats(stats, position) {
    const processed = { ...stats };

    if (position === 'RB') {
        // Combine Rushing Yards and Attempts into Yards Per Carry
        if (processed.rushing_attempts > 0) {
            processed.yards_per_carry = Number((processed.rushing_yards / processed.rushing_attempts).toFixed(1));
            processed._display_yards_per_carry = `${processed.yards_per_carry} (${processed.rushing_yards}/${processed.rushing_attempts})`;
        } else {
            processed.yards_per_carry = 0;
            processed._display_yards_per_carry = "0 (0/0)";
        }
        // Remove individual stats from being analyzed separately if desired, 
        // but we need them for the calculation. We'll filter them out later for the final output.
    } else if (position === 'K') {
        // Combine FG Made and Attempts
        if (processed.field_goals_attempted > 0) {
            processed.field_goal_pct = Number(((processed.field_goals_made / processed.field_goals_attempted) * 100).toFixed(0));
            processed._display_field_goal_pct = `${processed.field_goals_made}/${processed.field_goals_attempted} (${processed.field_goal_pct}%)`;
        } else {
            processed.field_goal_pct = 0;
            processed._display_field_goal_pct = "0/0";
        }

        // Combine XP Made and Attempts
        if (processed.extra_points_attempted > 0) {
            processed.extra_point_pct = Number(((processed.extra_points_made / processed.extra_points_attempted) * 100).toFixed(0));
            processed._display_extra_point_pct = `${processed.extra_points_made}/${processed.extra_points_attempted} (${processed.extra_point_pct}%)`;
        } else {
            processed.extra_point_pct = 0;
            processed._display_extra_point_pct = "0/0";
        }
    }

    return processed;
}

function generateHistory(player) {
    const history = [];
    for (let i = 0; i < 17; i++) { // 17 games
        const rawStats = generateStats(player.position);
        const processedStats = processStats(rawStats, player.position);
        history.push({
            week: i + 1,
            stats: processedStats
        });
    }
    return history;
}

function calculatePercentile(value, dataset) {
    if (dataset.length === 0) return 0;
    const sorted = [...dataset].sort((a, b) => a - b);
    const index = sorted.findIndex(v => v >= value);

    // If index is -1, value is greater than all items in dataset
    if (index === -1) {
        return 1.0;
    }

    return index / sorted.length;
}

const db = {
    players: [],
    week_stats: []
};

// 1. Generate Player History & Positional Data
const positionalData = {
    'QB': { passing_yards: [], passing_tds: [], interceptions: [], completion_pct: [] },
    'WR': { receiving_yards: [], receptions: [], receiving_tds: [] },
    'TE': { receiving_yards: [], receptions: [], receiving_tds: [] },
    'RB': { yards_per_carry: [], rushing_tds: [] }, // Removed raw yards/att
    'K': { field_goal_pct: [], extra_point_pct: [] }, // Updated to use XP pct
    'DST': { sacks: [], interceptions: [], points_allowed: [], defensive_tds: [] },
};

PLAYERS.forEach(p => {
    p.history = generateHistory(p);
    p.history.forEach(game => {
        Object.entries(game.stats).forEach(([key, val]) => {
            // Only track stats defined in positionalData
            if (positionalData[p.position] && positionalData[p.position][key] !== undefined) {
                positionalData[p.position][key].push(val);
            }
        });
    });
    db.players.push(p);
});

const STAT_CONFIG = {
    passing_yards: { lowerIsBetter: false },
    passing_tds: { lowerIsBetter: false },
    interceptions: { lowerIsBetter: true },
    completion_pct: { lowerIsBetter: false },
    receiving_yards: { lowerIsBetter: false },
    receptions: { lowerIsBetter: false },
    receiving_tds: { lowerIsBetter: false },
    yards_per_carry: { lowerIsBetter: false }, // Derived
    rushing_tds: { lowerIsBetter: false },
    field_goal_pct: { lowerIsBetter: false }, // Derived
    extra_point_pct: { lowerIsBetter: false }, // Derived
    sacks: { lowerIsBetter: false },
    interceptions: { lowerIsBetter: false }, // DST
    points_allowed: { lowerIsBetter: true },
    defensive_tds: { lowerIsBetter: false }
};

// 2. Generate "Current Week" Performance
const CURRENT_WEEK = 18;
const currentWeekPerformances = PLAYERS.map(p => {
    const rawStats = generateStats(p.position);
    const stats = processStats(rawStats, p.position);

    // Calculate percentiles
    const enrichedStats = Object.keys(positionalData[p.position]).map(key => {
        const val = stats[key];
        const config = STAT_CONFIG[key] || { lowerIsBetter: false };

        // Personal history for this stat
        const personalHistory = p.history.map(h => h.stats[key]).filter(v => v !== undefined);
        let personalPercentile = calculatePercentile(val, personalHistory);

        // Positional history
        const posHistory = positionalData[p.position][key];
        let positionalPercentile = calculatePercentile(val, posHistory);

        // Invert percentile if lower is better
        if (config.lowerIsBetter) {
            personalPercentile = 1 - personalPercentile;
            positionalPercentile = 1 - positionalPercentile;
        }

        // Check for display override
        const displayKey = `_display_${key}`;
        const displayValue = stats[displayKey];

        return {
            stat_name: key,
            value: val,
            display_value: displayValue, // Pass display value if it exists
            personal_percentile: personalPercentile,
            personal_history: personalHistory,
            positional_percentile: positionalPercentile,
            positional_history: posHistory,
            lower_is_better: config.lowerIsBetter
        };
    });

    // Calculate composite score (average of all percentiles)
    const totalPercentile = enrichedStats.reduce((sum, s) => sum + s.personal_percentile + s.positional_percentile, 0);
    const count = enrichedStats.length * 2;
    const compositeScore = totalPercentile / count;

    return {
        player_id: p.id,
        player_name: p.name,
        position: p.position,
        team: p.team,
        opponent: TEAMS[Math.floor(Math.random() * TEAMS.length)], // Random opponent
        week: CURRENT_WEEK,
        composite_score: compositeScore,
        stats: enrichedStats
    };
});

// Sort by composite score for "Top Performers"
currentWeekPerformances.sort((a, b) => b.composite_score - a.composite_score);

const output = {
    players: db.players,
    current_week: currentWeekPerformances
};

const outputPath = path.join(__dirname, '../public/data/stats.json');
fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));

console.log(`Generated stats for ${PLAYERS.length} players at ${outputPath}`);
