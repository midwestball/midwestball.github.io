# KnowBall Deployment Guide

## Overview
This guide walks you through deploying the KnowBall NBA statistics application to Vercel with a Supabase database backend.

## Prerequisites
- Vercel account
- Supabase account
- Git repository with your code

## Step 1: Set up Supabase Database

1. Create a new project in [Supabase](https://supabase.com)
2. Go to the SQL Editor in your Supabase dashboard
3. Run the SQL script from `db_schema.sql` to create all tables
4. Note down your database connection details:
   - Project URL
   - Database password
   - Service role key (for data collection)

## Step 2: Configure Environment Variables

1. Copy `.env.example` to `.env` locally for testing
2. Fill in your Supabase credentials:
   ```
   SUPABASE_URL=https://your-project-ref.supabase.co
   DB_HOST=db.your-project-ref.supabase.co
   DB_NAME=postgres
   DB_USER=postgres
   DB_PASSWORD=your-database-password
   DB_PORT=5432
   ```

## Step 3: Deploy to Vercel

1. Install Vercel CLI: `npm i -g vercel`
2. In your project directory, run: `vercel`
3. Follow the prompts to link your project
4. Set environment variables in Vercel dashboard:
   - Go to your project settings
   - Add the same environment variables from your `.env` file

## Step 4: Set up Data Collection (Optional)

The application is designed to work with NBA statistics data. You'll need to:

1. Set up GitHub Actions or another scheduled service to run `data_collection.py`
2. This script will populate your database with NBA statistics
3. The app will automatically calculate impressive performances and statistics

## Step 5: Configure Supabase Policies

The database schema includes Row Level Security (RLS) policies for public read access. You may need to adjust these based on your specific needs:

1. Go to Authentication > Policies in Supabase
2. Review the automatically created policies
3. Modify as needed for your use case

## File Structure

```
├── api/
│   └── index.py          # Vercel serverless function entry point
├── templates/            # HTML templates
├── static/              # CSS/JS assets
├── app.py               # Main Flask application
├── db_config.py         # Database configuration
├── stats_analyzer.py    # Statistical analysis functions
├── data_collection.py   # Data collection script
├── db_schema.sql        # Database schema
└── vercel.json          # Vercel configuration
```

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Your Supabase project URL | `https://abc123.supabase.co` |
| `DB_HOST` | Database host | `db.abc123.supabase.co` |
| `DB_NAME` | Database name | `postgres` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `your-secure-password` |
| `DB_PORT` | Database port | `5432` |

## Troubleshooting

### Database Connection Issues
- Verify your Supabase credentials
- Check that your database is running
- Ensure the connection string format is correct

### Deployment Issues
- Check Vercel logs for detailed error messages
- Verify all environment variables are set correctly
- Ensure `requirements.txt` includes all dependencies

### Data Issues
- Run the data collection script manually to populate the database
- Check that the database schema matches the expected structure
- Verify that statistical calculations are running correctly

## Next Steps

1. Deploy the application to Vercel
2. Set up your Supabase database
3. Configure data collection (if needed)
4. Test the application functionality
5. Set up monitoring and maintenance