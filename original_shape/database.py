import os
import sqlite3

class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "blackboard.db")
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self, schema_path: str = None):
        if schema_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(base_dir, "schema.sql")
            
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found at: {schema_path}")
        
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        conn.close()
        print(f"Database initialized at '{self.db_path}' using '{schema_path}'.")

    def log_run(self, agent_name: str, inputs: str, outputs: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runs (agent_name, input, output) VALUES (?, ?, ?)",
            (agent_name, inputs, outputs)
        )
        conn.commit()
        conn.close()

    def get_runs(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, timestamp, agent_name, input, output FROM runs ORDER BY id DESC")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()
        return rows
