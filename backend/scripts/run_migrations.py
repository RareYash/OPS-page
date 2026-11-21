import os
import sys
import traceback

def main():
    db_url = os.environ.get("DATABASE_URL")
    print(f"::notice::Database URL is {db_url}")
    if db_url and db_url.startswith("postgresql"):
        try:
            import psycopg2
            print("Verifying PostgreSQL connection...")
            conn = psycopg2.connect(db_url)
            print(f"::notice::PostgreSQL connection verified! DSN: {conn.dsn}")
            conn.close()
        except Exception as e:
            print(f"::error::PostgreSQL connection verification failed: {e}")
            for line in traceback.format_exc().splitlines():
                print(f"::error::{line}")
            sys.exit(1)

    print("Running Alembic upgrade head...")
    try:
        from alembic.config import Config
        from alembic import command

        cfg = Config("alembic.ini")
        if db_url:
            cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")
        print("::notice::Alembic upgrade head completed successfully!")
    except Exception as e:
        print(f"::error::Alembic upgrade head failed: {e}")
        for line in traceback.format_exc().splitlines():
            print(f"::error::{line}")
        sys.exit(1)

if __name__ == "__main__":
    main()
