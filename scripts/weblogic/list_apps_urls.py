# ==============================================================================
# list_apps.py  (WLST ONLINE, WebLogic 14.1.x)
# Lists every application deployed to the domain with:
#   - module type, source path and configured targets
#   - each server it is targeted to (clusters expanded to member servers)
#   - server state, application state and health on that server
#   - the web module's base URL (context root)
#   - every servlet with its URL mappings
#   - REST (JAX-RS / Jersey) endpoints with HTTP methods, read from the
#     application's WADL
#
# Usage:
#   WLS_USER='weblogic' WLS_PW='WlsPass' wlst.sh list_apps.py
#
# Optional environment variables:
#   ADMIN_URL      t3://127.0.0.1:7001 (default)
#   APP_NAMES      comma-separated list to report on only some applications
#   PUBLIC_HOST    host name to show in URLs. Default: the server's listen
#                  address, or this machine's host name if it is 0.0.0.0
#   SHOW_INTERNAL  true to also list WebLogic's built-in servlets (JSP, file)
#   REPORT_CSV     path of a CSV file to also write the report to
# ==============================================================================
import os
from java.net import URL as JavaURL
from java.net import InetAddress
from javax.xml.parsers import DocumentBuilderFactory

WLS_USER      = os.environ.get('WLS_USER', 'weblogic')
WLS_PW        = os.environ.get('WLS_PW')
ADMIN_URL     = os.environ.get('ADMIN_URL', 't3://127.0.0.1:7001')
PUBLIC_HOST   = os.environ.get('PUBLIC_HOST')
REPORT_CSV    = os.environ.get('REPORT_CSV')
SHOW_INTERNAL = os.environ.get('SHOW_INTERNAL', 'false').lower() == 'true'
APP_FILTER    = [a.strip() for a in os.environ.get('APP_NAMES', '').split(',') if a.strip()]

WADL_NS = 'http://wadl.dev.java.net/2009/02'
UNSPECIFIED_HOSTS = ('0.0.0.0', '', '::', '[::]')

if not WLS_PW:
    print "ERROR: WLS_PW environment variable is not set!"
    exit(exitcode=1)

try:
    connect(WLS_USER, WLS_PW, ADMIN_URL)
except Exception, err:
    print "ERROR: could not connect to " + ADMIN_URL + ". Is the AdminServer running?"
    exit(exitcode=1)

domain_cfg = domainRuntimeService.getDomainConfiguration()
domain_rt  = domainRuntimeService.getDomainRuntime()
state_rt   = domain_rt.getAppRuntimeStateRuntime()

running = {}
for sr in domainRuntimeService.getServerRuntimes():
    running[sr.getName()] = sr

try:
    LOCAL_HOST = InetAddress.getLocalHost().getCanonicalHostName()
except Exception:
    LOCAL_HOST = 'localhost'


# ------------------------------------------------------------------------------
# General helpers
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


def join_path(*parts):
    """Join URL path segments with single slashes; keeps a leading slash."""
    segs = []
    for p in parts:
        if p is None:
            continue
        for s in str(p).split('/'):
            if s:
                segs.append(s)
    return '/' + '/'.join(segs)


def base_urls(sr):
    """
    For a running server, return [(display_base, fetch_base)] per protocol.
    display_base is what a client should use; fetch_base is what this script
    uses to read the WADL (localhost when the server listens on 0.0.0.0).
    """
    result = []
    for proto in ('http', 'https'):
        try:
            u = sr.getURL(proto)
        except Exception:
            u = None
        if not u or not str(u).startswith(proto + '://'):
            continue
        ju = JavaURL(str(u))
        host = ju.getHost()
        port = ju.getPort()
        if host in UNSPECIFIED_HOSTS:
            fetch_host = 'localhost'
            display_host = PUBLIC_HOST or LOCAL_HOST
        else:
            fetch_host = host
            display_host = PUBLIC_HOST or host
        pair = ('%s://%s:%d' % (proto, display_host, port),
                '%s://%s:%d' % (proto, fetch_host, port))
        if pair not in result:
            result.append(pair)
    return result


def health_string(app_rt):
    try:
        from weblogic.health import HealthState
        return HealthState.mapToString(app_rt.getHealthState().getState())
    except Exception:
        return 'UNKNOWN'


# ------------------------------------------------------------------------------
# Servlet and REST discovery
# ------------------------------------------------------------------------------
def is_internal_servlet(class_name):
    return class_name.startswith('weblogic.')


def is_jaxrs_servlet(class_name):
    return 'jersey' in class_name.lower() and 'ServletContainer' in class_name


def servlet_patterns(servlet_rt):
    try:
        pats = servlet_rt.getURLPatterns()
        if pats:
            return [str(p) for p in pats]
    except Exception:
        pass
    try:
        p = servlet_rt.getServletPath()
        if p:
            return [str(p)]
    except Exception:
        pass
    return []


def pattern_to_path(ctx, pattern):
    """
    Turn a servlet URL pattern into a displayable path:
      /hello    -> /ctx/hello
      /api/*    -> /ctx/api/
      *.do      -> /ctx/<anything>.do
      /         -> /ctx/  (default servlet)
    """
    if pattern.startswith('*.'):
        return join_path(ctx) + '/<anything>' + pattern[1:]
    if pattern.endswith('/*'):
        return join_path(ctx, pattern[:-2]) + '/'
    if pattern in ('/', ''):
        return join_path(ctx) + '/'
    return join_path(ctx, pattern)


def fetch_wadl(url):
    """Return a parsed WADL document, or (None, reason)."""
    try:
        conn = JavaURL(url).openConnection()
        conn.setConnectTimeout(5000)
        conn.setReadTimeout(10000)
        code = conn.getResponseCode()
        if code != 200:
            return None, 'HTTP %d' % code
        dbf = DocumentBuilderFactory.newInstance()
        dbf.setNamespaceAware(True)
        try:
            dbf.setFeature('http://apache.org/xml/features/disallow-doctype-decl', True)
        except Exception:
            pass
        doc = dbf.newDocumentBuilder().parse(conn.getInputStream())
        return doc, None
    except Exception, e:
        return None, str(e)


def element_children(node, local_name):
    out = []
    kids = node.getChildNodes()
    for i in range(kids.getLength()):
        k = kids.item(i)
        if k.getNodeType() == 1 and k.getLocalName() == local_name:
            out.append(k)
    return out


def walk_resources(node, prefix, out):
    for res in element_children(node, 'resource'):
        path = join_path(prefix, res.getAttribute('path'))
        methods = [m.getAttribute('name') for m in element_children(res, 'method')]
        if methods and not path.endswith('application.wadl'):
            out.append((path, methods))
        walk_resources(res, path, out)


def rest_endpoints(fetch_root):
    """
    fetch_root: URL of the Jersey servlet root, e.g. http://localhost:9001/restapp/api
    Returns ([(relative_path, [methods])], error)
    """
    doc, err = fetch_wadl(fetch_root.rstrip('/') + '/application.wadl')
    if doc is None:
        return [], err
    endpoints = []
    res_list = doc.getElementsByTagNameNS(WADL_NS, 'resources')
    for i in range(res_list.getLength()):
        walk_resources(res_list.item(i), '', endpoints)
    return endpoints, None


def describe_web_modules(sr, app_name):
    """
    Returns (health, modules) where modules is a list of dicts:
      {'ctx': '/restapp', 'servlets': [(name, class, [paths], is_rest)]}
    """
    try:
        app_rt = sr.lookupApplicationRuntime(app_name)
    except Exception:
        app_rt = None
    if app_rt is None:
        return 'N/A', []

    modules = []
    for comp in app_rt.getComponentRuntimes():
        if comp.getType() != 'WebAppComponentRuntime':
            continue
        ctx = comp.getContextRoot() or '/'
        servlets = []
        try:
            servlet_rts = comp.getServlets()
        except Exception:
            servlet_rts = []
        for s in servlet_rts:
            cls = str(s.getServletClassName() or '')
            if is_internal_servlet(cls) and not SHOW_INTERNAL:
                continue
            paths = [pattern_to_path(ctx, p) for p in servlet_patterns(s)]
            servlets.append((str(s.getServletName()), cls, paths, is_jaxrs_servlet(cls)))
        modules.append({'ctx': join_path(ctx), 'servlets': servlets})
    return health_string(app_rt), modules


# ------------------------------------------------------------------------------
# Report
# ------------------------------------------------------------------------------
rows = []

def add_row(app, srv, srv_state, app_state, intended, health, kind, method, url):
    rows.append([app.getName(), str(app.getModuleType()), srv, srv_state,
                 app_state, intended, health, kind, method, url])

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

    for srv in servers:
        srv_state = server_state(srv)
        try:
            app_state = strip_state(state_rt.getCurrentState(app_name, srv))
        except Exception:
            app_state = 'UNKNOWN'

        health = 'N/A'
        modules = []
        bases = []
        if srv in running and srv_state == 'RUNNING':
            health, modules = describe_web_modules(running[srv], app_name)
            bases = base_urls(running[srv])

        flag = ''
        if app_state == 'ACTIVE':
            flag = '  <- active'
        print "   - Server %-15s [%s]  app state: %s  health: %s%s" % (
            srv, srv_state, app_state, health, flag)

        if srv_state != 'RUNNING':
            print "       (server not running: no URLs available)"
            add_row(app, srv, srv_state, app_state, intended, health, '', '', '')
            continue
        if not modules:
            print "       (no web modules: not reachable over HTTP)"
            add_row(app, srv, srv_state, app_state, intended, health, '', '', '')
            continue

        for display_base, fetch_base in bases:
            for mod in modules:
                print "       Base URL : " + display_base + mod['ctx'] + '/'
                add_row(app, srv, srv_state, app_state, intended, health,
                        'context-root', '', display_base + mod['ctx'] + '/')

                if not mod['servlets']:
                    print "         (no application servlets registered)"

                for name, cls, paths, is_rest in mod['servlets']:
                    if is_rest:
                        print "         REST application '%s'" % name
                    else:
                        print "         Servlet '%s' (%s)" % (name, cls)

                    for p in paths:
                        if not is_rest:
                            print "           " + display_base + p
                            add_row(app, srv, srv_state, app_state, intended, health,
                                    'servlet', '', display_base + p)
                            continue

                        # JAX-RS: list endpoints from the WADL
                        rest_root = p.rstrip('/')
                        endpoints, err = rest_endpoints(fetch_base + rest_root)
                        if err:
                            print "           " + display_base + rest_root + "/...  (WADL unavailable: " + err + ")"
                            add_row(app, srv, srv_state, app_state, intended, health,
                                    'rest-root', '', display_base + rest_root + '/')
                            continue
                        if not endpoints:
                            print "           " + display_base + rest_root + "/  (no resources found in WADL)"
                        for ep_path, methods in endpoints:
                            full = display_base + join_path(rest_root, ep_path)
                            print "           %-22s %s" % ('[' + ','.join(methods) + ']', full)
                            for m in methods:
                                add_row(app, srv, srv_state, app_state, intended, health,
                                        'rest', m, full)

print ""
print "=" * 78

if REPORT_CSV:
    def csv_cell(v):
        v = str(v)
        if ',' in v or '"' in v:
            v = '"' + v.replace('"', '""') + '"'
        return v
    f = open(REPORT_CSV, 'w')
    f.write('application,type,server,server_state,app_state,intended_state,health,kind,http_method,url\n')
    for r in rows:
        f.write(','.join([csv_cell(c) for c in r]) + '\n')
    f.close()
    print " CSV report written to " + REPORT_CSV

disconnect()
exit(exitcode=0)
