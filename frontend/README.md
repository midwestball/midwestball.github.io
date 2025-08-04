# KnowBall - NBA Player Statistics and Analytics

KnowBall is a web application for tracking, analyzing, and visualizing NBA player statistics with advanced analytics. It features statistical distributions, impressive performance tracking via z-scores, and detailed player profiles.

## Features

- **Player Statistics:** Comprehensive player statistics with interactive visualizations
- **Impressive Performances:** Track statistically impressive performances ranked by z-score
- **Statistical Distributions:** View probability distributions for various player stats
- **League Analytics:** League-wide statistical analysis and comparisons

## Architecture

The application uses a modern architecture optimized for serverless environments:

- **Frontend:** HTML/CSS/JavaScript with Plotly.js for visualizations
- **Backend:** Python Flask application
- **Database:** PostgreSQL (hosted on Supabase)
- **Data Collection:** Automated scripts running on GitHub Actions

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL database
- Git

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/knowball.git
   cd knowball
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```
   cp .env.example .env
   ```
   Edit the `.env` file with your database credentials.

5. Initialize the database:
   ```
   psql -U youruser -d yourdatabase -f db_schema.sql
   ```

### Running the Application

1. Local development:
   ```
   python app.py
   ```
   The application will be available at http://localhost:8080

2. Using Docker:
   ```
   docker build -t knowball .
   docker run -p 8080:8080 --env-file .env knowball
   ```

### Data Collection

For the automated data collection:

1. Initial setup:
   ```
   python data_collector.py --full
   ```

2. For daily updates (automated via GitHub Actions):
   ```
   python data_collector.py
   ```

## Deployment

The application is optimized for deployment on Vercel:

1. Install Vercel CLI:
   ```
   npm i -g vercel
   ```

2. Deploy:
   ```
   vercel
   ```

For database setup, use Supabase or any PostgreSQL provider. Make sure to set the environment variables in your deployment platform.

## GitHub Actions

The repository includes GitHub Actions workflows to:
- Automatically update player data twice daily
- Calculate statistical distributions
- Identify impressive performances

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Data is sourced from publicly available NBA statistics
- Uses the NBA Stats API and Basketball Reference as fallback data sources