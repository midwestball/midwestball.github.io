import os
import logging
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Database connection configuration
# Support both Supabase connection strings and individual parameters
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")

if DATABASE_URL:
    # Use DATABASE_URL if provided (common in deployment environments)
    DB_CONFIG = DATABASE_URL
elif SUPABASE_URL:
    # Build connection string from Supabase URL
    supabase_host = SUPABASE_URL.replace("https://", "").replace("http://", "")
    DB_CONFIG = {
        "host": f"db.{supabase_host.split('.')[0]}.supabase.co",
        "database": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "sslmode": "require"
    }
else:
    # Fallback to individual parameters
    DB_CONFIG = {
        "host": os.getenv("DB_HOST"),
        "database": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD"),
        "port": int(os.getenv("DB_PORT", 5432))
    }

def get_db_connection():
    """
    Create and return a database connection with retry logic
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if isinstance(DB_CONFIG, str):
                # DATABASE_URL string connection
                connection = psycopg2.connect(
                    DB_CONFIG,
                    cursor_factory = RealDictCursor
                )
            else:
                # Dictionary config
                connection = psycopg2.connect(
                    **DB_CONFIG,
                    cursor_factory = RealDictCursor
                )
            logger.info("Database connection established")
            return connection
        except psycopg2.OperationalError as e:
            retry_count += 1
            wait_time = 2 ** retry_count  # Exponential backoff
            logger.warning(f"Database connection failed, retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
            logger.error(f"Error: {e}")
            time.sleep(wait_time)
    
    logger.error("Failed to connect to database after multiple attempts")
    raise ConnectionError("Could not establish database connection")

def execute_query(query, params = None, fetch = True):
    """
    Execute a database query with proper connection handling
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query
        fetch (bool): Whether to fetch results (True) or just execute (False)
        
    Returns:
        list: Query results as a list of dictionaries, or None for non-SELECT queries
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            
            if fetch:
                results = cursor.fetchall()
                return [dict(row) for row in results]
            else:
                connection.commit()
                return None
                
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if connection:
            connection.close()

def insert_returning_id(table, data):
    """
    Insert a row into a table and return the generated ID
    
    Args:
        table (str): Table name
        data (dict): Column names and values to insert
        
    Returns:
        int: The ID of the newly inserted row
    """
    columns = ", ".join(data.keys())
    placeholders = ", ".join([f"%({key})s" for key in data.keys()])
    
    query = f"""
    INSERT INTO {table} ({columns})
    VALUES ({placeholders})
    RETURNING id
    """
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, data)
            result = cursor.fetchone()
            connection.commit()
            return result["id"]
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Insert error: {e}")
        raise
    finally:
        if connection:
            connection.close()

def bulk_insert(table, columns, values_list):
    """
    Perform a bulk insert operation
    
    Args:
        table (str): Table name
        columns (list): List of column names
        values_list (list): List of tuples containing values to insert
        
    Returns:
        int: Number of rows inserted
    """
    if not values_list:
        return 0
        
    columns_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    
    query = f"""
    INSERT INTO {table} ({columns_str})
    VALUES ({placeholders})
    ON CONFLICT DO NOTHING
    """
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.executemany(query, values_list)
            connection.commit()
            return cursor.rowcount
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Bulk insert error: {e}")
        raise
    finally:
        if connection:
            connection.close()