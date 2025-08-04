from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from datetime import datetime, timedelta
import logging

# Import our custom modules
from db_config import execute_query
from stats_analyzer import (
    calculate_player_distributions, 
    calculate_league_distributions,
    get_recent_impressive_performances
)

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(
    __name__, 
    template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
)

# Configure Plotly theme for all charts
pio.templates.default = "plotly_dark"

@app.route('/', methods = ['GET'])
def index():
    """Homepage with impressive recent performances"""
    try:
        # Get impressive recent performances
        performances = get_recent_impressive_performances(limit = 20)
        
        # Group performances by stat type for easier display
        performances_by_stat = {}
        
        for perf in performances:
            stat_type = perf["stat_type"]
            if stat_type not in performances_by_stat:
                performances_by_stat[stat_type] = []
            performances_by_stat[stat_type].append(perf)
        
        return render_template(
            'index.html',
            performances = performances,
            performances_by_stat = performances_by_stat
        )
        
    except Exception as e:
        logger.error(f"Error rendering homepage: {e}")
        return render_template('error.html', error = str(e))

@app.route('/player_suggestions', methods = ['GET'])
def player_suggestions():
    """
    Provide player name suggestions based on partial input.
    """
    query = request.args.get('q', '').lower()
    
    if len(query) < 2:
        return jsonify([])
    
    # Query database for matching players
    search_query = """
    SELECT full_name
    FROM players
    WHERE 
        lower(full_name) LIKE %s OR
        lower(first_name) LIKE %s OR
        lower(last_name) LIKE %s
    ORDER BY 
        CASE 
            WHEN lower(full_name) = %s THEN 1
            WHEN lower(full_name) LIKE %s THEN 2
            WHEN lower(first_name) = %s THEN 3
            WHEN lower(first_name) LIKE %s THEN 4
            WHEN lower(last_name) = %s THEN 5
            WHEN lower(last_name) LIKE %s THEN 6
            ELSE 7
        END
    LIMIT 10
    """
    
    exact_query = query.lower()
    fuzzy_query = f"%{query.lower()}%"
    
    results = execute_query(
        search_query, 
        (
            fuzzy_query, fuzzy_query, fuzzy_query,
            exact_query, fuzzy_query,
            exact_query, fuzzy_query,
            exact_query, fuzzy_query
        )
    )
    
    # Extract player names
    suggestions = [result["full_name"] for result in results]
    
    return jsonify(suggestions)

@app.route('/player/<player_name>', methods = ['GET'])
def player_profile(player_name):
    """
    Player profile page showing stats and visualizations
    """
    try:
        # Get season from query parameters or use default
        season = request.args.get('season', None)
        
        # Get player ID
        player_query = "SELECT id, full_name FROM players WHERE full_name = %s"
        player_result = execute_query(player_query, (player_name,))
        
        if not player_result:
            return render_template('error.html', error = f"Player {player_name} not found")
            
        player_id = player_result[0]["id"]
        player_name = player_result[0]["full_name"]
        
        # If no season specified, find the most recent season for this player
        if not season:
            season_query = """
            SELECT DISTINCT g.season
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.id
            WHERE pgs.player_id = %s
            ORDER BY g.season DESC
            LIMIT 1
            """
            
            season_result = execute_query(season_query, (player_id,))
            
            if season_result:
                season = season_result[0]["season"]
            else:
                return render_template('error.html', error = f"No stats found for {player_name}")
        
        # Get player's game stats for the season
        games_query = """
        SELECT 
            pgs.*,
            g.game_date,
            g.home_team,
            g.away_team
        FROM 
            player_game_stats pgs
        JOIN 
            games g ON pgs.game_id = g.id
        WHERE 
            pgs.player_id = %s
            AND g.season = %s
        ORDER BY 
            g.game_date
        """
        
        games_result = execute_query(games_query, (player_id, season))
        
        if not games_result:
            return render_template(
                'error.html', 
                error = f"No stats found for {player_name} in the {season} season"
            )
        
        # Convert to DataFrame for easier manipulation
        player_data = pd.DataFrame(games_result)
        
        # Calculate rolling averages
        if len(player_data) >= 5:
            player_data['points_ma'] = player_data['points'].rolling(5, min_periods = 1).mean()
            player_data['minutes_ma'] = player_data['minutes'].rolling(5, min_periods = 1).mean()
        else:
            player_data['points_ma'] = player_data['points']
            player_data['minutes_ma'] = player_data['minutes']
        
        # Calculate rest days and back-to-backs
        player_data['game_date'] = pd.to_datetime(player_data['game_date'])
        player_data['days_rest'] = player_data['game_date'].diff().dt.days.fillna(3)
        player_data['back_to_back'] = player_data['days_rest'] == 1
        
        # Get available seasons for this player
        seasons_query = """
        SELECT DISTINCT g.season
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.id
        WHERE pgs.player_id = %s
        ORDER BY g.season DESC
        """
        
        available_seasons = execute_query(seasons_query, (player_id,))
        available_seasons = [s["season"] for s in available_seasons]
        
        # Get player's statistical distributions
        distributions = calculate_player_distributions(player_id, season)
        
        # Create visualizations
        scoring_chart = create_scoring_chart(player_data)
        efficiency_chart = create_efficiency_chart(player_data)
        rest_days_chart = create_rest_days_chart(player_data)
        back_to_back_chart = create_back_to_back_chart(player_data)
        distribution_charts = create_distribution_charts(distributions)
        
        # Get impressive performances
        performances_query = """
        SELECT 
            ip.*,
            g.game_date,
            g.home_team,
            g.away_team
        FROM 
            impressive_performances ip
        JOIN 
            games g ON ip.game_id = g.id
        WHERE 
            ip.player_id = %s
        ORDER BY 
            ip.z_score DESC
        LIMIT 10
        """
        
        impressive_performances = execute_query(performances_query, (player_id,))
        
        return render_template(
            'player_profile.html',
            player_name = player_name,
            season = season,
            available_seasons = available_seasons,
            player_data = player_data,
            scoring_chart = scoring_chart,
            efficiency_chart = efficiency_chart,
            rest_days_chart = rest_days_chart,
            back_to_back_chart = back_to_back_chart,
            distribution_charts = distribution_charts,
            impressive_performances = impressive_performances
        )
        
    except Exception as e:
        logger.error(f"Error in player profile: {e}")
        return render_template('error.html', error = str(e))

@app.route('/player_stats', methods = ['POST'])
def player_stats_redirect():
    """
    Redirect from search form to player profile page
    """
    player_name = request.form.get('player_name', '')
    season = request.form.get('season', '')
    
    if not player_name:
        return redirect(url_for('index'))
    
    if season:
        return redirect(url_for('player_profile', player_name = player_name, season = season))
    else:
        return redirect(url_for('player_profile', player_name = player_name))

@app.route('/league_stats', methods = ['GET'])
def league_stats():
    """
    League-wide statistical distributions page
    """
    try:
        # Get season from query parameters or use default
        season = request.args.get('season')
        
        # If no season specified, find the most recent season
        if not season:
            season_query = "SELECT season FROM games ORDER BY game_date DESC LIMIT 1"
            season_result = execute_query(season_query)
            
            if season_result:
                season = season_result[0]["season"]
            else:
                return render_template('error.html', error = "No game data found")
        
        # Get available seasons
        seasons_query = """
        SELECT DISTINCT season
        FROM games
        ORDER BY season DESC
        """
        
        available_seasons = execute_query(seasons_query)
        available_seasons = [s["season"] for s in available_seasons]
        
        # Get league-wide statistical distributions
        distributions = calculate_league_distributions(season)
        
        # Create distribution charts
        distribution_charts = create_distribution_charts(distributions, is_league = True)
        
        # Get top performers for each stat category
        top_performers = {}
        
        for stat_type in ['points', 'rebounds', 'assists', 'steals', 'blocks']:
            query = f"""
            SELECT 
                p.full_name,
                AVG(pgs.{stat_type}) as avg_value
            FROM 
                player_game_stats pgs
            JOIN 
                games g ON pgs.game_id = g.id
            JOIN 
                players p ON pgs.player_id = p.id
            WHERE 
                g.season = %s
            GROUP BY 
                p.full_name
            HAVING 
                COUNT(*) >= 10
            ORDER BY 
                avg_value DESC
            LIMIT 10
            """
            
            results = execute_query(query, (season,))
            top_performers[stat_type] = results
        
        return render_template(
            'league_stats.html',
            season = season,
            available_seasons = available_seasons,
            distribution_charts = distribution_charts,
            top_performers = top_performers
        )
        
    except Exception as e:
        logger.error(f"Error in league stats: {e}")
        return render_template('error.html', error = str(e))

@app.route('/impressive_performances', methods = ['GET'])
def impressive_performances():
    """
    Page showing all impressive performances
    """
    try:
        # Get stat type from query parameters
        stat_type = request.args.get('stat', None)
        
        # Get impressive performances
        query = """
        SELECT 
            ip.*,
            p.full_name as player_name,
            g.game_date,
            g.home_team,
            g.away_team,
            g.season
        FROM 
            impressive_performances ip
        JOIN 
            players p ON ip.player_id = p.id
        JOIN 
            games g ON ip.game_id = g.id
        WHERE 
            ip.display_until >= CURRENT_DATE
        """
        
        if stat_type:
            query += " AND ip.stat_type = %s"
            query_params = (stat_type,)
        else:
            query_params = None
            
        query += " ORDER BY ip.z_score DESC LIMIT 100"
        
        performances = execute_query(query, query_params)
        
        # Group by stat type
        performances_by_stat = {}
        
        for perf in performances:
            stat = perf["stat_type"]
            if stat not in performances_by_stat:
                performances_by_stat[stat] = []
            performances_by_stat[stat].append(perf)
        
        return render_template(
            'impressive_performances.html',
            performances = performances,
            performances_by_stat = performances_by_stat,
            selected_stat = stat_type
        )
        
    except Exception as e:
        logger.error(f"Error in impressive performances: {e}")
        return render_template('error.html', error = str(e))

# Chart creation functions
def create_scoring_chart(df):
    """Create a scoring trend chart"""
    fig = go.Figure()
    
    # Add points per game line
    fig.add_trace(
        go.Scatter(
            x = df['game_date'],
            y = df['points'],
            mode = 'lines+markers',
            name = 'Points',
            line = dict(color = '#3366CC', width = 1),
            marker = dict(size = 6)
        )
    )
    
    # Add 5-game moving average
    fig.add_trace(
        go.Scatter(
            x = df['game_date'],
            y = df['points_ma'],
            mode = 'lines',
            name = '5-Game Average',
            line = dict(color = '#FF9900', width = 2)
        )
    )
    
    # Add season average line
    season_avg = df['points'].mean()
    fig.add_trace(
        go.Scatter(
            x = [df['game_date'].min(), df['game_date'].max()],
            y = [season_avg, season_avg],
            mode = 'lines',
            name = 'Season Average',
            line = dict(color = '#DC3912', width = 2, dash = 'dash')
        )
    )
    
    # Update layout
    fig.update_layout(
        title = 'Scoring Trend',
        xaxis_title = 'Game Date',
        yaxis_title = 'Points',
        legend = dict(
            orientation = "h",
            yanchor = "bottom",
            y = -0.2,
            xanchor = "center",
            x = 0.5
        ),
        margin = dict(l = 20, r = 20, t = 50, b = 20),
        height = 400
    )
    
    return pio.to_html(fig, full_html = False)

def create_efficiency_chart(df):
    """Create a scoring efficiency chart"""
    # Calculate points per minute
    df['points_per_minute'] = df['points'] / df['minutes'].replace(0, np.nan)
    
    # Handle cases where minutes is 0 or NaN
    df['points_per_minute'] = df['points_per_minute'].fillna(0)
    
    fig = go.Figure()
    
    # Add scatter plot
    fig.add_trace(
        go.Scatter(
            x = df['minutes'],
            y = df['points'],
            mode = 'markers',
            marker = dict(
                size = 8,
                color = df['points_per_minute'],
                colorscale = 'Viridis',
                colorbar = dict(title = 'Points per Minute'),
                showscale = True
            ),
            text = df.apply(
                lambda row: f"Date: {row['game_date'].strftime('%Y-%m-%d')}<br>"
                          f"Points: {row['points']}<br>"
                          f"Minutes: {row['minutes']:.1f}<br>"
                          f"Efficiency: {row['points_per_minute']:.2f} pts/min",
                axis = 1
            ),
            hoverinfo = 'text'
        )
    )
    
    # Add average lines
    avg_points = df['points'].mean()
    avg_minutes = df['minutes'].mean()
    
    fig.add_hline(
        y = avg_points,
        line_dash = "dash",
        line_color = "white",
        annotation_text = f"Avg Points: {avg_points:.1f}",
        annotation_position = "bottom right"
    )
    
    fig.add_vline(
        x = avg_minutes,
        line_dash = "dash",
        line_color = "white",
        annotation_text = f"Avg Minutes: {avg_minutes:.1f}",
        annotation_position = "top left"
    )
    
    # Update layout
    fig.update_layout(
        title = 'Scoring Efficiency (Points vs. Minutes)',
        xaxis_title = 'Minutes Played',
        yaxis_title = 'Points Scored',
        margin = dict(l = 20, r = 20, t = 50, b = 20),
        height = 500
    )
    
    return pio.to_html(fig, full_html = False)

def create_rest_days_chart(df):
    """Create a rest days impact chart"""
    # Group by days rest
    rest_group = df.groupby('days_rest').agg({
        'points': ['mean', 'count']
    }).reset_index()
    
    rest_group.columns = ['days_rest', 'avg_points', 'games']
    
    # Only include categories with at least 2 games
    rest_group = rest_group[rest_group['games'] >= 2]
    
    fig = go.Figure()
    
    # Add bar chart
    fig.add_trace(
        go.Bar(
            x = rest_group['days_rest'],
            y = rest_group['avg_points'],
            text = rest_group['avg_points'].apply(lambda x: f"{x:.1f}"),
            textposition = 'auto',
            marker_color = '#3366CC',
            name = 'Avg Points',
            hovertemplate = 'Rest Days: %{x}<br>Avg Points: %{y:.1f}<br>Games: %{customdata}',
            customdata = rest_group['games']
        )
    )
    
    # Add overall average line
    overall_avg = df['points'].mean()
    fig.add_hline(
        y = overall_avg,
        line_dash = "dash",
        line_color = "red",
        annotation_text = f"Overall Avg: {overall_avg:.1f}",
        annotation_position = "bottom right"
    )
    
    # Update layout
    fig.update_layout(
        title = 'Points by Days of Rest',
        xaxis_title = 'Days Since Last Game',
        yaxis_title = 'Average Points',
        xaxis = dict(
            tickmode = 'array',
            tickvals = rest_group['days_rest'],
            ticktext = rest_group['days_rest']
        ),
        margin = dict(l = 20, r = 20, t = 50, b = 20),
        height = 400
    )
    
    return pio.to_html(fig, full_html = False)

def create_back_to_back_chart(df):
    """Create a back-to-back games comparison chart"""
    if sum(df['back_to_back']) < 2:
        # Not enough back-to-back games for meaningful analysis
        return None
    
    fig = go.Figure()
    
    # Create box plots for each category
    fig.add_trace(
        go.Box(
            y = df[~df['back_to_back']]['points'],
            name = 'Regular Rest',
            boxpoints = 'all',
            jitter = 0.3,
            pointpos = -1.8,
            marker_color = '#3366CC'
        )
    )
    
    fig.add_trace(
        go.Box(
            y = df[df['back_to_back']]['points'],
            name = 'Back-to-Back',
            boxpoints = 'all',
            jitter = 0.3,
            pointpos = -1.8,
            marker_color = '#DC3912'
        )
    )
    
    # Add averages
    regular_avg = df[~df['back_to_back']]['points'].mean()
    b2b_avg = df[df['back_to_back']]['points'].mean()
    
    fig.add_annotation(
        x = 0,
        y = regular_avg,
        text = f"Avg: {regular_avg:.1f}",
        showarrow = True,
        arrowhead = 2,
        arrowsize = 1,
        arrowwidth = 2,
        ax = -40,
        ay = 0
    )
    
    fig.add_annotation(
        x = 1,
        y = b2b_avg,
        text = f"Avg: {b2b_avg:.1f}",
        showarrow = True,
        arrowhead = 2,
        arrowsize = 1,
        arrowwidth = 2,
        ax = 40,
        ay = 0
    )
    
    # Update layout
    fig.update_layout(
        title = 'Performance in Back-to-Back Games',
        yaxis_title = 'Points Scored',
        xaxis = dict(
            ticktext = ['Regular Rest', 'Back-to-Back'],
            tickvals = [0, 1]
        ),
        margin = dict(l = 20, r = 20, t = 50, b = 20),
        height = 400
    )
    
    return pio.to_html(fig, full_html = False)

def create_distribution_charts(distributions, is_league = False):
    """Create statistical distribution charts"""
    charts = {}
    
    for stat_type, data in distributions.items():
        # Create histogram
        if 'histogram' in data:
            hist_data = data['histogram']
            
            fig = go.Figure()
            
            # Add histogram bars
            fig.add_trace(
                go.Bar(
                    x = hist_data['bin_edges'][:-1],
                    y = hist_data['counts'],
                    width = [(hist_data['bin_edges'][i+1] - hist_data['bin_edges'][i]) 
                             for i in range(len(hist_data['bin_edges'])-1)],
                    marker_color = '#3366CC',
                    name = 'Frequency'
                )
            )
            
            # Add title based on whether it's league or player stats
            title = f"Distribution of {stat_type.replace('_', ' ').title()}"
            if is_league:
                title += " Across the League"
            
            # Update layout
            fig.update_layout(
                title = title,
                xaxis_title = stat_type.replace('_', ' ').title(),
                yaxis_title = 'Frequency',
                margin = dict(l = 20, r = 20, t = 50, b = 20),
                height = 300
            )
            
            charts[f"{stat_type}_hist"] = pio.to_html(fig, full_html = False)
        
        # Create time series (player only)
        if not is_league and 'time_series' in data:
            ts_data = data['time_series']
            
            fig = go.Figure()
            
            # Add time series line
            fig.add_trace(
                go.Scatter(
                    x = ts_data['dates'],
                    y = ts_data['values'],
                    mode = 'lines+markers',
                    marker_color = '#3366CC',
                    name = stat_type.replace('_', ' ').title()
                )
            )
            
            # Add average line if we have the data
            if 'mean' in data:
                mean_value = data['mean']
                fig.add_hline(
                    y = mean_value,
                    line_dash = "dash",
                    line_color = "red",
                    annotation_text = f"Avg: {mean_value:.1f}",
                    annotation_position = "top right"
                )
            
            # Update layout
            fig.update_layout(
                title = f"{stat_type.replace('_', ' ').title()} Over Time",
                xaxis_title = "Game Date",
                yaxis_title = stat_type.replace('_', ' ').title(),
                margin = dict(l = 20, r = 20, t = 50, b = 20),
                height = 300
            )
            
            charts[f"{stat_type}_time"] = pio.to_html(fig, full_html = False)
    
    return charts

# Main application entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host = "0.0.0.0", port = port, debug = True)