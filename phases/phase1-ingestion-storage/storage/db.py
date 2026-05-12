import sqlite3
import os

# We will place the database in the root folder for easy access across phases
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "pulse_data.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Initializes the SQLite schema for reviews and run_state."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            store TEXT NOT NULL,
            review_date TEXT NOT NULL,
            rating INTEGER,
            raw_text TEXT,
            scrubbed_text TEXT,
            cluster_id INTEGER,
            ingestion_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_state (
            run_id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            iso_week TEXT NOT NULL,
            status TEXT NOT NULL,
            doc_heading_id TEXT,
            email_message_id TEXT,
            error_log TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, iso_week)
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized at {os.path.abspath(DB_PATH)}")
