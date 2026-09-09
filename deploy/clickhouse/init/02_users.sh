#!/bin/bash
set -euo pipefail

: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD is required}"
: "${CH_SYNC_PASSWORD:?CH_SYNC_PASSWORD is required}"
: "${CH_AGENT_PASSWORD:?CH_AGENT_PASSWORD is required}"
: "${CH_VMS_PASSWORD:?CH_VMS_PASSWORD is required}"

chc() {
  clickhouse-client --user default --password "$CLICKHOUSE_PASSWORD" --multiquery
}

chc <<SQL
CREATE SETTINGS PROFILE IF NOT EXISTS agent_ro_profile
SETTINGS
  readonly = 1,
  max_execution_time = 30,
  max_result_rows = 5000,
  result_overflow_mode = 'break',
  max_memory_usage = 4294967296,
  max_rows_to_read = 2000000000;

CREATE SETTINGS PROFILE IF NOT EXISTS vms_ro_profile
SETTINGS
  readonly = 1,
  max_execution_time = 30,
  max_result_rows = 100000,
  result_overflow_mode = 'break',
  max_memory_usage = 4294967296,
  max_rows_to_read = 2000000000;

CREATE USER IF NOT EXISTS vms_sync IDENTIFIED WITH sha256_password BY '${CH_SYNC_PASSWORD}';
CREATE USER IF NOT EXISTS agent_ro IDENTIFIED WITH sha256_password BY '${CH_AGENT_PASSWORD}'
  SETTINGS PROFILE agent_ro_profile;
CREATE USER IF NOT EXISTS vms_ro IDENTIFIED WITH sha256_password BY '${CH_VMS_PASSWORD}'
  SETTINGS PROFILE vms_ro_profile;

GRANT INSERT, SELECT ON vms.* TO vms_sync;

GRANT SELECT ON vms.* TO agent_ro;
GRANT SELECT ON system.databases TO agent_ro;
GRANT SELECT ON system.tables TO agent_ro;
GRANT SELECT ON system.columns TO agent_ro;
GRANT SHOW DATABASES ON *.* TO agent_ro;
GRANT SHOW TABLES ON vms.* TO agent_ro;
GRANT SHOW COLUMNS ON vms.* TO agent_ro;

GRANT SELECT ON vms.* TO vms_ro;
GRANT SELECT ON system.databases TO vms_ro;
GRANT SELECT ON system.tables TO vms_ro;
GRANT SELECT ON system.columns TO vms_ro;
GRANT SHOW DATABASES ON *.* TO vms_ro;
GRANT SHOW TABLES ON vms.* TO vms_ro;
GRANT SHOW COLUMNS ON vms.* TO vms_ro;

CREATE QUOTA IF NOT EXISTS agent_ro_quota
  KEYED BY user_name
  FOR INTERVAL 1 HOUR MAX queries = 600
  TO agent_ro;
SQL
