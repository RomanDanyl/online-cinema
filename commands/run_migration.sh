##!/bin/sh
#
## SQLAlchemy migrate
#ALEMBIC_CONFIG="/usr/src/alembic/alembic.ini"
#MIGRATIONS_DIR="/usr/src/fastapi/database/migrations/versions"
#
#echo "Checking for changes before generating a migration..."
#
## Ensure the migrations folder exists
#if [ ! -d "$MIGRATIONS_DIR" ]; then
#    echo "Migrations folder does not exist. Creating it..."
#    mkdir -p "$MIGRATIONS_DIR"
#fi
#
## Check if the alembic_version table exists in the database
#export PGPASSWORD="$POSTGRES_PASSWORD"
#
#if ! psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt" | grep -q "alembic_version"; then
#    echo "Alembic version table not found. Applying all migrations..."
#
#    # Check if there are existing migration files
#    if [ -z "$(ls -A "$MIGRATIONS_DIR")" ]; then
#        echo "No migration files found. Generating initial migration..."
#        alembic -c $ALEMBIC_CONFIG revision --autogenerate -m "initial migration"
#    fi
#
#    echo "Applying all migrations..."
#    alembic -c $ALEMBIC_CONFIG upgrade head
#
#    # Run database saver script only if alembic_version table was just created
#    echo "Running database saver script..."
#    python -m database.populate
#    echo "Database saver script completed."
#
#    exit 0
#fi
#
## Generate temporary migration
#if ! alembic -c $ALEMBIC_CONFIG revision --autogenerate -m "temp_migration"; then
#    echo "Error generating migration. Exiting."
#    exit 1
#fi
#
## Find the last created migration file
#LAST_MIGRATION=$(find "$MIGRATIONS_DIR" -type f -printf '%T+ %p\n' | sort | tail -n 1 | awk '{print $2}')
#
## Show migration content
#echo "Generated migration content:"
#cat "$LAST_MIGRATION"
#
## Check if the migration contains real changes
#if grep -qE '^\s*pass\s*$' "$LAST_MIGRATION"; then
#    echo "No changes detected. Deleting temporary migration."
#    rm "$LAST_MIGRATION"
#else
#    echo "Changes detected. Applying migration."
#    alembic -c $ALEMBIC_CONFIG upgrade head
#fi
#
## Run database saver script
#echo "Running database saver script..."
#python -m database.populate
#echo "Database saver script completed."


#!/bin/sh
set -e

# Alembic configuration
ALEMBIC_CONFIG="/usr/src/alembic/alembic.ini"
MIGRATIONS_DIR="/usr/src/fastapi/database/migrations/versions"

echo "Checking for changes before generating a migration..."

# Ensure the migrations folder exists
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "Migrations folder does not exist. Creating it..."
    mkdir -p "$MIGRATIONS_DIR"
fi

# Configure Postgres connection using environment variables
PGHOST="${POSTGRES_HOST:-db}"  # default to 'db' if POSTGRES_HOST is not set
PGUSER="${POSTGRES_USER}"
PGDATABASE="${POSTGRES_DB}"
PGPASSWORD="${POSTGRES_PASSWORD}"
export PGPASSWORD

echo "Checking if alembic_version table exists in DB '${PGDATABASE}'..."

# If the alembic_version table does NOT exist -> initial migration flow
if ! psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c "\dt" | grep -q "alembic_version"; then
    echo "Alembic version table not found."

    # If there are no migration files yet -> generate initial migration
    if [ -z "$(ls -A "$MIGRATIONS_DIR")" ]; then
        echo "No migration files found. Generating initial migration..."
        alembic -c "$ALEMBIC_CONFIG" revision --autogenerate -m "initial migration"
    else
        echo "Migration files already exist. Will apply them."
    fi

    echo "Applying all migrations (upgrade head)..."
    alembic -c "$ALEMBIC_CONFIG" upgrade head
    echo "Initial migrations applied."
    exit 0
fi

# If alembic is already configured -> first ensure DB is up-to-date
echo "alembic_version exists. Making sure the database is up-to-date (upgrade head)..."
if ! alembic -c "$ALEMBIC_CONFIG" upgrade head; then
    echo "Failed to upgrade database to head. Exiting."
    exit 1
fi

# Now it is safe to generate a new temporary migration
echo "Generating temporary migration..."
if ! alembic -c "$ALEMBIC_CONFIG" revision --autogenerate -m "temp_migration"; then
    echo "Error generating migration (even after upgrade head). Exiting."
    exit 1
fi

# Find the most recently created migration file
LAST_MIGRATION=$(find "$MIGRATIONS_DIR" -type f -printf '%T+ %p\n' | sort | tail -n 1 | awk '{print $2}')

echo "Generated migration content:"
cat "$LAST_MIGRATION"

# If the migration only contains 'pass' -> no schema changes -> delete it
if grep -qE '^\s*pass\s*$' "$LAST_MIGRATION"; then
    echo "No changes detected. Deleting temporary migration."
    rm "$LAST_MIGRATION"
else
    echo "Changes detected. Applying migration (upgrade head)..."
    alembic -c "$ALEMBIC_CONFIG" upgrade head
fi

echo "Migrations done."
