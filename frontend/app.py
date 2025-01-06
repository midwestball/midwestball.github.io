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
    template_folder=os.path.join(os.path.dirname(__file__), "./templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "./static")
)

# Load players at startup
PLAYERS = player_cache.load_players()

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/test_connection', methods=['GET'])
def test_connection():
    try:
        # Test if the app can connect to the NBA API
        response = requests.get('https://stats.nba.com')
        return jsonify({'status': 'success', 'response': response.text[:200]})  # Return first 200 chars of response
    except requests.exceptions.RequestException as e:
        # Handle errors if connection fails
        return jsonify({'status': 'error', 'error': str(e)})

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
        
        return render_template(
            'player_stats.html', 
            player_name=player_name, 
            points_chart=points_chart,
            rest_days_chart=rest_days_chart,
            season=season,
            player_data=player_data
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
    return pio.to_html(fig, full_html=False)

if __name__ == '__main__':
    # Update player cache on startup
    player_cache.cache_players()
    app.run(debug=True)