# Tasks

## 1. Compose configuration

- [x] 1.1 Add an env-backed `--max_allowed_packet` server flag to the MariaDB
  service in `docker-compose.yml`.
- [x] 1.2 Document `MARIADB_MAX_ALLOWED_PACKET` in `.env.example`.

## 2. Verification

- [x] 2.1 Verify the rendered Compose config includes the packet-size flag.
- [x] 2.2 Restart the local MariaDB container and confirm the server variable
  resolves to the configured value.
