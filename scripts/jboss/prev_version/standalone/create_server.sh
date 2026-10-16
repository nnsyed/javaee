#!/usr/bin/env bash
# ==============================================================================
# create_server.sh
# WildFly equivalent of create_domain.py. Configures the standalone-full profile with:
#   - Oracle JDBC driver module (com.oracle.ojdbc)
#   - DataSource scottDS      -> java:jboss/datasources/scottDS
#   - JMS queue scottQueue    -> java:/jms/queue/scottQueue
#   - public interface on 0.0.0.0 (like ListenAddress 0.0.0.0 in WebLogic)
# The connection factory java:/JmsXA already exists in standalone-full.
#
# Works in two modes, chosen automatically:
#   - server stopped : edits the config offline with an embedded server
#                      (like WLST offline)
#   - server running : applies the changes online, then reloads the server
#
# Usage:
#   DB_PW='tiger' OJDBC_JAR=/path/to/ojdbc11.jar ./create_server.sh
#
# Optional environment variables:
#   JBOSS_HOME     /opt/jboss/wildfly (default)
#   SERVER_CONFIG  standalone-full.xml (default; JMS needs a "full" profile)
#   CONTROLLER     localhost:9990 (management endpoint, for online mode)
#   MGMT_USER / MGMT_PW   management user to create, and to authenticate with
#   DB_URL         jdbc:oracle:thin:@//oracle-ai-scott:1521/FREEPDB1 (default)
#   DB_USER        scott (default)
# ==============================================================================
set -euo pipefail

JBOSS_HOME="${JBOSS_HOME:-/opt/jboss/wildfly}"
CLI="$JBOSS_HOME/bin/jboss-cli.sh"
SERVER_CONFIG="${SERVER_CONFIG:-standalone-full.xml}"
CONTROLLER="${CONTROLLER:-localhost:9990}"
DB_URL="${DB_URL:-jdbc:oracle:thin:@//oracle-ai-scott:1521/FREEPDB1}"
DB_USER="${DB_USER:-scott}"
DB_PW="${DB_PW:-}"
OJDBC_JAR="${OJDBC_JAR:-/opt/jboss/wildfly/scripts/db/ojdbc11-23.26.3.0.0.jar}"
MGMT_USER="${MGMT_USER:-admin}"
MGMT_PW="${MGMT_PW:-Welcome1}"

MODULE_NAME="com.oracle.ojdbc"
MODULE_DIR="$JBOSS_HOME/modules/com/oracle/ojdbc/main"

die() { echo "ERROR: $*" >&2; exit 1; }

[ -x "$CLI" ] || die "jboss-cli.sh not found at $CLI (set JBOSS_HOME)"
[ -n "$DB_PW" ] || die "DB_PW is not set. Usage: DB_PW='tiger' OJDBC_JAR=/path/ojdbc11.jar $0"
case "$DB_PW" in *\"*|*\\*) die "DB_PW must not contain double quotes or backslashes";; esac

AUTH_ARGS=()
if [ -n "$MGMT_USER" ]; then
    AUTH_ARGS=(--user="$MGMT_USER" --password="$MGMT_PW")
fi

# ------------------------------------------------------------------------------
# 1. Oracle JDBC driver module (a filesystem change, works with or without a server)
# ------------------------------------------------------------------------------
if [ -f "$MODULE_DIR/module.xml" ]; then
    echo ">>> JDBC module $MODULE_NAME already exists, keeping it."
else
    [ -n "$OJDBC_JAR" ] || die "OJDBC_JAR is not set and module $MODULE_NAME does not exist yet."
    [ -f "$OJDBC_JAR" ] || die "OJDBC_JAR file not found: $OJDBC_JAR"
    JAR_NAME="$(basename "$OJDBC_JAR")"
    echo ">>> Creating JDBC module $MODULE_NAME from $OJDBC_JAR"
    mkdir -p "$MODULE_DIR"
    cp "$OJDBC_JAR" "$MODULE_DIR/"
    cat > "$MODULE_DIR/module.xml" << MODXML
<?xml version="1.0" encoding="UTF-8"?>
<module xmlns="urn:jboss:module:1.5" name="$MODULE_NAME">
    <resources>
        <resource-root path="$JAR_NAME"/>
    </resources>
    <dependencies>
        <module name="javax.api"/>
    </dependencies>
</module>
MODXML
fi

# ------------------------------------------------------------------------------
# 2. Management user (optional; needed for the web console or remote CLI)
# ------------------------------------------------------------------------------
if [ -n "$MGMT_USER" ]; then
    [ -n "$MGMT_PW" ] || die "MGMT_USER is set but MGMT_PW is not."
    echo ">>> Adding management user $MGMT_USER"
    "$JBOSS_HOME/bin/add-user.sh" -u "$MGMT_USER" -p "$MGMT_PW" -s \
        || echo ">>> WARNING: add-user.sh failed (the user may already exist)."
fi

# ------------------------------------------------------------------------------
# 3. Online or offline?
# ------------------------------------------------------------------------------
if "$CLI" -c --controller="$CONTROLLER" "${AUTH_ARGS[@]}" \
        --command=":read-attribute(name=server-state)" >/dev/null 2>&1; then
    MODE=online
    echo ">>> WildFly is running: applying configuration online."
    "$CLI" -c --controller="$CONTROLLER" "${AUTH_ARGS[@]}" \
        --command="/subsystem=messaging-activemq:read-resource" >/dev/null 2>&1 \
        || die "The running server has no messaging subsystem. Start it with -c standalone-full.xml."
else
    MODE=offline
    [ -f "$JBOSS_HOME/standalone/configuration/$SERVER_CONFIG" ] \
        || die "Config $SERVER_CONFIG not found in $JBOSS_HOME/standalone/configuration"
    echo ">>> WildFly is not running: editing $SERVER_CONFIG offline."
fi

# ------------------------------------------------------------------------------
# 4. Build the CLI script (temp file, readable only by this user: it holds DB_PW)
# ------------------------------------------------------------------------------
CLI_FILE="$(mktemp)"
chmod 600 "$CLI_FILE"
trap 'rm -f "$CLI_FILE"' EXIT

{
if [ "$MODE" = offline ]; then
    echo "embed-server --server-config=$SERVER_CONFIG --std-out=discard"
fi

cat << CLICMDS
# --- Listen on all interfaces unless -b is given at startup
/interface=public:write-attribute(name=inet-address,value="\${jboss.bind.address:0.0.0.0}")

# --- Oracle JDBC driver
if (outcome != success) of /subsystem=datasources/jdbc-driver=oracle:read-resource
    /subsystem=datasources/jdbc-driver=oracle:add(driver-name=oracle,driver-module-name=$MODULE_NAME,driver-class-name=oracle.jdbc.OracleDriver,driver-xa-datasource-class-name=oracle.jdbc.xa.client.OracleXADataSource)
end-if

# --- DataSource scottDS (recreated so URL/user/password changes are applied)
if (outcome == success) of /subsystem=datasources/data-source=scottDS:read-resource
    data-source remove --name=scottDS
end-if
data-source add --name=scottDS --jndi-name=java:jboss/datasources/scottDS --driver-name=oracle --connection-url="$DB_URL" --user-name="$DB_USER" --password="$DB_PW" --min-pool-size=1 --max-pool-size=20 --validate-on-match=true --background-validation=false --valid-connection-checker-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleValidConnectionChecker --exception-sorter-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleExceptionSorter --stale-connection-checker-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleStaleConnectionChecker --enabled=true

# --- JMS queue scottQueue (kept if it exists, so queued messages survive)
if (outcome != success) of /subsystem=messaging-activemq/server=default/jms-queue=scottQueue:read-resource
    jms-queue add --queue-address=scottQueue --entries=java:/jms/queue/scottQueue,java:jboss/exported/jms/queue/scottQueue --durable=true
end-if
CLICMDS

if [ "$MODE" = offline ]; then
    echo "stop-embedded-server"
else
    echo "reload"
fi
} > "$CLI_FILE"

# ------------------------------------------------------------------------------
# 5. Apply
# ------------------------------------------------------------------------------
if [ "$MODE" = online ]; then
    "$CLI" -c --controller="$CONTROLLER" "${AUTH_ARGS[@]}" --file="$CLI_FILE"
else
    "$CLI" --file="$CLI_FILE"
fi

echo ">>> WildFly configured ($MODE): scottDS, scottQueue, Oracle driver."
if [ "$MODE" = offline ]; then
    echo ">>> Start it with: ./start_server.sh  (uses $SERVER_CONFIG)"
fi