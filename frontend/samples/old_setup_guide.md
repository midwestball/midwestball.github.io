# NFL Analytics Platform - Setup Guide

## Project Overview

This simplified NFL analytics platform uses:
- **Frontend**: React (deployed on Vercel)
- **Backend**: Python FastAPI + SQLite (deployed on Railway)
- **Mathematics**: Dual-component impressiveness scoring framework

## Local Development Setup

### 1. Backend Setup (Python FastAPI)

```bash
# Create project directory
mkdir nfl-analytics && cd nfl-analytics
mkdir backend && cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn pandas numpy scipy scikit-learn requests

# Create the main files
# Copy the FastAPI backend code into main.py
# Copy the data collection script into data_collection.py

# Initialize database with synthetic data
python data_collection.py

# Run the backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

### 2. Frontend Setup (React)

```bash
# In a new terminal, go back to project root
cd ../

# Create React app
npx create-react-app frontend
cd frontend

# Replace src/App.js with the React frontend code
# Replace src/App.css with the CSS styles

# Add environment variable
echo "REACT_APP_API_URL=http://localhost:8000" > .env.local

# Start the frontend
npm start
```

The frontend will be available at `http://localhost:3000`

## Mathematical Framework Implementation

### Core Equation

The impressiveness score combines personal improvement and peer comparison:

$$I_p = 0.6 \cdot \frac{\sum_{i=1}^k w_i \cdot \Phi(z_{p,i})}{\sum_{i=1}^k w_i} + 0.4 \cdot \frac{\sum_{i=1}^k w_i \cdot r_{p,i}}{\sum_{i=1}^k w_i}$$

Where:
- $z_{p,i} = \frac{s_{p,g,i} - \mu_{p,i}}{\sigma_{p,i}}$ (personal z-score)
- $r_{p,i}$ = percentile rank vs peers
- $w_i$ = position-specific weights
- $\Phi$ = standard normal CDF

### Position-Specific Configurations

**Quarterbacks:**
```python
{
    "key_stats": ["passing_yards", "passing_touchdowns", "interceptions", "completions", "attempts"],
    "weights": {
        "passing_touchdowns": 0.35,
        "passing_yards": 0.30,
        "completions": 0.15,
        "attempts": 0.10,
        "interceptions": -0.10
    }
}
```

**Running Backs:**
```python
{
    "key_stats": ["rushing_yards", "rushing_touchdowns", "receiving_yards", "receiving_touchdowns"],
    "weights": {
        "rushing_touchdowns": 0.35,
        "rushing_yards": 0.30,
        "receiving_yards": 0.20,
        "receiving_touchdowns": 0.15
    }
}
```

## Deployment Guide

### 1. Backend Deployment (Railway)

1. **Create Railway Account**: Sign up at [railway.app](https://railway.app)

2. **Create New Project**: 
   - Connect your GitHub repository
   - Select the backend directory

3. **Configure Environment**:
   ```bash
   # Railway will automatically detect Python and install dependencies
   # Ensure requirements.txt is in your backend directory
   ```

4. **Database Setup**:
   ```bash
   # Railway will run data_collection.py automatically on first deploy
   # The SQLite database will be created in the container
   ```

5. **Custom Start Command** (if needed):
   ```bash
   python data_collection.py && uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

### 2. Frontend Deployment (Vercel)

1. **Create Vercel Account**: Sign up at [vercel.com](https://vercel.com)

2. **Import Project**: 
   - Connect your GitHub repository
   - Select the frontend directory

3. **Configure Build Settings**:
   - Framework Preset: Create React App
   - Build Command: `npm run build`
   - Output Directory: `build`

4. **Environment Variables**:
   ```
   REACT_APP_API_URL = https://your-railway-app.railway.app
   ```

5. **Deploy**: Vercel will automatically build and deploy

## API Endpoints

### Core Analytics Endpoints

**POST /analyze**
```json
{
  "player_id": 1,
  "game_id": 1,
  "stats": {
    "passing_yards": 350,
    "passing_touchdowns": 3,
    "interceptions": 1,
    "completions": 28,
    "attempts": 42
  }
}
```

**GET /top-performances**
```
?position=QB&timeframe=month&limit=20
```

**GET /players**
```
?position=QB
```

## Database Schema Summary

### Key Tables

1. **teams**: NFL team information
2. **players**: Player roster with positions
3. **games**: Game schedule and results
4. **player_game_stats**: Individual game statistics
5. **performance_analysis**: Mathematical analysis results

### Sample Queries

**Top QB Performances This Month:**
```sql
SELECT 
    p.name, t.abbreviation, pa.impressiveness_score,
    pa.personal_percentile, pa.comparative_percentile
FROM performance_analysis pa
JOIN players p ON pa.player_id = p.id
JOIN teams t ON p.team_id = t.id
WHERE p.position = 'QB' 
    AND pa.created_at >= date('now', '-30 days')
ORDER BY pa.impressiveness_score DESC
LIMIT 10;
```

## Data Collection Strategy

### Option 1: Synthetic Data (Included)
- Realistic statistical distributions
- Position-appropriate stat ranges
- Season-long progression modeling
- Suitable for development and testing

### Option 2: Real NFL Data
- **ESPN API**: Public endpoints for basic stats
- **NFL.com**: Limited free access
- **Sports Reference**: Historical data scraping
- **Fantasy Football APIs**: Player performance data

### Example Real Data Integration
```python
def fetch_real_nfl_data(week: int, season: int):
    """Fetch real NFL data from public APIs"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    params = {"week": week, "seasontype": 2, "year": season}
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Process and store in database
    # Implementation depends on specific API structure
```

## Testing the Mathematical Framework

### Validation Approaches

1. **Expert Comparison**: Compare scores to analyst rankings
2. **Fan Engagement**: Correlate with social media mentions
3. **Predictive Power**: Test correlation with future performance
4. **Edge Case Analysis**: Test with known outlier performances

### Sample Test Cases

```python
def test_impressiveness_calculation():
    # Test case: Career-best performance for average player
    player_avg_stats = {"passing_yards": 250, "passing_touchdowns": 1.5}
    game_stats = {"passing_yards": 450, "passing_touchdowns": 4}
    
    # Should score high on personal improvement
    assert personal_component > 90
    
    # Test case: Good but typical performance for elite player
    elite_avg_stats = {"passing_yards": 320, "passing_touchdowns": 2.8}
    game_stats = {"passing_yards": 350, "passing_touchdowns": 3}
    
    # Should score high on peer comparison, moderate on personal
    assert comparative_component > 80
    assert personal_component < 70
```

## Performance Optimization

### Backend Optimizations
- SQLite indexes on frequently queried columns
- Batch analysis calculations
- Caching for frequently accessed player baselines
- Connection pooling for concurrent requests

### Frontend Optimizations
- Component memoization for expensive calculations
- Virtual scrolling for large performance lists
- Progressive loading of detailed analyses
- Responsive design for mobile analytics

## Monitoring and Analytics

### Key Metrics to Track
- API response times
- Database query performance
- Analysis calculation accuracy
- User engagement with different performance types
- Mathematical framework confidence scores

### Logging Strategy
```python
import logging

logger = logging.getLogger(__name__)

def analyze_performance(player_id, stats):
    logger.info(f"Analyzing performance for player {player_id}")
    
    try:
        result = calculate_impressiveness(stats)
        logger.info(f"Analysis complete: score={result.score}, confidence={result.confidence}")
        return result
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise
```

## Future Enhancements

### Phase 2 Features
- **Multi-sport expansion**: Basketball, baseball analytics
- **Advanced visualizations**: Performance trend charts
- **Predictive modeling**: Season trajectory forecasting
- **Social features**: User-generated performance discussions

### Phase 3 Features
- **Real-time analysis**: Live game performance tracking
- **Mobile app**: Native iOS/Android applications
- **API monetization**: Premium analytics for fantasy sports
- **Machine learning**: Automated pattern recognition

## Troubleshooting

### Common Issues

**Database Connection Errors:**
```bash
# Ensure SQLite file permissions
chmod 644 nfl_analytics.db

# Verify database schema
sqlite3 nfl_analytics.db ".schema"
```

**CORS Errors:**
```python
# Update FastAPI CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-vercel-app.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Mathematical Calculation Errors:**
```python
# Handle division by zero in z-score calculations
if std_val == 0:
    z_scores[stat] = 0.0
else:
    z_scores[stat] = (current_val - mean_val) / std_val
```

This simplified platform provides a solid foundation for NFL analytics while maintaining realistic scope for individual development. The mathematical framework offers genuine analytical innovation, and the architecture supports future expansion into additional sports and advanced features.