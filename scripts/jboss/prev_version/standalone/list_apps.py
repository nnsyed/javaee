#!/usr/bin/env python3
# ==============================================================================
# list_apps.py
# WildFly equivalent of the WLST list_apps.py. Uses jboss-cli.sh to read the
# server's management model and prints, for every deployment:
#   - enabled flag and status (OK / FAILED / STOPPED)
#   - each web module and its context root (EARs list their WAR subdeployments)
#   - servlets with full URLs built from their mappings
#   - REST endpoints with HTTP methods, read from WildFly's JAX-RS runtime data
#
# Usage:
#   python3 list_apps.py
#
# Optional environment variables:
#   JBOSS_HOME     /opt/jboss/wildfly (default)
#   JBOSS_CLI      command used to run the CLI. Default: $JBOSS_HOME/bin/jboss-cli.sh
#                  For a container from the host:
#                  JBOSS_CLI="docker exec -i wildfly /opt/jboss/wildfly/bin/jboss-cli.sh"
#   CONTROLLER     localhost:9990
#   MGMT_USER / MGMT_PW   only needed if local CLI authentication is disabled
#   APP_NAMES      comma-separated deployment names (e.g. rest-app.war,servlet-app.war)
#   PUBLIC_HOST    host name to show in URLs (default: bound address, or this
#                  machine's host name when bound to 0.0.0.0)
#   SHOW_INTERNAL  true to also list Undertow's built-in servlets (default, JSP)
#   REPORT_CSV     path of a CSV file to also write the report to
# ==============================================================================
import csv
import json
import os
import shlex
import socket
import subprocess
import sys

JBOSS_HOME    = os.environ.get('JBOSS_HOME', '/opt/jboss/wildfly')
CLI           = shlex.split(os.environ.get('JBOSS_CLI', os.path.join(JBOSS_HOME, 'bin', 'jboss-cli.sh')))
CONTROLLER    = os.environ.get('CONTROLLER', 'localhost:9990')
MGMT_USER     = os.environ.get('MGMT_USER')
MGMT_PW       = os.environ.get('MGMT_PW', '')
PUBLIC_HOST   = os.environ.get('PUBLIC_HOST')
REPORT_CSV    = os.environ.get('REPORT_CSV')
SHOW_INTERNAL = os.environ.get('SHOW_INTERNAL', 'false').lower() == 'true'
APP_FILTER    = [a.strip() for a in os.environ.get('APP_NAMES', '').split(',') if a.strip()]

UNSPECIFIED_HOSTS = ('0.0.0.0', '', '::', '0:0:0:0:0:0:0:0')
INTERNAL_PREFIXES = ('io.undertow.', 'org.apache.jasper.', 'org.wildfly.extension.undertow.')

COMMANDS = [
    ':read-attribute(name=server-state)',
    ':read-attribute(name=product-version)',
    '/socket-binding-group=standard-sockets/socket-binding=http:read-resource(include-runtime=true)',
    '/socket-binding-group=standard-sockets/socket-binding=https:read-resource(include-runtime=true)',
    '/deployment=*:read-resource(include-runtime=true,recursive=true)',
]


# ------------------------------------------------------------------------------
# CLI access
# ------------------------------------------------------------------------------
def parse_json_stream(text):
    """The CLI prints one JSON document per command; decode them in order."""
    decoder = json.JSONDecoder()
    docs, i = [], 0
    while True:
        j = text.find('{', i)
        if j < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, j)
            docs.append(obj)
            i = end
        except ValueError:
            i = j + 1
    return docs


def run_cli():
    cmd = CLI + ['-c', '--controller=' + CONTROLLER, '--output-json']
    if MGMT_USER:
        cmd += ['--user=' + MGMT_USER, '--password=' + MGMT_PW]
    try:
        proc = subprocess.run(cmd, input='\n'.join(COMMANDS) + '\n',
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=180)
    except FileNotFoundError:
        sys.exit('ERROR: cannot run %s (set JBOSS_HOME or JBOSS_CLI)' % CLI[0])
    except subprocess.TimeoutExpired:
        sys.exit('ERROR: jboss-cli.sh timed out')

    docs = parse_json_stream(proc.stdout)
    if len(docs) < len(COMMANDS):
        print('ERROR: unexpected output from jboss-cli.sh. Is WildFly running at %s?' % CONTROLLER)
        print(proc.stderr.strip() or proc.stdout.strip()[-2000:])
        sys.exit(1)
    return docs


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def join_path(*parts):
    segs = []
    for p in parts:
        if p:
            segs.extend(s for s in str(p).split('/') if s)
    return '/' + '/'.join(segs)


def pattern_to_path(ctx, pattern):
    if pattern.startswith('*.'):
        return join_path(ctx) + '/<anything>' + pattern[1:]
    if pattern.endswith('/*'):
        return join_path(ctx, pattern[:-2]) + '/'
    if pattern in ('/', ''):
        return join_path(ctx) + '/'
    return join_path(ctx, pattern)


def base_urls(http_doc, https_doc):
    urls = []
    for proto, doc in (('http', http_doc), ('https', https_doc)):
        if doc.get('outcome') != 'success':
            continue
        r = doc.get('result') or {}
        if not r.get('bound'):
            continue
        addr = str(r.get('bound-address') or '').lstrip('/')
        port = r.get('bound-port')
        if PUBLIC_HOST:
            host = PUBLIC_HOST
        elif addr in UNSPECIFIED_HOSTS:
            host = socket.getfqdn()
        else:
            host = addr
        urls.append('%s://%s:%s' % (proto, host, port))
    return urls


def web_modules(dep_name, dep):
    """[(module_name, undertow_dict, jaxrs_dict)] for the deployment and its subdeployments."""
    mods = []
    sub = dep.get('subsystem') or {}
    if sub.get('undertow'):
        mods.append((dep_name, sub['undertow'], sub.get('jaxrs') or {}))
    for sname, sdep in (dep.get('subdeployment') or {}).items():
        ssub = (sdep or {}).get('subsystem') or {}
        if ssub.get('undertow'):
            mods.append((sname, ssub['undertow'], ssub.get('jaxrs') or {}))
    return mods


def rest_endpoints(jaxrs, ctx):
    """{path: set(methods)} from the JAX-RS runtime data ('GET /ctx/api/items')."""
    eps = {}
    for _cls, res in (jaxrs.get('rest-resource') or {}).items():
        for rp in (res or {}).get('rest-resource-paths') or []:
            for rm in rp.get('resource-methods') or []:
                parts = str(rm).split(' ', 1)
                if len(parts) != 2:
                    continue
                method, path = parts
                if not path.startswith(join_path(ctx)):
                    path = join_path(ctx, path)
                eps.setdefault(path, set()).add(method)
    return eps


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
state_doc, version_doc, http_doc, https_doc, deps_doc = run_cli()[:5]

server_state = state_doc.get('result', 'unknown')
version = str(version_doc.get('result') or 'unknown')
bases = base_urls(http_doc, https_doc)

print('')
print('=' * 78)
print(' WildFly %s   server state: %s' % (version, server_state))
print('=' * 78)

major = version.split('.')[0]
if major.isdigit() and int(major) >= 27:
    print(' WARNING: WildFly %s supports only jakarta.* APIs; javax.* (Java EE 8) apps will fail.' % major)

rows = []
deployments = [d for d in (deps_doc.get('result') or []) if d.get('outcome') == 'success']
if APP_FILTER:
    deployments = [d for d in deployments if (d.get('result') or {}).get('name') in APP_FILTER]

if not deployments:
    print(' No deployments found.')

for item in deployments:
    dep = item.get('result') or {}
    name = dep.get('name', '?')
    status = dep.get('status', 'UNKNOWN')
    enabled = dep.get('enabled')

    print('')
    print(' Deployment  : ' + name)
    print(' Enabled     : ' + str(enabled))
    print(' Status      : ' + str(status) + ('  <- active' if status == 'OK' and enabled else ''))

    if not enabled or status != 'OK':
        rows.append([name, enabled, status, '', '', '', ''])
        print('       (not active: no URLs available)')
        continue

    mods = web_modules(name, dep)
    if not mods:
        print('       (no web modules: not reachable over HTTP)')
        rows.append([name, enabled, status, '', '', '', ''])
        continue

    for mod_name, undertow, jaxrs in mods:
        ctx = undertow.get('context-root') or '/'
        servlets = undertow.get('servlet') or {}
        endpoints = rest_endpoints(jaxrs, ctx)

        for base in bases:
            print('       Module %s' % mod_name)
            print('       Base URL : ' + base + join_path(ctx) + '/')
            rows.append([name, enabled, status, mod_name, 'context-root', '', base + join_path(ctx) + '/'])

            shown = 0
            for sname, s in sorted(servlets.items()):
                s = s or {}
                cls = str(s.get('servlet-class') or '')
                if 'resteasy' in cls.lower():
                    continue          # REST is listed from the JAX-RS data below
                if cls.startswith(INTERNAL_PREFIXES) and not SHOW_INTERNAL:
                    continue
                print("         Servlet '%s' (%s)" % (sname, cls))
                for pat in s.get('mappings') or []:
                    url = base + pattern_to_path(ctx, str(pat))
                    print('           ' + url)
                    rows.append([name, enabled, status, mod_name, 'servlet', '', url])
                shown += 1

            if endpoints:
                print('         REST endpoints')
                for path in sorted(endpoints):
                    methods = sorted(endpoints[path])
                    url = base + path
                    print('           %-22s %s' % ('[' + ','.join(methods) + ']', url))
                    for m in methods:
                        rows.append([name, enabled, status, mod_name, 'rest', m, url])
            elif not shown:
                print('         (no application servlets or REST resources registered)')

print('')
print('=' * 78)

if REPORT_CSV:
    with open(REPORT_CSV, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['deployment', 'enabled', 'status', 'module', 'kind', 'http_method', 'url'])
        w.writerows(rows)
    print(' CSV report written to ' + REPORT_CSV)