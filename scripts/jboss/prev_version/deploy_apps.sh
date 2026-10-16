#!/usr/bin/env bash
# ==============================================================================
# deploy_apps.sh   (WildFly managed domain)
# WildFly equivalent of deploy_apps.py: deploys each archive to the server
# group (= WebLogic cluster). An existing deployment is undeployed first.
# Context roots come from each archive's jboss-web.xml / application.xml.
#
# Usage (from the directory that contains ./artifacts):
#   ./deploy_apps.sh
# ==============================================================================
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/wf_domain_common.sh"

APPS=(
    "./artifacts/ejb-jsp-app.ear"
    "./artifacts/web-module-1.0.0.war"
    "./artifacts/scott-jdbc-app.war"
    "./artifacts/scott-jms-jdbc-app.war"
    "./artifacts/rest-app.war"
    "./artifacts/servlet-app.war"
)

[ "$(launch_type)" = DOMAIN ] || die "No Domain Controller reachable at $CONTROLLER. Run start_domain.sh first."
HOST="$(detect_host online)"

version="$(cli_online ':read-attribute(name=product-version)' | result_of)"
major="${version%%.*}"
echo ">>> WildFly ${version:-unknown}, deploying to server group $SERVER_GROUP"
if [[ "$major" =~ ^[0-9]+$ ]] && [ "$major" -ge 27 ]; then
    echo ">>> WARNING: WildFly $major supports only jakarta.* APIs; javax.* (Java EE 8) apps will fail."
fi

for s in $(server_list); do
    st="$(server_status "$HOST" "$s")"
    [ "$st" = STARTED ] || echo ">>> WARNING: $s is ${st:-unknown}; apps will start when it does."
done

deployed=()
failed=()

for app in "${APPS[@]}"; do
    name="$(basename "$app")"
    abs="$(cd "$(dirname "$app")" 2>/dev/null && pwd)/$name"

    if [ ! -f "$abs" ]; then
        echo ">>> WARNING: $abs not found, skipping"
        failed+=("$name")
        continue
    fi

    if cli_online "/deployment=$name:read-resource" | grep -q '"outcome" => "success"'; then
        echo ">>> $name already exists; undeploying first..."
        cli_online "undeploy $name --all-relevant-server-groups" > /dev/null
    fi

    echo ">>> Deploying $name -> $SERVER_GROUP"
    out="$(cli_online "deploy \"$abs\" --name=$name --server-groups=$SERVER_GROUP")"
    rc=$?

    ok=true
    if [ $rc -ne 0 ]; then
        ok=false
    else
        # Check the deployment on every started server in the group
        for s in $(server_list); do
            [ "$(server_status "$HOST" "$s")" = STARTED ] || continue
            st="$(cli_online "/host=$HOST/server=$s/deployment=$name:read-attribute(name=status)" | result_of)"
            if [ "$st" != OK ]; then
                echo ">>> ERROR: $name on $s has status ${st:-unknown}"
                ok=false
            fi
        done
    fi

    if [ "$ok" = true ]; then
        deployed+=("$name")
    else
        [ -n "$out" ] && echo "$out" | sed 's/^/      /'
        echo "      Server log: $JBOSS_HOME/domain/servers/<server>/log/server.log"
        failed+=("$name")
    fi
done

echo ""
echo ">>> Deployed: ${deployed[*]:-none}"
if [ ${#failed[@]} -gt 0 ]; then
    echo ">>> Failed:   ${failed[*]}"
    exit 1
fi
exit 0