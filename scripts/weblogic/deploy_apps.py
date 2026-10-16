# ==============================================================================
# deploy_apps.py  (WLST ONLINE)
# Deploys the applications to a running domain. If an application is already
# deployed it is undeployed first, so the script is safe to re-run.
#
# Usage (run from the directory containing ./artifacts):
#   WLS_USER='weblogic' WLS_PW='WlsPass' wlst.sh deploy_apps.py
# Optional: DEPLOY_TARGET (default app_cluster), ADMIN_URL
# ==============================================================================
import os

WLS_USER = os.environ.get('WLS_USER', 'weblogic')
WLS_PW   = os.environ.get('WLS_PW')

if not WLS_PW:
    print "ERROR: WLS_PW environment variable is not set!"
    exit(exitcode=1)

ADMIN_URL      = os.environ.get('ADMIN_URL', 't3://127.0.0.1:7001')
DEPLOY_TARGET  = os.environ.get('DEPLOY_TARGET', 'app_cluster')
TARGET_SERVERS = ['my_server']        # servers behind DEPLOY_TARGET, for a pre-check
DEPLOY_TIMEOUT = 600000               # milliseconds per application

apps = [
    {'name': 'ejb-jsp-app',        'path': './artifacts/ejb-jsp-app.ear'},
    {'name': 'scott-jdbc-app',     'path': './artifacts/scott-jdbc-app.war'},
    {'name': 'scott-jms-jdbc-app', 'path': './artifacts/scott-jms-jdbc-app.war'},
    {'name': 'rest-app',           'path': './artifacts/rest-app.war'},
    {'name': 'servlet-app',        'path': './artifacts/servlet-app.war'}
]

try:
    connect(WLS_USER, WLS_PW, ADMIN_URL)
except Exception, err:
    print "ERROR: could not connect to " + ADMIN_URL + ". Is the AdminServer running?"
    exit(exitcode=1)

# Warn (but continue) if a target server isn't running: the deployment is
# recorded and activates when the server starts.
domainRuntime()
for srv in TARGET_SERVERS:
    cd('/ServerLifeCycleRuntimes/' + srv)
    state = cmo.getState()
    if state != 'RUNNING':
        print ">>> WARNING: " + srv + " is " + state + "; apps will start when it comes up."

current_working_dir = os.getcwd()
deployed = []
failed   = []

for app in apps:
    app_name = app['name']
    app_path = os.path.abspath(os.path.join(current_working_dir, app['path']))

    if not os.path.exists(app_path):
        print ">>> WARNING: " + app_path + " not found, skipping " + app_name
        failed.append(app_name)
        continue

    try:
        serverConfig()
        if getMBean('/AppDeployments/' + app_name) is not None:
            print ">>> " + app_name + " is already deployed; undeploying first..."
            undeploy(app_name, block='true', timeout=DEPLOY_TIMEOUT)

        print ">>> Deploying " + app_name + " -> " + DEPLOY_TARGET
        progress = deploy(app_name, app_path,
                          targets=DEPLOY_TARGET,
                          stageMode='stage',
                          block='true',
                          timeout=DEPLOY_TIMEOUT)

        if progress.isFailed():
            print ">>> ERROR: deployment of " + app_name + " failed."
            progress.printStatus()
            failed.append(app_name)
        else:
            deployed.append(app_name)
    except Exception, err:
        print ">>> ERROR: deployment of " + app_name + " failed: " + str(err)
        failed.append(app_name)

disconnect()

print ""
print ">>> Deployed: " + (', '.join(deployed) or 'none')
if failed:
    print ">>> Failed:   " + ', '.join(failed)
    exit(exitcode=1)

exit(exitcode=0)