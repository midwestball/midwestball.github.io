"""
Setup script for local PostgreSQL database.
This script creates the database schema matching Supabase.
"""

import asyncio
import asyncpg
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def setup_database(connection_string: str, schema_file: str):
    """
    Connect to PostgreSQL and execute the schema SQL file.
    """
    logger.info(f"Connecting to database...")

    try:
        # Connect to the database
        conn = await asyncpg.connect(connection_string)

        logger.info("Connected successfully. Reading schema file...")

        # Read the schema file
        schema_path = Path(schema_file)
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_file}")
            return False

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        logger.info("Executing schema SQL...")

        # Execute the schema SQL
        # We need to handle multi-line statements (especially functions with $$)
        statements = []
        current_statement = []
        in_dollar_quote = False
        dollar_tag = None

        for line in schema_sql.split('\n'):
            # Skip standalone comments
            stripped = line.strip()
            if stripped.startswith('--') and not in_dollar_quote:
                continue

            # Track dollar-quoted strings (used in functions)
            if '$$' in line:
                if not in_dollar_quote:
                    in_dollar_quote = True
                    # Extract the dollar quote tag if it exists (e.g., $body$ or $$)
                    dollar_tag = '$$'
                elif dollar_tag and dollar_tag in line:
                    in_dollar_quote = False
                    dollar_tag = None

            current_statement.append(line)

            # Check if this line ends a statement (semicolon, but not inside dollar quotes)
            if not in_dollar_quote and line.strip().endswith(';'):
                statement = '\n'.join(current_statement).strip()
                if statement:
                    statements.append(statement)
                current_statement = []

        # Don't forget the last statement if there is one
        if current_statement:
            statement = '\n'.join(current_statement).strip()
            if statement:
                statements.append(statement)

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            try:
                await conn.execute(statement)
                logger.info(f"Executed statement {i}/{len(statements)}")
            except asyncpg.exceptions.DuplicateObjectError:
                logger.warning(f"Object already exists (skipping): statement {i}")
            except Exception as e:
                logger.error(f"Error executing statement {i}: {e}")
                # Show more of the statement for debugging
                preview = statement.replace('\n', ' ')[:150]
                logger.error(f"Statement: {preview}...")

        logger.info("Schema setup complete!")

        await conn.close()
        return True

    except asyncpg.exceptions.InvalidCatalogNameError:
        logger.error("Database does not exist. Please create it first.")
        logger.info("You can create it with: createdb knowball_analytics")
        return False
    except Exception as e:
        logger.error(f"Error setting up database: {e}", exc_info=True)
        return False


async def verify_setup(connection_string: str):
    """
    Verify that the database schema was created successfully.
    """
    logger.info("Verifying database setup...")

    try:
        conn = await asyncpg.connect(connection_string)

        # Check for key tables
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        table_names = [t['table_name'] for t in tables]
        logger.info(f"Found {len(table_names)} tables:")

        expected_tables = [
            'sports', 'seasons', 'teams', 'players', 'games',
            'player_game_stats', 'weekly_percentiles',
            'player_performance_scores', 'ml_models',
            'ml_feature_store', 'ml_predictions'
        ]

        for table in expected_tables:
            if table in table_names:
                logger.info(f"  ✓ {table}")
            else:
                logger.warning(f"  ✗ {table} (missing)")

        # Check if sports and seasons have data
        sport_count = await conn.fetchval("SELECT COUNT(*) FROM sports")
        season_count = await conn.fetchval("SELECT COUNT(*) FROM seasons")

        logger.info(f"\nData check:")
        logger.info(f"  Sports: {sport_count}")
        logger.info(f"  Seasons: {season_count}")

        await conn.close()

        if len(table_names) >= len(expected_tables):
            logger.info("\n✓ Database setup verified successfully!")
            return True
        else:
            logger.warning("\n⚠ Some tables are missing. Please check the schema.")
            return False

    except Exception as e:
        logger.error(f"Error verifying setup: {e}")
        return False


async def main():
    import argparse
    from config import Config

    parser = argparse.ArgumentParser(description="Setup local PostgreSQL database")
    parser.add_argument(
        "--connection-string",
        type=str,
        help="PostgreSQL connection string (optional, uses LOCAL_DATABASE_URL from .env by default)"
    )
    parser.add_argument(
        "--schema-file",
        type=str,
        default="../supabase/migrations/001_initial_schema.sql",
        help="Path to the schema SQL file"
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip verification step after setup"
    )

    args = parser.parse_args()

    # Get connection string from args or config
    connection_string = args.connection_string or Config.LOCAL_DATABASE_URL

    if not connection_string:
        logger.error("No connection string provided.")
        logger.error("Either set LOCAL_DATABASE_URL in .env or use --connection-string")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Local PostgreSQL Database Setup")
    logger.info("=" * 60)
    logger.info(f"Connection string: {connection_string}")
    logger.info(f"Schema file: {args.schema_file}")
    logger.info("=" * 60)

    # Setup the database
    success = await setup_database(connection_string, args.schema_file)

    if not success:
        logger.error("Database setup failed!")
        sys.exit(1)

    # Verify the setup (unless skipped)
    if not args.skip_verification:
        await verify_setup(connection_string)

    logger.info("\nNext steps:")
    logger.info("1. Set USE_LOCAL_DB=true in your .env file (or use --use-local-db flag)")
    logger.info("2. Run seed command: python main.py --mode seed --use-local-db")
    logger.info("3. Start collecting data: python main.py --mode collect --season 2024 --week 8 --use-local-db")


if __name__ == "__main__":
    asyncio.run(main())
