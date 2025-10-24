"""
Diagnostic script to debug why position_stat_distribution_agg is empty.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def diagnose():
    """Run diagnostics on the aggregation tables."""

    # Connect using the LOCAL_DATABASE_URL from .env
    conn = await asyncpg.connect(os.getenv("LOCAL_DATABASE_URL"))

    try:
        print("=" * 70)
        print("DIAGNOSTICS: Aggregation Tables Investigation")
        print("=" * 70)

        # 1. Check if player_game_stats has data
        print("\n1. Checking player_game_stats table...")
        stats_count = await conn.fetchval("SELECT COUNT(*) FROM player_game_stats")
        print(f"   Total player_game_stats rows: {stats_count}")

        if stats_count > 0:
            sample_stats = await conn.fetch("""
                SELECT game_id, player_id, position, stat_category, stat_value
                FROM player_game_stats
                LIMIT 5
            """)
            print(f"   Sample data:")
            for row in sample_stats:
                print(f"     game_id={row['game_id']}, player_id={row['player_id']}, "
                      f"position={row['position']}, stat={row['stat_category']}, value={row['stat_value']}")

        # 2. Check distinct positions and stat categories
        print("\n2. Checking distinct positions and stat categories...")
        positions = await conn.fetch("""
            SELECT DISTINCT position, COUNT(*) as count
            FROM player_game_stats
            GROUP BY position
            ORDER BY count DESC
        """)
        print(f"   Positions found:")
        for row in positions:
            print(f"     {row['position']}: {row['count']} stats")

        stat_categories = await conn.fetch("""
            SELECT DISTINCT stat_category, COUNT(*) as count
            FROM player_game_stats
            GROUP BY stat_category
            ORDER BY count DESC
            LIMIT 10
        """)
        print(f"   Top stat categories:")
        for row in stat_categories:
            print(f"     {row['stat_category']}: {row['count']} stats")

        # 3. Check player_stat_history_agg (the working table)
        print("\n3. Checking player_stat_history_agg table...")
        history_count = await conn.fetchval("SELECT COUNT(*) FROM player_stat_history_agg")
        print(f"   Total player_stat_history_agg rows: {history_count}")

        if history_count > 0:
            sample_history = await conn.fetch("""
                SELECT player_id, season_id, stat_category, game_count
                FROM player_stat_history_agg
                LIMIT 5
            """)
            print(f"   Sample data:")
            for row in sample_history:
                print(f"     player_id={row['player_id']}, season_id={row['season_id']}, "
                      f"stat={row['stat_category']}, games={row['game_count']}")

        # 4. Check position_stat_distribution_agg (the empty table)
        print("\n4. Checking position_stat_distribution_agg table...")
        position_count = await conn.fetchval("SELECT COUNT(*) FROM position_stat_distribution_agg")
        print(f"   Total position_stat_distribution_agg rows: {position_count}")

        if position_count > 0:
            sample_position = await conn.fetch("""
                SELECT season_id, position, stat_category, week_number, player_count, game_count
                FROM position_stat_distribution_agg
                LIMIT 10
            """)
            print(f"   Sample data:")
            for row in sample_position:
                print(f"     season_id={row['season_id']}, position={row['position']}, "
                      f"stat={row['stat_category']}, week={row['week_number']}, "
                      f"players={row['player_count']}, games={row['game_count']}")
        else:
            print(f"   *** TABLE IS EMPTY ***")

        # 5. Test the function manually with real data
        print("\n5. Testing update_position_stat_distribution() manually...")

        # Get a real game to test with
        test_game = await conn.fetchrow("""
            SELECT g.game_id, g.season_id, g.game_week, pgs.position, pgs.stat_category
            FROM games g
            JOIN player_game_stats pgs ON g.game_id = pgs.game_id
            LIMIT 1
        """)

        if test_game:
            print(f"   Testing with: game_id={test_game['game_id']}, season={test_game['season_id']}, "
                  f"week={test_game['game_week']}, position={test_game['position']}, stat={test_game['stat_category']}")

            try:
                # Call the function directly
                await conn.execute("""
                    SELECT update_position_stat_distribution($1, $2, $3, $4)
                """, test_game['season_id'], test_game['position'],
                     test_game['stat_category'], test_game['game_week'])

                print(f"   ✓ Function executed successfully!")

                # Check if it inserted anything
                check = await conn.fetchval("""
                    SELECT COUNT(*) FROM position_stat_distribution_agg
                    WHERE season_id = $1 AND position = $2 AND stat_category = $3 AND week_number = $4
                """, test_game['season_id'], test_game['position'],
                     test_game['stat_category'], test_game['game_week'])

                print(f"   Rows inserted/updated: {check}")

            except Exception as e:
                print(f"   ✗ Function failed with error: {e}")
                print(f"   Error type: {type(e).__name__}")
        else:
            print(f"   No game data found to test with!")

        # 6. Check if refresh_aggregations_for_game is being called
        print("\n6. Testing refresh_aggregations_for_game()...")

        test_game_id = await conn.fetchval("SELECT game_id FROM games LIMIT 1")
        if test_game_id:
            print(f"   Testing with game_id={test_game_id}")
            try:
                await conn.execute("SELECT refresh_aggregations_for_game($1)", test_game_id)
                print(f"   ✓ Function executed successfully!")

                # Check position table again
                position_count_after = await conn.fetchval("SELECT COUNT(*) FROM position_stat_distribution_agg")
                print(f"   Position table rows after refresh: {position_count_after}")

            except Exception as e:
                print(f"   ✗ Function failed with error: {e}")
                print(f"   Error type: {type(e).__name__}")

        print("\n" + "=" * 70)
        print("DIAGNOSIS COMPLETE")
        print("=" * 70)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(diagnose())
