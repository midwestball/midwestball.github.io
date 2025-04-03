from flask import Flask, render_template, request, jsonify
import os
import difflib
import plotly.express as px
import plotly.io as pio
import pandas as pd
import get_nba_data
import player_cache
import requests

# Initialize Flask app
app = Flask(
    __name__, 
    template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
)    

# Load player data
# For Vercel, we'll need to handle this differently since we can't write to the filesystem
try:
    PLAYERS = player_cache.load_players()
except Exception as e:
    print(f"Warning: Failed to load player cache: {e}")
    PLAYERS = []

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/player_suggestions', methods=['GET'])
def player_suggestions():
    """
    Provide player name suggestions based on partial input.
    """
    query = request.args.get('q', '').lower()
    
    # Find matches using difflib for fuzzy matching
    suggestions = []
    for player in PLAYERS:
        # Check if query matches first name, last name, or full name
        if (query in player['first_name'].lower() or 
            query in player['last_name'].lower() or 
            query in player['name'].lower()):
            suggestions.append(player['name'])
    
    # Sort suggestions by similarity
    suggestions.sort(key=lambda x: difflib.SequenceMatcher(None, query, x.lower()).ratio(), reverse=True)
    
    return jsonify(suggestions[:10])  # Limit to 10 suggestions

@app.route('/player_stats', methods=['POST'])
def player_stats():
    """
    Fetch and display player statistics and visualizations.
    """
    player_name = request.form['player_name']
    season = request.form.get('season', '2023-24')
    
    try:
        # Fetch player data using your existing function
        player_data = get_nba_data.get_player_data(player_name, season)
        
        # Create visualizations
        points_chart = create_points_chart(player_data)
        rest_days_chart = create_rest_days_chart(player_data)
        efficiency_chart = create_scoring_efficiency_chart(player_data)
        rolling_stats = create_rolling_stats_chart(player_data)
        back_to_back_chart = create_back_to_back_comparison(player_data)
        
        return render_template(
            'player_stats.html', 
            player_name=player_name,
            season=season,
            player_data=player_data,
            points_chart=points_chart,
            rest_days_chart=rest_days_chart,
            efficiency_chart=efficiency_chart,
            rolling_stats=rolling_stats,
            back_to_back_chart=back_to_back_chart
        )
    
    except Exception as e:
        return render_template('index.html', error=f"Error fetching data: {str(e)}")

def create_points_chart(df):
    """Create an interactive line chart of points over time."""
    fig = px.line(
        df, 
        template='plotly_dark',
        x='game_date', 
        y='points', 
        title=f'Points per Game',
        labels={'points': 'Points', 'game_date': 'Game Date'}
    )
    fig.add_scatter(
        x=df['game_date'], 
        y=df['points_ma'], 
        mode='lines', 
        name='5-Game Moving Average'
    )
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5
        )
    )
    return pio.to_html(fig, full_html=False)

def create_rest_days_chart(df):
    """Create a chart showing rest days and their impact."""
    fig = px.scatter(
        df, 
        template='plotly_dark',
        x='days_rest', 
        y='points', 
        title='Points by Rest Days',
        labels={'days_rest': 'Days Since Last Game', 'points': 'Points Scored'}
    )
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5
        )
    )
    return pio.to_html(fig, full_html=False)

def create_scoring_efficiency_chart(df):
    """Create a scatter plot showing points vs minutes with efficiency metrics."""
    # Calculate points per minute
    df['points_per_minute'] = df['points'] / df['minutes']
    
    fig = px.scatter(
        df,
        template='plotly_dark',
        x='minutes',
        y='points',
        color='points_per_minute',
        title='Scoring Efficiency by Minutes Played',
        labels={
            'minutes': 'Minutes Played',
            'points': 'Points Scored',
            'points_per_minute': 'Points per Minute'
        }
    )
    
    # Add average lines
    fig.add_hline(
        y=df['points'].mean(),
        line_dash="dash",
        line_color="white",
        annotation_text="Avg Points"
    )
    fig.add_vline(
        x=df['minutes'].mean(),
        line_dash="dash",
        line_color="white",
        annotation_text="Avg Minutes"
    )
    
    return pio.to_html(fig, full_html=False)

def create_rolling_stats_chart(df):
    """Create a comprehensive rolling statistics chart."""
    fig = px.line(
        df,
        template='plotly_dark',
        x='game_date',
        y=['points', 'points_ma', 'season_avg_points'],
        title='Scoring Trends and Averages',
        labels={
            'game_date': 'Game Date',
            'value': 'Points',
            'variable': 'Metric'
        }
    )
    
    # Customize line properties
    fig.update_traces(
        line=dict(width=1),
        selector=dict(name='points')
    )
    fig.update_traces(
        line=dict(width=2),
        selector=dict(name='points_ma')
    )
    fig.update_traces(
        line=dict(width=2, dash='dot'),
        selector=dict(name='season_avg_points')
    )
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5
        )
    )
    return pio.to_html(fig, full_html=False)

def create_back_to_back_comparison(df):
    """Create a box plot comparing performance in back-to-back games."""
    fig = px.box(
        df,
        template='plotly_dark',
        x='back_to_back',
        y='points',
        title='Points Distribution in Back-to-Back Games',
        labels={
            'back_to_back': 'Back-to-Back Game',
            'points': 'Points Scored'
        },
        color='back_to_back'
    )
    
    # Update layout for better readability
    fig.update_layout(
        xaxis=dict(
            ticktext=['Regular Rest', 'Back-to-Back'],
            tickvals=[False, True]
        )
    )
    fig.update_layout(
        xaxis=dict(
            ticktext=['Regular Rest', 'Back-to-Back'],
            tickvals=[False, True]
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5
        )
    )
    
    return pio.to_html(fig, full_html=False)