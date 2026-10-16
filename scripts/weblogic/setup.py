import os
import subprocess
import shutil
from time import sleep as python_sleep

# ==============================================================================
# SECURE CREDENTIAL RETRIEVAL (Environment Variables)
# ==============================================================================
WLS_USER = os.environ.get('WLS_USER', 'weblogic')
WLS_PW   = os.environ.get('WLS_PW')
DB_PW    = os.environ.get('DB_PW')

if not WLS_PW or not DB_PW:
    print "ERROR: WLS_PW or DB_PW environment variables are not set!"
    print "Execute using: WLS_USER='weblogic' WLS_PW='WlsPass' DB_PW='tiger' wlst.sh setup_offline.py"
    exit()

domain_home    = '/u01/oracle/user_projects/domains/base_domain'
ADMIN_SERVER   = 'AdminServer'
MANAGED_SERVER = 'my_server'
CLUSTER        = 'app_cluster'

# ==============================================================================
# PHASE 1: Domain & Server Creation
# ==============================================================================
print ">>> Phase 1: Initializing domain creation in memory..."

if os.path.exists(domain_home):
    print ">>> Found existing domain directory. Cleaning it up for overwrite..."
    try:
        shutil.rmtree(domain_home)
    except Exception, err_cleanup:
        print ">>> Warning: Could not completely clear directory via script."

selectTemplate('Basic WebLogic Server Domain')
selectTemplate('Oracle Restricted JRF')
loadTemplates()

# Configure Administration Server
cd('/Servers/' + ADMIN_SERVER)
set('ListenAddress', '0.0.0.0')
set('ListenPort', 7001)

# Create the Cluster
cd('/')
create(CLUSTER, 'Cluster')

# Create Managed Server
cd('/')
create(MANAGED_SERVER, 'Server')
cd('/Servers/' + MANAGED_SERVER)
set('ListenAddress', '0.0.0.0')
set('ListenPort', 9001)

# reference attributes (like Cluster) must be linked with assign() offline
cd('/')
assign('Server', MANAGED_SERVER, 'Cluster', CLUSTER)

# with a JRF template, managed servers need a server group or the
# JRF libraries/services are only targeted to the AdminServer.
try:
    setServerGroups(MANAGED_SERVER, ['JRF-MAN-SVR'])
except Exception, err_sg:
    print ">>> Warning: could not set JRF server group on " + MANAGED_SERVER + ": " + str(err_sg)

# Set Administration Security Credentials
# the template only contains the user 'weblogic'. Rename it if a different
# admin user name was requested instead of cd-ing to a path that doesn't exist.
cd('/Security/base_domain/User/weblogic')
if WLS_USER != 'weblogic':
    cmo.setName(WLS_USER)
cmo.setPassword(WLS_PW)


# ==============================================================================
# PHASE 2: Provisioning DataSources and JMS Resources (Offline Mode)
# ==============================================================================
print ">>> Phase 2: Building JDBC resources..."

DS_NAME = 'scottDS'
DS_ROOT = '/JDBCSystemResource/' + DS_NAME + '/JdbcResource/' + DS_NAME

# 1. Create JDBC System Resource
cd('/')
create(DS_NAME, 'JDBCSystemResource')
cd(DS_ROOT)
cmo.setName(DS_NAME)

# 1a. DataSource params (child beans must be created; they are named NO_NAME_0)
cd(DS_ROOT)
create('dsParams', 'JDBCDataSourceParams')
cd('JDBCDataSourceParams/NO_NAME_0')
set('JNDIName', 'jdbc/scottDS')
# Non-XA driver: OnePhaseCommit is the valid protocol. See notes if the
# JMS+JDBC app needs both resources in one global transaction.
set('GlobalTransactionsProtocol', 'OnePhaseCommit')

# 1b. Driver params
cd(DS_ROOT)
create('driverParams', 'JDBCDriverParams')
cd('JDBCDriverParams/NO_NAME_0')
set('DriverName', 'oracle.jdbc.OracleDriver')   # must be a quoted string
set('URL', 'jdbc:oracle:thin:@//oracle-ai-scott:1521/FREEPDB1')
set('PasswordEncrypted', DB_PW)

# 1c. Driver properties (needs a Properties container first)
create('driverProps', 'Properties')
cd('Properties/NO_NAME_0')
create('user', 'Property')
cd('Property/user')
set('Value', 'scott')

# 1d. Connection pool params
cd(DS_ROOT)
create('poolParams', 'JDBCConnectionPoolParams')
cd('JDBCConnectionPoolParams/NO_NAME_0')
set('TestTableName', 'SQL SELECT 1 FROM DUAL')
set('TestConnectionsOnReserve', 'true')

# Target JDBC Resource
cd('/')
assign('JDBCSystemResource', DS_NAME, 'Target', CLUSTER)


print ">>> Phase 2: Building JMS resources..."

JMS_SERVER = 'ScottJMSServer'
JMS_STORE  = 'ScottFileStore'
JMS_MODULE = 'ScottJMSModule'
SUBDEPLOY  = 'ScottSubDeployment'

# 2. Persistent store + JMS Server, both on the managed server where the apps run
cd('/')
create(JMS_STORE, 'FileStore')
cd('/FileStores/' + JMS_STORE)
set('Directory', JMS_STORE)          # relative to the domain directory
cd('/')
assign('FileStore', JMS_STORE, 'Target', MANAGED_SERVER)

cd('/')
create(JMS_SERVER, 'JMSServer')
cd('/JMSServers/' + JMS_SERVER)
set('PersistentStore', JMS_STORE)
cd('/')
assign('JMSServer', JMS_SERVER, 'Target', MANAGED_SERVER)

# 3. JMS System Module
# the offline MBean type is 'JMSSystemResource', not 'JMSSystemModule'
cd('/')
create(JMS_MODULE, 'JMSSystemResource')
cd('/')
assign('JMSSystemResource', JMS_MODULE, 'Target', CLUSTER)

# 4. Subdeployment inside the module, targeted to the JMS server
cd('/JMSSystemResource/' + JMS_MODULE)
create(SUBDEPLOY, 'SubDeployment')
cd('/')
assign('JMSSystemResource.SubDeployment', JMS_MODULE + '.' + SUBDEPLOY, 'Target', JMS_SERVER)

# 5. Connection Factory
# the module's resource bean lives at JmsResource/NO_NAME_0 offline
cd('/JMSSystemResource/' + JMS_MODULE + '/JmsResource/NO_NAME_0')
cf = create('ScottCF', 'ConnectionFactory')
cf.setJNDIName('jms/CF')
cf.setSubDeploymentName(SUBDEPLOY)

# 6. Queue mapped to the subdeployment
cd('/JMSSystemResource/' + JMS_MODULE + '/JmsResource/NO_NAME_0')
queue = create('ScottQueueParams', 'Queue')
queue.setJNDIName('jms/scottQueue')
queue.setSubDeploymentName(SUBDEPLOY)


# ==============================================================================
# PHASE 3: Deploy Applications (Offline Mode Declarations)
# ==============================================================================
print ">>> Phase 3: Registering Application Deployments..."

# 'context_root' is optional. If present, a deployment plan is generated to
# override the context root without modifying the archive.
# For an EAR, 'web_uri' must be the WAR's file name INSIDE the EAR
# (as listed in its META-INF/application.xml); add one entry per web module.
apps = [
    {'name': 'ejb-jsp-app',        'path': './artifacts/ejb-jsp-app.ear',
     'web_modules': [ {'web_uri': 'ejb-jsp-web.war', 'context_root': '/ejbjsp'} ]},
    {'name': 'scott-jdbc-app',     'path': './artifacts/scott-jdbc-app.war',     'context_root': '/scott-jdbc'},
    {'name': 'scott-jms-jdbc-app', 'path': './artifacts/scott-jms-jdbc-app.war', 'context_root': '/scott-jms-jdbc'},
    {'name': 'rest-app',           'path': './artifacts/rest-app.war',           'context_root': '/api'},
    {'name': 'servlet-app',        'path': './artifacts/servlet-app.war',        'context_root': '/servlet'}
]

DEPLOY_TARGET = os.environ.get('DEPLOY_TARGET', CLUSTER)
current_working_dir = os.getcwd()

# Plans live outside domain_home, because domain_home is wiped on each run.
PLAN_ROOT = os.path.join(current_working_dir, 'plans')

PLAN_HEADER = """<?xml version='1.0' encoding='UTF-8'?>
<deployment-plan xmlns="http://xmlns.oracle.com/weblogic/deployment-plan"
                 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xsi:schemaLocation="http://xmlns.oracle.com/weblogic/deployment-plan http://xmlns.oracle.com/weblogic/deployment-plan/1.0/deployment-plan.xsd"
                 global-variables="false">
  <application-name>%s</application-name>
  <variable-definition>
%s  </variable-definition>
"""

VARIABLE = """    <variable>
      <name>%s</name>
      <value>%s</value>
    </variable>
"""

def build_war_plan(app_name, archive_name, context_root):
    var = 'ContextRoot_' + app_name
    xml = PLAN_HEADER % (app_name, VARIABLE % (var, context_root))
    xml += """  <module-override>
    <module-name>%s</module-name>
    <module-type>war</module-type>
    <module-descriptor external="false">
      <root-element>weblogic-web-app</root-element>
      <uri>WEB-INF/weblogic.xml</uri>
      <variable-assignment>
        <name>%s</name>
        <xpath>/weblogic-web-app/context-root</xpath>
      </variable-assignment>
    </module-descriptor>
  </module-override>
</deployment-plan>
""" % (archive_name, var)
    return xml

def build_ear_plan(app_name, archive_name, web_modules):
    variables = ''
    assignments = ''
    idx = 0
    for wm in web_modules:
        var = 'ContextRoot_%s_%d' % (app_name, idx)
        variables += VARIABLE % (var, wm['context_root'])
        assignments += """      <variable-assignment>
        <name>%s</name>
        <xpath>/application/module/web/[web-uri="%s"]/context-root</xpath>
      </variable-assignment>
""" % (var, wm['web_uri'])
        idx += 1
    xml = PLAN_HEADER % (app_name, variables)
    xml += """  <module-override>
    <module-name>%s</module-name>
    <module-type>ear</module-type>
    <module-descriptor external="false">
      <root-element>application</root-element>
      <uri>META-INF/application.xml</uri>
%s    </module-descriptor>
  </module-override>
</deployment-plan>
""" % (archive_name, assignments)
    return xml

def write_plan(app_name, xml):
    plan_dir = os.path.join(PLAN_ROOT, app_name)
    if not os.path.exists(plan_dir):
        os.makedirs(plan_dir)
    plan_path = os.path.join(plan_dir, 'plan.xml')
    f = open(plan_path, 'w')
    f.write(xml)
    f.close()
    return plan_dir, plan_path

for app in apps:
    app_name = app['name']
    absolute_path = os.path.abspath(os.path.join(current_working_dir, app['path']))
    archive_name = os.path.basename(absolute_path)

    # Offline mode doesn't validate paths; a missing file only fails at boot.
    if not os.path.exists(absolute_path):
        print ">>> WARNING: " + absolute_path + " not found, skipping " + app_name
        continue

    cd('/')
    create(app_name, 'AppDeployment')
    cd('/AppDeployment/' + app_name)
    set('SourcePath', absolute_path)
    set('StagingMode', 'stage')

    plan_xml = None
    if archive_name.endswith('.ear') and app.get('web_modules'):
        plan_xml = build_ear_plan(app_name, archive_name, app['web_modules'])
    elif archive_name.endswith('.war') and app.get('context_root'):
        plan_xml = build_war_plan(app_name, archive_name, app['context_root'])

    if plan_xml:
        plan_dir, plan_path = write_plan(app_name, plan_xml)
        set('PlanDir', plan_dir)
        set('PlanPath', plan_path)
        print ">>> " + app_name + ": deployment plan written to " + plan_path

    cd('/')
    assign('AppDeployment', app_name, 'Target', DEPLOY_TARGET)


# ==============================================================================
# COMMIT ALL CHANGES & WRITE DOMAIN TO DISK
# ==============================================================================
print ">>> Writing unified configuration to disk..."
setOption('OverwriteDomain', 'true')
writeDomain(domain_home)
closeTemplate()
print ">>> Domain successfully written to " + domain_home


# ==============================================================================
# BOOT IDENTITY FILES
# without boot.properties the managed server (and sometimes the admin
# server) stops at a username/password prompt and never finishes booting.
# WebLogic encrypts these values on first start.
# ==============================================================================
def write_boot_properties(server_name):
    sec_dir = os.path.join(domain_home, 'servers', server_name, 'security')
    if not os.path.exists(sec_dir):
        os.makedirs(sec_dir)
    bp = os.path.join(sec_dir, 'boot.properties')
    if not os.path.exists(bp):
        f = open(bp, 'w')
        f.write('username=' + WLS_USER + '\n')
        f.write('password=' + WLS_PW + '\n')
        f.close()

write_boot_properties(ADMIN_SERVER)
write_boot_properties(MANAGED_SERVER)


# ==============================================================================
# SERVER STARTUP ORCHESTRATION (Post-Write Process)
# ==============================================================================
print ">>> Starting AdminServer in the background..."

start_admin_script   = os.path.join(domain_home, 'bin', 'startWebLogic.sh')
start_managed_script = os.path.join(domain_home, 'bin', 'startManagedWebLogic.sh')
dev_null = open('/dev/null', 'r')

# no shell=True with an argument list (the shell drops the extra args),
# and stdin from /dev/null so a prompt can never hang the process.
admin_log  = open('/tmp/admin_server_startup.log', 'w')
admin_proc = subprocess.Popen([start_admin_script],
                              stdin=dev_null, stdout=admin_log, stderr=admin_log)

print ">>> Waiting for AdminServer to boot on port 7001..."
admin_up = False
for loop_idx in range(60):
    python_sleep(5)
    try:
        connect(WLS_USER, WLS_PW, 't3://127.0.0.1:7001', timeout='5000')
        print ">>> AdminServer is online and connected!"
        disconnect()
        admin_up = True
        break
    except Exception, err_conn:
        print ">>> Still waiting for AdminServer... (" + str((loop_idx + 1) * 5) + "s elapsed)"

if not admin_up:
    print ">>> ERROR: AdminServer did not come up in 300s. See /tmp/admin_server_startup.log"
    exit()

print ">>> Starting Managed Server (" + MANAGED_SERVER + ") in the background..."
managed_log  = open('/tmp/my_server_startup.log', 'w')
managed_proc = subprocess.Popen([start_managed_script, MANAGED_SERVER, 't3://127.0.0.1:7001'],
                                stdin=dev_null, stdout=managed_log, stderr=managed_log)

print ">>> Orchestration complete. Managed server log: /tmp/my_server_startup.log"