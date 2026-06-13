import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
IS_SQLITE = not DATABASE_URL

if not IS_SQLITE:
    import psycopg2
    from psycopg2.extras import DictCursor, execute_values

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        if 'cursor_factory' not in kwargs and not args:
            from psycopg2.extras import DictCursor
            kwargs['cursor_factory'] = DictCursor
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def execute(self, sql, params=None):
        from psycopg2.extras import DictCursor
        cursor = self._conn.cursor(cursor_factory=DictCursor)
        cursor.execute(sql, params)
        return cursor

def get_connection():
    """Returns a connection to the PostgreSQL database if DATABASE_URL is set, else local SQLite."""
    if IS_SQLITE:
        db_path = os.environ.get("PULSE_DB_PATH", "pulse.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        conn = psycopg2.connect(DATABASE_URL)
        return PostgresConnectionWrapper(conn)

def adapt_query(query: str) -> str:
    """Replaces %s placeholders with ? placeholders if using SQLite."""
    if IS_SQLITE:
        return query.replace("%s", "?")
    return query

def init_db():
    """Initializes the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    if IS_SQLITE:
        # SQLite compatibility schemas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                app_store_id TEXT,
                play_store_package TEXT,
                google_doc_id TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL REFERENCES products(id),
                store TEXT NOT NULL,
                review_date TEXT NOT NULL,
                rating INTEGER,
                raw_text TEXT,
                scrubbed_text TEXT,
                cluster_id INTEGER,
                ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL REFERENCES products(id),
                iso_week TEXT NOT NULL,
                status TEXT NOT NULL,
                doc_heading_id TEXT,
                email_message_id TEXT,
                error_log TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, iso_week)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                cluster_id INTEGER NOT NULL,
                theme_name TEXT NOT NULL,
                action_idea TEXT NOT NULL,
                quote TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_embeddings (
                review_id TEXT PRIMARY KEY,
                embedding BLOB
            );
        """)
    else:
        # PostgreSQL schemas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                app_store_id TEXT,
                play_store_package TEXT,
                google_doc_id TEXT
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL REFERENCES products(id),
                store TEXT NOT NULL,
                review_date TEXT NOT NULL,
                rating INTEGER,
                raw_text TEXT,
                scrubbed_text TEXT,
                cluster_id INTEGER,
                ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL REFERENCES products(id),
                iso_week TEXT NOT NULL,
                status TEXT NOT NULL,
                doc_heading_id TEXT,
                email_message_id TEXT,
                error_log TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, iso_week)
            );

            CREATE TABLE IF NOT EXISTS themes (
                id SERIAL PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                cluster_id INTEGER NOT NULL,
                theme_name TEXT NOT NULL,
                action_idea TEXT NOT NULL,
                quote TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS review_embeddings (
                review_id TEXT PRIMARY KEY,
                embedding BYTEA
            );
        """)

    conn.commit()
    cursor.close()
    conn.close()

def save_reviews(reviews: list[dict]):
    """Inserts reviews into the database, ignoring duplicates."""
    conn = get_connection()
    cursor = conn.cursor()
    
    values = [
        (r['id'], r['product_id'], r['store'], r['review_date'], r['rating'], r['raw_text'], r.get('scrubbed_text'))
        for r in reviews
    ]
    
    if values:
        if IS_SQLITE:
            query = """
                INSERT INTO reviews (id, product_id, store, review_date, rating, raw_text, scrubbed_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
            """
            cursor.executemany(query, values)
        else:
            query = """
                INSERT INTO reviews (id, product_id, store, review_date, rating, raw_text, scrubbed_text)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """
            execute_values(cursor, query, values)
        
    conn.commit()
    cursor.close()
    conn.close()

def get_reviews_to_embed(product_id: str) -> list[dict]:
    """Returns reviews that don't have embeddings yet."""
    conn = get_connection()
    if IS_SQLITE:
        cursor = conn.cursor()
        query = adapt_query("""
            SELECT r.id, r.raw_text, r.scrubbed_text FROM reviews r
            LEFT JOIN review_embeddings e ON r.id = e.review_id
            WHERE r.product_id = %s AND e.review_id IS NULL
        """)
        cursor.execute(query, (product_id,))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
    else:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("""
            SELECT r.id, r.raw_text, r.scrubbed_text FROM reviews r
            LEFT JOIN review_embeddings e ON r.id = e.review_id
            WHERE r.product_id = %s AND e.review_id IS NULL
        """, (product_id,))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        
    cursor.close()
    conn.close()
    return results

def save_embeddings(embeddings_data: list[tuple]):
    """Saves embeddings into the virtual table."""
    conn = get_connection()
    cursor = conn.cursor()
    
    processed_data = []
    for r_id, e in embeddings_data:
        if hasattr(e, 'tobytes'):
            e_bytes = e.tobytes()
        else:
            e_bytes = bytes(e)
        processed_data.append((r_id, e_bytes))
        
    if processed_data:
        if IS_SQLITE:
            query = """
                INSERT OR REPLACE INTO review_embeddings (review_id, embedding)
                VALUES (?, ?)
            """
            cursor.executemany(query, processed_data)
        else:
            query = """
                INSERT INTO review_embeddings (review_id, embedding)
                VALUES %s
                ON CONFLICT (review_id) DO UPDATE SET embedding = EXCLUDED.embedding
            """
            execute_values(cursor, query, processed_data)
        
    conn.commit()
    cursor.close()
    conn.close()

def update_review_clusters(cluster_data: list[tuple]):
    """Updates the cluster_id for reviews."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if IS_SQLITE:
        query = "UPDATE reviews SET cluster_id = ? WHERE id = ?"
        cursor.executemany(query, cluster_data)
    else:
        from psycopg2.extras import execute_batch
        query = "UPDATE reviews SET cluster_id = %s WHERE id = %s"
        execute_batch(cursor, query, cluster_data)
    
    conn.commit()
    cursor.close()
    conn.close()

def get_clustered_reviews(product_id: str) -> dict[int, list[dict]]:
    """Returns reviews grouped by cluster_id."""
    conn = get_connection()
    if IS_SQLITE:
        cursor = conn.cursor()
        query = adapt_query("SELECT * FROM reviews WHERE product_id = %s AND cluster_id IS NOT NULL")
        cursor.execute(query, (product_id,))
        rows = cursor.fetchall()
        rows_dict = [dict(row) for row in rows]
    else:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND cluster_id IS NOT NULL", (product_id,))
        rows = cursor.fetchall()
        rows_dict = [dict(row) for row in rows]
        
    cursor.close()
    conn.close()
    
    clusters = {}
    for row in rows_dict:
        c_id = row['cluster_id']
        if c_id not in clusters:
            clusters[c_id] = []
        clusters[c_id].append(row)
    return clusters

def save_themes(run_id: str, insights: list[dict]):
    """Saves the final themes generated by LLM."""
    conn = get_connection()
    cursor = conn.cursor()
    
    values = [
        (run_id, ins['cluster_id'], ins['theme_name'], ins['action_idea'], ins['quote'])
        for ins in insights
    ]
    
    if values:
        if IS_SQLITE:
            query = """
                INSERT INTO themes (run_id, cluster_id, theme_name, action_idea, quote)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.executemany(query, values)
        else:
            query = """
                INSERT INTO themes (run_id, cluster_id, theme_name, action_idea, quote)
                VALUES %s
            """
            execute_values(cursor, query, values)
        
    conn.commit()
    cursor.close()
    conn.close()

def update_theme(theme_id: int, theme_name: str, action_idea: str, quote: str):
    """Updates an existing theme's content."""
    conn = get_connection()
    cursor = conn.cursor()
    query = adapt_query("""
        UPDATE themes 
        SET theme_name = %s, action_idea = %s, quote = %s
        WHERE id = %s
    """)
    cursor.execute(query, (theme_name, action_idea, quote, theme_id))
    conn.commit()
    cursor.close()
    conn.close()

def get_themes(run_id: str) -> list[dict]:
    """Fetches themes for a given run_id."""
    conn = get_connection()
    if IS_SQLITE:
        cursor = conn.cursor()
        query = adapt_query("SELECT id, cluster_id, theme_name, action_idea, quote FROM themes WHERE run_id = %s")
        cursor.execute(query, (run_id,))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
    else:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("SELECT id, cluster_id, theme_name, action_idea, quote FROM themes WHERE run_id = %s", (run_id,))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        
    cursor.close()
    conn.close()
    return results
