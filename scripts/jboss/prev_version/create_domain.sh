#!/usr/bin/env bash
# ==============================================================================
# create_domain.sh   (WildFly managed domain)
# WildFly equivalent of the WebLogic create_domain.py:
#
#   WebLogic                      WildFly managed domain
#   ---------------------------   ---------------------------------------------
#   cluster app_cluster        -> server group app_cluster (profile full-ha)
#   managed server my_server   -> server-config my_server in group app_cluster
#   scottDS targeted to cluster-> datasource scottDS in profile full-ha
#   JMS module/queue           -> jms-queue scottQueue in profile full-ha
#   connection factory jms/CF  -> java:/JmsXA (already in full-ha)
#
# The sample servers (server-one/two/three) and groups (main-server-group,
# other-server-group) are removed unless REMOVE_SAMPLES=false.
#
# Modes, chosen automatically:
#   - domain stopped : edits domain.xml/host.xml offline (embedded host controller)
#   - domain running : applies the changes online, then reloads the host
#
# Usage:
#   DB_PW='tiger' OJDBC_JAR=/path/to/ojdbc11.jar ./create_domain.sh
#
# Optional: DB_URL, DB_USER, MSG_CLUSTER_PW, REMOVE_SAMPLES, HOST_NAME, and the
# topology settings in wf_domain_common.sh (SERVER_GROUP, SERVERS, PROFILE, ...)
# ==============================================================================
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/wf_domain_common.sh"

DB_URL="${DB_URL:-jdbc:oracle:thin:@//oracle-ai-scott:1521/FREEPDB1}"
DB_USER="${DB_USER:-scott}"
DB_PW="${DB_PW:-}"
OJDBC_JAR="${OJDBC_JAR:-}"
MSG_CLUSTER_PW="${MSG_CLUSTER_PW:-}"
REMOVE_SAMPLES="${REMOVE_SAMPLES:-true}"

MODULE_NAME="com.oracle.ojdbc"
MODULE_DIR="$JBOSS_HOME/modules/com/oracle/ojdbc/main"
P="/profile=$PROFILE"

[ -n "$DB_PW" ] || die "DB_PW is not set. Usage: DB_PW='tiger' OJDBC_JAR=/path/ojdbc11.jar $0"
for v in "$DB_PW" "$MSG_CLUSTER_PW"; do
    case "$v" in *\"*|*\\*) die "Passwords must not contain double quotes or backslashes";; esac
done

# ------------------------------------------------------------------------------
# 1. Oracle JDBC driver module
#    In a multi-host domain, this module must exist on EVERY host.
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
# 2. Management user (needed for the console and for remote CLI access)
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
LT="$(launch_type)"
case "$LT" in
    DOMAIN)
        MODE=online
        echo ">>> Domain Controller is running: applying configuration online." ;;
    STANDALONE)
        die "A STANDALONE server is running on $CONTROLLER. Stop it, or use the standalone scripts." ;;
    *)
        MODE=offline
        [ -f "$CONFIG_DIR/$DOMAIN_CONFIG" ] || die "$CONFIG_DIR/$DOMAIN_CONFIG not found"
        [ -f "$CONFIG_DIR/$HOST_CONFIG" ]   || die "$CONFIG_DIR/$HOST_CONFIG not found"
        echo ">>> Domain is not running: editing $DOMAIN_CONFIG and $HOST_CONFIG offline." ;;
esac

HOST="$(detect_host "$MODE")"
[ -n "$HOST" ] || die "Could not determine the host controller name. Set HOST_NAME."
echo ">>> Host controller: $HOST"

# ------------------------------------------------------------------------------
# 4. Build the CLI script (temp file readable only by this user: it holds passwords)
# ------------------------------------------------------------------------------
CLI_FILE="$(mktemp)"
chmod 600 "$CLI_FILE"
trap 'rm -f "$CLI_FILE"' EXIT

{
if [ "$MODE" = offline ]; then
    echo "embed-host-controller --domain-config=$DOMAIN_CONFIG --host-config=$HOST_CONFIG --std-out=discard"
fi

cat << CLICMDS
# ---------------- Host: listen on all interfaces unless -b is given ----------
/host=$HOST/interface=public:write-attribute(name=inet-address,value="\${jboss.bind.address:0.0.0.0}")

# ---------------- Profile $PROFILE: Oracle JDBC driver -----------------------
if (outcome != success) of $P/subsystem=datasources/jdbc-driver=oracle:read-resource
    $P/subsystem=datasources/jdbc-driver=oracle:add(driver-name=oracle,driver-module-name=$MODULE_NAME,driver-class-name=oracle.jdbc.OracleDriver,driver-xa-datasource-class-name=oracle.jdbc.xa.client.OracleXADataSource)
end-if

# ---------------- Profile $PROFILE: DataSource scottDS ------------------------
if (outcome == success) of $P/subsystem=datasources/data-source=scottDS:read-resource
    $P/subsystem=datasources/data-source=scottDS:write-attribute(name=connection-url,value="$DB_URL")
    $P/subsystem=datasources/data-source=scottDS:write-attribute(name=user-name,value="$DB_USER")
    $P/subsystem=datasources/data-source=scottDS:write-attribute(name=password,value="$DB_PW")
else
    $P/subsystem=datasources/data-source=scottDS:add(jndi-name="java:jboss/datasources/scottDS",driver-name=oracle,connection-url="$DB_URL",user-name="$DB_USER",password="$DB_PW",min-pool-size=1,max-pool-size=20,validate-on-match=true,background-validation=false,valid-connection-checker-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleValidConnectionChecker,exception-sorter-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleExceptionSorter,stale-connection-checker-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleStaleConnectionChecker,enabled=true)
end-if

# ---------------- Profile $PROFILE: JMS queue scottQueue ---------------------
if (outcome != success) of $P/subsystem=messaging-activemq/server=default/jms-queue=scottQueue:read-resource
    $P/subsystem=messaging-activemq/server=default/jms-queue=scottQueue:add(entries=["java:/jms/queue/scottQueue","java:jboss/exported/jms/queue/scottQueue"],durable=true)
end-if
CLICMDS

if [ -n "$MSG_CLUSTER_PW" ]; then
    echo "$P/subsystem=messaging-activemq/server=default:write-attribute(name=cluster-password,value=\"$MSG_CLUSTER_PW\")"
fi

# ---------------- Remove the sample topology ----------------------------------
if [ "$REMOVE_SAMPLES" = true ]; then
    for s in server-one server-two server-three; do
        echo "if (outcome == success) of /host=$HOST/server-config=$s:read-resource"
        if [ "$MODE" = online ]; then
            echo "    /host=$HOST/server-config=$s:stop(blocking=true)"
        fi
        echo "    /host=$HOST/server-config=$s:remove"
        echo "end-if"
    done
    for g in main-server-group other-server-group; do
        echo "if (outcome == success) of /server-group=$g:read-resource"
        echo "    /server-group=$g:remove"
        echo "end-if"
    done
fi

# ---------------- Server group = WebLogic cluster ----------------------------
cat << CLICMDS
if (outcome != success) of /server-group=$SERVER_GROUP:read-resource
    /server-group=$SERVER_GROUP:add(profile=$PROFILE,socket-binding-group=$SOCKET_BINDING_GROUP)
end-if
if (outcome != success) of /server-group=$SERVER_GROUP/jvm=default:read-resource
    /server-group=$SERVER_GROUP/jvm=default:add(heap-size=256m,max-heap-size=1024m)
end-if
CLICMDS

# ---------------- Servers = WebLogic managed servers -------------------------
i=0
for s in $(server_list); do
    offset=$((BASE_PORT_OFFSET + i * PORT_OFFSET_STEP))
    echo "if (outcome != success) of /host=$HOST/server-config=$s:read-resource"
    echo "    /host=$HOST/server-config=$s:add(group=$SERVER_GROUP,socket-binding-port-offset=$offset,auto-start=true)"
    echo "end-if"
    i=$((i + 1))
done

if [ "$MODE" = offline ]; then
    echo "stop-embedded-host-controller"
else
    # Reload the host controller; its servers are restarted with the new config
    echo "reload --host=$HOST"
fi
} > "$CLI_FILE"

# ------------------------------------------------------------------------------
# 5. Apply
# ------------------------------------------------------------------------------
if [ "$MODE" = online ]; then
    cli_online_file "$CLI_FILE"
else
    "$CLI" --file="$CLI_FILE"
fi

echo ""
echo ">>> Managed domain configured ($MODE)."
echo ">>>   Server group : $SERVER_GROUP (profile $PROFILE, sockets $SOCKET_BINDING_GROUP)"
i=0
for s in $(server_list); do
    offset=$((BASE_PORT_OFFSET + i * PORT_OFFSET_STEP))
    echo ">>>   Server       : $s on host $HOST, HTTP port $((8080 + offset))"
    i=$((i + 1))
done
echo ">>>   Resources    : java:jboss/datasources/scottDS, java:/jms/queue/scottQueue, java:/JmsXA"
[ -z "$MSG_CLUSTER_PW" ] && echo ">>> NOTE: MSG_CLUSTER_PW not set; the messaging cluster uses the default password (WildFly logs a warning)."
exit 0