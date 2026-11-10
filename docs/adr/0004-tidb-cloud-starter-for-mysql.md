# TiDB Cloud Starter as the MySQL-compatible database

The developer chose MySQL. Render offers no MySQL (only Postgres, whose free tier is deleted after 30 days), and Aiven stopped creating free MySQL services on 6 November 2026. TiDB Cloud Starter is free with no time limit, speaks the MySQL protocol and SQL, and its free allowance (5 GiB storage, 50M request units per month per instance) comfortably covers 100,000 Tickets a day.

## Consequences

- TiDB differs from MySQL in small ways (notably locking behaviour and auto-increment ID allocation). Uniqueness and idempotency are enforced with unique constraints rather than relying on lock or ID ordering.
- Connections must use TLS.
