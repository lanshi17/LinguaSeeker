# SQL Scripts

This directory stores SQL assets used by `database/scripts/dbctl.sh`.

## Files

- `init_database_schema.sql`: reference schema SQL (kept for audit/reference)
- `seed_data.sql`: seed records (safe insert style)
- `cleanup_orphan_records.sql`: cleanup script for orphan/redundant records

## Usage

Use the unified CLI from repository root:

```bash
# initialize schema and apply seed (preferred)
./database/scripts/dbctl.sh init

# run cleanup SQL
./database/scripts/dbctl.sh cleanup
```

If you need direct execution:

```bash
psql -h <host> -p <port> -U <user> -d <database> -f database/sql/cleanup_orphan_records.sql
```
