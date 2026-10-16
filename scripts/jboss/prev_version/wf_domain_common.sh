# ==============================================================================
# wf_domain_common.sh
# Shared settings and helpers for the WildFly managed-domain scripts.
# Sourced by create_domain.sh, start_domain.sh and deploy_apps.sh.
# Every value can be overridden with an environment variable.
# ==============================================================================

JBOSS_HOME="${JBOSS_HOME:-/opt/jboss/wildfly}"
CLI="$JBOSS_HOME/bin/jboss-cli.sh"
CONTROLLER="${CONTROLLER:-localhost:9990}"          # Domain Controller management endpoint

DOMAIN_CONFIG="${DOMAIN_CONFIG:-domain.xml}"
HOST_CONFIG="${HOST_CONFIG:-host.xml}"
CONFIG_DIR="$JBOSS_HOME/domain/configuration"

# Topology, named like the WebLogic domain
SERVER_GROUP="${SERVER_GROUP:-app_cluster}"         # WebLogic cluster
PROFILE="${PROFILE:-full-ha}"                       # full = JMS, ha = clustering
SOCKET_BINDING_GROUP="${SOCKET_BINDING_GROUP:-full-ha-sockets}"
SERVERS="${SERVERS:-my_server}"                     # managed servers, comma or space separated
BASE_PORT_OFFSET="${BASE_PORT_OFFSET:-0}"           # first server: 8080
PORT_OFFSET_STEP="${PORT_OFFSET_STEP:-100}"         # next ones: 8180, 8280, ...

MGMT_USER="${MGMT_USER:-}"
MGMT_PW="${MGMT_PW:-}"
AUTH_ARGS=()
if [ -n "$MGMT_USER" ]; then
    AUTH_ARGS=(--user="$MGMT_USER" --password="$MGMT_PW")
fi

die() { echo "ERROR: $*" >&2; exit 1; }

[ -x "$CLI" ] || die "jboss-cli.sh not found at $CLI (set JBOSS_HOME)"

# Run one CLI command against the running Domain Controller
cli_online() {
    "$CLI" -c --controller="$CONTROLLER" ${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"} --command="$1" 2>&1
}

# Run a CLI script file against the running Domain Controller
cli_online_file() {
    "$CLI" -c --controller="$CONTROLLER" ${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"} --file="$1"
}

# Extract a string result:  "result" => "value"
result_of() {
    tr -d '\n' | sed -n 's/.*"result" => "\([^"]*\)".*/\1/p'
}

# Extract the first item of a list result:  "result" => ["a", "b"]
first_list_item() {
    tr -d '\n' | sed -n 's/.*"result" => \[ *"\([^"]*\)".*/\1/p'
}

# DOMAIN, STANDALONE, or empty if nothing answers on $CONTROLLER
launch_type() {
    cli_online ":read-attribute(name=launch-type)" | result_of
}

# Name of the host controller (in host.xml): "primary" or "master" depending on version
detect_host() {
    if [ -n "${HOST_NAME:-}" ]; then
        echo "$HOST_NAME"
    elif [ "$1" = online ]; then
        cli_online ":read-children-names(child-type=host)" | first_list_item
    else
        sed -n 's/.*<host [^>]*name="\([^"]*\)".*/\1/p' "$CONFIG_DIR/$HOST_CONFIG" | head -1
    fi
}

server_list() {
    echo "$SERVERS" | tr ',' ' '
}

server_status() {    # STARTED, STOPPED, STARTING, FAILED, DISABLED
    cli_online "/host=$1/server-config=$2:read-attribute(name=status)" | result_of
}