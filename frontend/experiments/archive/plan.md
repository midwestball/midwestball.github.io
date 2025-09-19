# NBA Stats App Architecture Redesign

## Database Schema

### Players
- id (primary key)
- first_name
- last_name
- full_name
- is_active
- player_slug (for URLs)
- last_updated

### Games
- id (primary key)
- game_date
- season
- home_team
- away_team
- game_id (from NBA API/source)

### PlayerGameStats
- id (primary key)
- player_id (foreign key)
- game_id (foreign key)
- points
- rebounds
- assists
- steals
- blocks
- minutes
- field_goal_percentage
- three_point_percentage
- free_throw_percentage
- turnover
- plus_minus

### LeagueAverages
- id (primary key)
- season
- stat_type (points, rebounds, etc.)
- average_value
- standard_deviation
- min_value
- max_value
- sample_size
- last_updated

### ImpressivePerformances
- id (primary key)
- player_id (foreign key)
- game_id (foreign key)
- stat_type
- value
- z_score
- rank
- display_until (date)

## System Components

1. **Database Layer**
   - PostgreSQL hosted on a managed service (e.g., Supabase)
   - NoSQL option for flexibility (e.g., MongoDB Atlas or Firestore)

2. **Data Collection Service**
   - Standalone Python script running on a scheduled basis (e.g., daily)
   - Uses NBA Stats API or alternative data sources
   - Calculates z-scores and identifies impressive performances
   - Updates database with new stats and performance metrics

3. **Web Application**
   - Flask app optimized for Vercel serverless functions
   - Static generation for common pages
   - API routes for dynamic data
   - Client-side rendering for visualization components

4. **Caching Layer**
   - Redis or similar for frequently accessed data
   - Browser caching for static assets
   - API response caching

## Data Flow

1. **Daily Data Collection**
   - Fetch new game data from NBA Stats API or alternative sources
   - Process and calculate z-scores
   - Update database with new stats
   - Run on a separate service (e.g., GitHub Actions, AWS Lambda)

2. **Web Application**
   - Serve pre-calculated data from database
   - No live scraping during user requests
   - Use client-side rendering for visualizations

## Implementation Plan

1. Set up database schema
2. Create data collection service
3. Refactor web application
4. Add new features (z-score analysis, statistical distributions)
5. Deploy to Vercel

## Technology Stack

- **Database**: Supabase (PostgreSQL)
- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript (with Plotly for visualizations)
- **Deployment**: Vercel for web app, GitHub Actions for scheduled tasks
- **Analytics**: Custom z-score calculation library