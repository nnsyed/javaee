#!/usr/bin/env bash
# ==============================================================================
# start_server.sh
# Starts WildFly with the standalone-full profile in the background and waits
# until it is running. Does nothing if the server is already up.
#
# Optional environment variables:
#   JBOSS_HOME     /opt/jboss/wildfly (default)
#   SERVER_CONFIG  standalone-full.xml (default)
#   BIND_ADDRESS   0.0.0.0 (default)
#   CONTROLLER     localhost:9990
#   MGMT_USER / MGMT_PW   only needed if local CLI authentication is disabled
#   LOG_FILE       /tmp/wildfly_startup.log
#   TIMEOUT_SECS   300
# ==============================================================================
set -uo pipefail

JBOSS_HOME="${JBOSS_HOME:-/opt/jboss/wildfly}"
CLI="$JBOSS_HOME/bin/jboss-cli.sh"
SERVER_CONFIG="${SERVER_CONFIG:-standalone-full.xml}"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"
CONTROLLER="${CONTROLLER:-localhost:9990}"
LOG_FILE="${LOG_FILE:-/tmp/wildfly_startup.log}"
TIMEOUT_SECS="${TIMEOUT_SECS:-300}"

AUTH_ARGS=()
if [ -n "${MGMT_USER:-}" ]; then
    AUTH_ARGS=(--user="$MGMT_USER" --password="${MGMT_PW:-}")
fi

server_state() {
    "$CLI" -c --controller="$CONTROLLER" "${AUTH_ARGS[@]}" \
        --command=":read-attribute(name=server-state)" 2>/dev/null \
        | grep -o '"result" => "[a-z-]*"' | sed 's/.*=> "\(.*\)"/\1/'
}

state="$(server_state)"
if [ -n "$state" ]; then
    echo ">>> WildFly is already running (state: $state)."
    exit 0
fi

echo ">>> Starting WildFly with $SERVER_CONFIG (log: $LOG_FILE)..."
nohup "$JBOSS_HOME/bin/standalone.sh" -c "$SERVER_CONFIG" -b "$BIND_ADDRESS" \
    > "$LOG_FILE" 2>&1 < /dev/null &

waited=0
while [ "$waited" -lt "$TIMEOUT_SECS" ]; do
    sleep 5
    waited=$((waited + 5))
    state="$(server_state)"
    case "$state" in
        running)
            echo ">>> WildFly is running."
            exit 0 ;;
        reload-required|restart-required)
            echo ">>> WildFly is up but reports '$state'. Check $LOG_FILE."
            exit 0 ;;
        *)
            echo ">>> Waiting for WildFly... (${waited}s, state: ${state:-not reachable})" ;;
    esac
done

echo ">>> ERROR: WildFly did not start within ${TIMEOUT_SECS}s. See $LOG_FILE"
exit 1