import os
import sys
import traceback

def main():
    db_url = os.environ.get("DATABASE_URL")
    print(f"Database URL: {db_url}")
    if db_url and db_url.startswith("postgresql"):
        try:
            import psycopg2
            print("Verifying PostgreSQL connection...")
            conn = psycopg2.connect(db_url)
            print(f"PostgreSQL connection verified! DSN: {conn.dsn}")
            conn.close()
        except Exception as e:
            print(f"PostgreSQL connection verification failed: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)

    print("Running Alembic upgrade head...")
    try:
        from alembic.config import Config
        from alembic import command

        cfg = Config("alembic.ini")
        if db_url:
            cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")
        print("Alembic upgrade head completed successfully!")
    except Exception as e:
        print(f"Alembic upgrade head failed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
