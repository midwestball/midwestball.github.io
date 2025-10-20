import asyncio
import asyncpg
from config import Config

async def test_connection():
    try:
        print(f"Trying to connect to: {Config.DATABASE_URL}")
        conn = await asyncpg.connect(Config.DATABASE_URL)
        print("Connection successful!")

        # Test a simple query
        result = await conn.fetchval("SELECT version()")
        print(f"Database version: {result}")

        await conn.close()

    except Exception as e:
        print(f"Connection failed: {e}")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    asyncio.run(test_connection())