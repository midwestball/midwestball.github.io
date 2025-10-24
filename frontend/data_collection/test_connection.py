import asyncio
import asyncpg
from config import Config
from database import Database
from local_database import LocalDatabase

async def test_supabase_connection():
    """Test Supabase connection"""
    print("=" * 60)
    print("TESTING SUPABASE CONNECTION")
    print("=" * 60)

    try:
        if not Config.SUPABASE_URL or Config.SUPABASE_URL == "your_supabase_url_here":
            print("❌ SUPABASE_URL not configured in .env")
            return False

        if not Config.SUPABASE_KEY or Config.SUPABASE_KEY == "your_supabase_anon_key_here":
            print("❌ SUPABASE_KEY not configured in .env")
            return False

        print(f"🔌 Connecting to: {Config.SUPABASE_URL}")

        db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        await db.connect()

        # Test query
        result = db.client.table("sports").select("*").limit(1).execute()

        print("✅ Supabase connection successful!")
        print(f"   Found {len(result.data)} sport(s)")

        await db.close()
        return True

    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print(f"   Error type: {type(e)}")
        return False

async def test_local_connection():
    """Test Local PostgreSQL connection"""
    print("\n" + "=" * 60)
    print("TESTING LOCAL POSTGRESQL CONNECTION")
    print("=" * 60)

    try:
        if not Config.LOCAL_DATABASE_URL:
            print("❌ LOCAL_DATABASE_URL not configured in .env")
            print("   Add: LOCAL_DATABASE_URL=postgresql://localhost/knowball")
            return False

        print(f"🔌 Connecting to: {Config.LOCAL_DATABASE_URL}")

        conn = await asyncpg.connect(Config.LOCAL_DATABASE_URL)

        # Test queries
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Local PostgreSQL connection successful!")
        print(f"   Version: {version[:50]}...")

        # Count tables
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        print(f"   Tables found: {len(tables)}")

        # Check for key tables
        table_names = [t['table_name'] for t in tables]
        expected_tables = ['sports', 'seasons', 'teams', 'players', 'games', 'player_game_stats']

        for table in expected_tables:
            if table in table_names:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"   ✓ {table}: {count} records")
            else:
                print(f"   ✗ {table}: NOT FOUND (run schema migration)")

        await conn.close()
        return True

    except Exception as e:
        print(f"❌ Local PostgreSQL connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")

        if "does not exist" in str(e):
            print("\n💡 Database 'knowball' doesn't exist. Create it with:")
            print("   createdb knowball")
        elif "Connection refused" in str(e):
            print("\n💡 PostgreSQL server not running. Start it with:")
            print("   brew services start postgresql")
        elif "authentication failed" in str(e):
            print("\n💡 Authentication issue. Try:")
            print("   LOCAL_DATABASE_URL=postgresql://your_username@localhost/knowball")

        return False

async def main():
    print("\n🔧 Database Connection Test\n")

    # Test both connections
    supabase_ok = await test_supabase_connection()
    local_ok = await test_local_connection()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Supabase:   {'✅ Connected' if supabase_ok else '❌ Failed'}")
    print(f"Local DB:   {'✅ Connected' if local_ok else '❌ Failed'}")

    if supabase_ok and local_ok:
        print("\n🎉 All connections successful! You're ready to collect data.")
    elif supabase_ok:
        print("\n⚠️  Supabase OK, but local DB needs setup.")
        print("   Run: psql -d knowball -f supabase/migrations/001_initial_schema.sql")
    elif local_ok:
        print("\n⚠️  Local DB OK, but Supabase needs configuration.")
        print("   Update SUPABASE_URL and SUPABASE_KEY in .env")
    else:
        print("\n❌ Both connections failed. Check the errors above.")

    print()

if __name__ == "__main__":
    asyncio.run(main())
