# ==============================================================================
# start_servers.py  (WLST)
# Starts the AdminServer, waits for it, then starts the managed server(s)
# and waits until each one reaches RUNNING. Servers already running are left
# alone, so the script is safe to re-run.
#
# Usage:
#   WLS_USER='weblogic' WLS_PW='WlsPass' wlst.sh start_servers.py
# ==============================================================================
import os
import subprocess
from time import sleep

WLS_USER = os.environ.get('WLS_USER', 'weblogic')
WLS_PW   = os.environ.get('WLS_PW')

if not WLS_PW:
    print "ERROR: WLS_PW environment variable is not set!"
    exit(exitcode=1)

DOMAIN_HOME     = os.environ.get('DOMAIN_HOME', '/u01/oracle/user_projects/domains/base_domain')
ADMIN_URL       = os.environ.get('ADMIN_URL', 't3://127.0.0.1:7001')
MANAGED_SERVERS = ['my_server']
LOG_DIR         = os.environ.get('LOG_DIR', '/tmp')

ADMIN_TIMEOUT_SECS   = 300
MANAGED_TIMEOUT_SECS = 600
POLL_SECS            = 10

start_admin_script   = os.path.join(DOMAIN_HOME, 'bin', 'startWebLogic.sh')
start_managed_script = os.path.join(DOMAIN_HOME, 'bin', 'startManagedWebLogic.sh')


def launch(cmd, log_path):
    # nohup + stdin from /dev/null: the server keeps running after WLST exits
    # and can never block on a credentials prompt.
    log = open(log_path, 'a')
    dev_null = open('/dev/null', 'r')
    subprocess.Popen(['nohup'] + cmd, stdin=dev_null, stdout=log, stderr=log)


def try_connect():
    try:
        connect(WLS_USER, WLS_PW, ADMIN_URL, timeout='5000')
        return True
    except Exception, err:
        return False


def server_state(name):
    domainRuntime()
    cd('/ServerLifeCycleRuntimes/' + name)
    return cmo.getState()


# ------------------------------------------------------------------------------
# AdminServer
# ------------------------------------------------------------------------------
if try_connect():
    print ">>> AdminServer is already running."
else:
    admin_log = os.path.join(LOG_DIR, 'AdminServer_startup.log')
    print ">>> Starting AdminServer (log: " + admin_log + ")..."
    launch([start_admin_script], admin_log)

    waited = 0
    connected = False
    while waited < ADMIN_TIMEOUT_SECS:
        sleep(POLL_SECS)
        waited += POLL_SECS
        if try_connect():
            connected = True
            break
        print ">>> Waiting for AdminServer... (" + str(waited) + "s)"

    if not connected:
        print ">>> ERROR: AdminServer did not start within " + str(ADMIN_TIMEOUT_SECS) + "s. See " + admin_log
        exit(exitcode=1)
    print ">>> AdminServer is RUNNING."


# ------------------------------------------------------------------------------
# Managed servers
# ------------------------------------------------------------------------------
failed = []

for ms in MANAGED_SERVERS:
    boot_props = os.path.join(DOMAIN_HOME, 'servers', ms, 'security', 'boot.properties')
    if not os.path.exists(boot_props):
        print ">>> WARNING: " + boot_props + " is missing; " + ms + " may fail to start."

    state = server_state(ms)
    if state == 'RUNNING':
        print ">>> " + ms + " is already RUNNING."
        continue

    ms_log = os.path.join(LOG_DIR, ms + '_startup.log')
    print ">>> Starting " + ms + " (current state: " + state + ", log: " + ms_log + ")..."
    launch([start_managed_script, ms, ADMIN_URL], ms_log)

    waited = 0
    while waited < MANAGED_TIMEOUT_SECS:
        sleep(POLL_SECS)
        waited += POLL_SECS
        state = server_state(ms)
        if state in ('RUNNING', 'FAILED', 'ADMIN'):
            break
        print ">>> " + ms + " state: " + state + " (" + str(waited) + "s)"

    if state == 'RUNNING':
        print ">>> " + ms + " is RUNNING."
    else:
        print ">>> ERROR: " + ms + " ended in state " + state + ". See " + ms_log
        failed.append(ms)

disconnect()

if failed:
    print ">>> Servers that did not reach RUNNING: " + ', '.join(failed)
    exit(exitcode=1)

print ">>> All servers are RUNNING."
exit(exitcode=0)