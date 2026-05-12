import os
import psycopg2
from psycopg2.extras import DictCursor, execute_values

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    """Returns a connection to the PostgreSQL database."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Please set it to your Supabase connection string.")
    
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Initializes the PostgreSQL database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create tables
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
        
        -- Using BYTEA instead of vec0 for embeddings since we just store and retrieve them
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
    
    query = """
        INSERT INTO reviews (id, product_id, store, review_date, rating, raw_text, scrubbed_text)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """
    
    values = [
        (r['id'], r['product_id'], r['store'], r['review_date'], r['rating'], r['raw_text'], r.get('scrubbed_text'))
        for r in reviews
    ]
    
    if values:
        execute_values(cursor, query, values)
        
    conn.commit()
    cursor.close()
    conn.close()

def get_reviews_to_embed(product_id: str) -> list[dict]:
    """Returns reviews that don't have embeddings yet."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute("""
        SELECT r.id, r.raw_text, r.scrubbed_text FROM reviews r
        LEFT JOIN review_embeddings e ON r.id = e.review_id
        WHERE r.product_id = %s AND e.review_id IS NULL
    """, (product_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def save_embeddings(embeddings_data: list[tuple]):
    """Saves embeddings into the virtual table."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO review_embeddings (review_id, embedding)
        VALUES %s
        ON CONFLICT (review_id) DO UPDATE SET embedding = EXCLUDED.embedding
    """
    
    if embeddings_data:
        execute_values(cursor, query, embeddings_data)
        
    conn.commit()
    cursor.close()
    conn.close()

def update_review_clusters(cluster_data: list[tuple]):
    """Updates the cluster_id for reviews."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # execute_values is faster for bulk updates if we use a temp table or FROM VALUES
    # But since execute_batch is also available, let's just use standard executemany
    from psycopg2.extras import execute_batch
    query = "UPDATE reviews SET cluster_id = %s WHERE id = %s"
    execute_batch(cursor, query, cluster_data)
    
    conn.commit()
    cursor.close()
    conn.close()

def get_clustered_reviews(product_id: str) -> dict[int, list[dict]]:
    """Returns reviews grouped by cluster_id."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute("SELECT * FROM reviews WHERE product_id = %s AND cluster_id IS NOT NULL", (product_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    clusters = {}
    for row in rows:
        c_id = row['cluster_id']
        if c_id not in clusters:
            clusters[c_id] = []
        clusters[c_id].append(dict(row))
    return clusters

def save_themes(run_id: str, insights: list[dict]):
    """Saves the final themes generated by LLM."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO themes (run_id, cluster_id, theme_name, action_idea, quote)
        VALUES %s
    """
    values = [
        (run_id, ins['cluster_id'], ins['theme_name'], ins['action_idea'], ins['quote'])
        for ins in insights
    ]
    
    if values:
        execute_values(cursor, query, values)
        
    conn.commit()
    cursor.close()
    conn.close()

def update_theme(theme_id: int, theme_name: str, action_idea: str, quote: str):
    """Updates an existing theme's content."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE themes 
        SET theme_name = %s, action_idea = %s, quote = %s
        WHERE id = %s
    """, (theme_name, action_idea, quote, theme_id))
    conn.commit()
    cursor.close()
    conn.close()

def get_themes(run_id: str) -> list[dict]:
    """Fetches themes for a given run_id."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute("SELECT id, cluster_id, theme_name, action_idea, quote FROM themes WHERE run_id = %s", (run_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]
