# UN Fixture Restore Workflow

The `UN` competitive regression fixture lives in two files:

- `un_guild_fixture.sql.gz`: raw shared-schema rows for the `un` guild
- `un_guild_snapshot.json`: expected regression anchors after aggregates are
  recomputed from the raw rows

## Run the regression test

The test suite does not need MariaDB for this fixture. It restores the compressed
SQL directly into a temporary SQLite database and then rebuilds the guild
aggregates:

```bash
pytest -q tests/test_un_guild_regression.py
```

## Restore into an empty MariaDB database

If the original MariaDB container is gone, bootstrap the shared schema in a new
database first, then import the checked-in dump.

Bootstrap the schema with the same config used by the site:

```bash
python - <<'PY'
from src.core.config import load_config
from src.data.database import init_shared_database
from src.data.shared.schema import bootstrap_shared_schema

config = load_config("config.yml")
database = init_shared_database(config.mariadb)
bootstrap_shared_schema(database)
print("shared schema ready")
PY
```

Restore the fixture rows:

```bash
gunzip -c tests/fixtures/un_guild_fixture.sql.gz | \
  mysql \
    --host="$MARIADB_HOST" \
    --port="$MARIADB_PORT" \
    --user="$MARIADB_USER" \
    --password="$MARIADB_PASSWORD" \
    "$MARIADB_DATABASE"
```

After the import, rebuild aggregates from the raw observations before checking
leaderboard output:

```bash
pytest -q tests/test_un_guild_regression.py
```
