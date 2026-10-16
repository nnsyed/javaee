# ==============================================================================
# list_apps.py  (WLST ONLINE, WebLogic 14.1.x)
# Lists every application deployed to the domain with:
#   - module type, source path and configured targets
#   - each server it is targeted to (clusters expanded to member servers)
#   - server state, application state and health on that server
#   - runtime URLs built from each web module's actual context root
#
# Usage:
#   WLS_USER='weblogic' WLS_PW='WlsPass' wlst.sh list_apps.py
#
# Optional environment variables:
#   ADMIN_URL    t3://127.0.0.1:7001 (default)
#   APP_NAMES    comma-separated list to report on only some applications
#   PUBLIC_HOST  host name to show in URLs instead of the server's listen address
#                (useful when servers listen on 0.0.0.0 or run in containers)
#   REPORT_CSV   path of a CSV file to also write the report to
# ==============================================================================
import os
from java.net import URL as JavaURL

WLS_USER    = os.environ.get('WLS_USER', 'weblogic')
WLS_PW      = os.environ.get('WLS_PW')
ADMIN_URL   = os.environ.get('ADMIN_URL', 't3://127.0.0.1:7001')
PUBLIC_HOST = os.environ.get('PUBLIC_HOST')
REPORT_CSV  = os.environ.get('REPORT_CSV')
APP_FILTER  = [a.strip() for a in os.environ.get('APP_NAMES', '').split(',') if a.strip()]

if not WLS_PW:
    print "ERROR: WLS_PW environment variable is not set!"
    exit(exitcode=1)

try:
    connect(WLS_USER, WLS_PW, ADMIN_URL)
except Exception, err:
    print "ERROR: could not connect to " + ADMIN_URL + ". Is the AdminServer running?"
    exit(exitcode=1)

# Use the MBean APIs directly instead of cd(), so the output stays clean.
domain_cfg = domainRuntimeService.getDomainConfiguration()
domain_rt  = domainRuntimeService.getDomainRuntime()
state_rt   = domain_rt.getAppRuntimeStateRuntime()

# Running servers only have a ServerRuntime while they are up.
running = {}
for sr in domainRuntimeService.getServerRuntimes():
    running[sr.getName()] = sr


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def strip_state(s):
    if s is None:
        return 'UNKNOWN'
    s = str(s)
    if s.startswith('STATE_'):
        s = s[len('STATE_'):]
    return s


def server_state(name):
    try:
        return domain_rt.lookupServerLifeCycleRuntime(name).getState()
    except Exception:
        return 'UNKNOWN'


def expand_targets(targets):
    """Return (target label list, ordered unique server name list)."""
    labels = []
    servers = []
    for t in targets:
        t_type = t.getType()
        labels.append(t.getName() + ' (' + t_type + ')')
        if t_type == 'Cluster':
            for s in t.getServers():
                if s.getName() not in servers:
                    servers.append(s.getName())
        elif t_type == 'Server':
            if t.getName() not in servers:
                servers.append(t.getName())
    return labels, servers


def base_urls(sr):
    """http/https base URLs a running server answers on."""
    urls = []
    for proto in ('http', 'https'):
        try:
            u = sr.getURL(proto)
        except Exception:
            u = None
        if not u or not str(u).startswith(proto + '://'):
            continue
        u = str(u)
        if PUBLIC_HOST:
            ju = JavaURL(u)
            u = '%s://%s:%d' % (proto, PUBLIC_HOST, ju.getPort())
        if u not in urls:
            urls.append(u)
    return urls


def health_string(app_rt):
    try:
        from weblogic.health import HealthState
        return HealthState.mapToString(app_rt.getHealthState().getState())
    except Exception:
        return 'UNKNOWN'


def web_modules(sr, app_name):
    """Context roots of the app's web modules on a running server, plus health."""
    modules = []
    try:
        app_rt = sr.lookupApplicationRuntime(app_name)
    except Exception:
        app_rt = None
    if app_rt is None:
        return modules, 'N/A'
    for comp in app_rt.getComponentRuntimes():
        if comp.getType() == 'WebAppComponentRuntime':
            ctx = comp.getContextRoot() or '/'
            if not ctx.startswith('/'):
                ctx = '/' + ctx
            modules.append((comp.getModuleId(), ctx))
    return modules, health_string(app_rt)


def join_url(base, ctx):
    if ctx == '/':
        return base + '/'
    return base + ctx


# ------------------------------------------------------------------------------
# Build the report
# ------------------------------------------------------------------------------
rows = []   # for CSV
apps = domain_cfg.getAppDeployments()
if APP_FILTER:
    apps = [a for a in apps if a.getName() in APP_FILTER]

print ""
print "=" * 78
print " Applications deployed to domain '%s'" % domain_cfg.getName()
print "=" * 78

if not apps:
    print " No applications found."

for app in apps:
    app_name = app.getName()
    try:
        intended = strip_state(state_rt.getIntendedState(app_name))
    except Exception:
        intended = 'UNKNOWN'

    target_labels, servers = expand_targets(app.getTargets())

    print ""
    print " Application : " + app_name
    print " Type        : " + str(app.getModuleType())
    print " Source      : " + str(app.getAbsoluteSourcePath())
    print " Targets     : " + (', '.join(target_labels) or 'NONE (untargeted)')
    print " Intended    : " + intended

    if not servers:
        rows.append([app_name, str(app.getModuleType()), '', '', '', intended, '', ''])
        continue

    for srv in servers:
        srv_state = server_state(srv)
        try:
            app_state = strip_state(state_rt.getCurrentState(app_name, srv))
        except Exception:
            app_state = 'UNKNOWN'

        urls = []
        health = 'N/A'
        if srv in running and srv_state == 'RUNNING':
            modules, health = web_modules(running[srv], app_name)
            for base in base_urls(running[srv]):
                for module_id, ctx in modules:
                    urls.append(join_url(base, ctx))

        active_flag = ''
        if app_state == 'ACTIVE':
            active_flag = '  <- active'

        print "   - Server %-15s [%s]  app state: %s  health: %s%s" % (
            srv, srv_state, app_state, health, active_flag)

        if urls:
            for u in urls:
                print "       " + u
        elif srv_state != 'RUNNING':
            print "       (server not running: no URLs available)"
        elif app_state == 'ACTIVE':
            print "       (no web modules: not reachable over HTTP)"

        if urls:
            for u in urls:
                rows.append([app_name, str(app.getModuleType()), srv, srv_state,
                             app_state, intended, health, u])
        else:
            rows.append([app_name, str(app.getModuleType()), srv, srv_state,
                         app_state, intended, health, ''])

print ""
print "=" * 78

# ------------------------------------------------------------------------------
# Optional CSV
# ------------------------------------------------------------------------------
if REPORT_CSV:
    def csv_cell(v):
        v = str(v)
        if ',' in v or '"' in v:
            v = '"' + v.replace('"', '""') + '"'
        return v
    f = open(REPORT_CSV, 'w')
    f.write('application,type,server,server_state,app_state,intended_state,health,url\n')
    for r in rows:
        f.write(','.join([csv_cell(c) for c in r]) + '\n')
    f.close()
    print " CSV report written to " + REPORT_CSV

disconnect()
exit(exitcode=0)
