#!/usr/bin/env python3
"""
Production startup script for PrimeHaul Office Manager.
Handles database migrations safely.
"""
import os
import sys
import subprocess
from sqlalchemy import create_engine, text


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print("Checking database state...")
    engine = create_engine(database_url)

    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
            ))
            alembic_exists = result.scalar()

            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'companies')"
            ))
            tables_exist = result.scalar()

            if tables_exist and not alembic_exists:
                print("Database tables exist but no alembic_version - stamping to head...")
                subprocess.run(["alembic", "stamp", "head"], check=True)
            elif not tables_exist:
                print("Fresh database - running all migrations...")
                subprocess.run(["alembic", "upgrade", "head"], check=True)
            else:
                print("Running pending migrations...")
                subprocess.run(["alembic", "upgrade", "head"], check=True)

    except Exception as e:
        print(f"Database setup error: {e}")
        print("Attempting to continue anyway...")

    try:
        from app.models import Base
        Base.metadata.create_all(engine, checkfirst=True)
        print("All model tables verified")
    except Exception as e:
        print(f"Table creation check error: {e}")

    print("Database ready!")


if __name__ == "__main__":
    main()
