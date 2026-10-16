# ==============================================================================
# create_domain.py  (WLST OFFLINE)
# Creates the domain, servers, cluster, JDBC DataSource and JMS resources.
#
# Usage:
#   WLS_USER='weblogic' WLS_PW='WlsPass' DB_PW='tiger' wlst.sh create_domain.py
# ==============================================================================
import os
import shutil

WLS_USER = os.environ.get('WLS_USER', 'weblogic')
WLS_PW   = os.environ.get('WLS_PW')
DB_PW    = os.environ.get('DB_PW')

if not WLS_PW or not DB_PW:
    print "ERROR: WLS_PW or DB_PW environment variables are not set!"
    print "Execute using: WLS_USER='weblogic' WLS_PW='WlsPass' DB_PW='tiger' wlst.sh create_domain.py"
    exit(exitcode=1)

domain_home    = os.environ.get('DOMAIN_HOME', '/u01/oracle/user_projects/domains/base_domain')
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

# Administration Server
cd('/Servers/' + ADMIN_SERVER)
set('ListenAddress', '0.0.0.0')
set('ListenPort', 7001)

# Cluster
cd('/')
create(CLUSTER, 'Cluster')

# Managed Server
cd('/')
create(MANAGED_SERVER, 'Server')
cd('/Servers/' + MANAGED_SERVER)
set('ListenAddress', '0.0.0.0')
set('ListenPort', 9001)

cd('/')
assign('Server', MANAGED_SERVER, 'Cluster', CLUSTER)

# JRF server group for the managed server
try:
    setServerGroups(MANAGED_SERVER, ['JRF-MAN-SVR'])
except Exception, err_sg:
    print ">>> Warning: could not set JRF server group on " + MANAGED_SERVER + ": " + str(err_sg)

# Admin credentials
cd('/Security/base_domain/User/weblogic')
if WLS_USER != 'weblogic':
    cmo.setName(WLS_USER)
cmo.setPassword(WLS_PW)


# ==============================================================================
# PHASE 2: JDBC
# ==============================================================================
print ">>> Phase 2: Building JDBC resources..."

DS_NAME = 'scottDS'
DS_ROOT = '/JDBCSystemResource/' + DS_NAME + '/JdbcResource/' + DS_NAME

cd('/')
create(DS_NAME, 'JDBCSystemResource')
cd(DS_ROOT)
cmo.setName(DS_NAME)

cd(DS_ROOT)
create('dsParams', 'JDBCDataSourceParams')
cd('JDBCDataSourceParams/NO_NAME_0')
set('JNDIName', 'jdbc/scottDS')
set('GlobalTransactionsProtocol', 'OnePhaseCommit')

cd(DS_ROOT)
create('driverParams', 'JDBCDriverParams')
cd('JDBCDriverParams/NO_NAME_0')
set('DriverName', 'oracle.jdbc.OracleDriver')
set('URL', 'jdbc:oracle:thin:@//oracle-ai-scott:1521/FREEPDB1')
set('PasswordEncrypted', DB_PW)

create('driverProps', 'Properties')
cd('Properties/NO_NAME_0')
create('user', 'Property')
cd('Property/user')
set('Value', 'scott')

cd(DS_ROOT)
create('poolParams', 'JDBCConnectionPoolParams')
cd('JDBCConnectionPoolParams/NO_NAME_0')
set('TestTableName', 'SQL SELECT 1 FROM DUAL')
set('TestConnectionsOnReserve', 'true')

cd('/')
assign('JDBCSystemResource', DS_NAME, 'Target', CLUSTER)


# ==============================================================================
# PHASE 2: JMS
# ==============================================================================
print ">>> Phase 2: Building JMS resources..."

JMS_SERVER = 'ScottJMSServer'
JMS_STORE  = 'ScottFileStore'
JMS_MODULE = 'ScottJMSModule'
SUBDEPLOY  = 'ScottSubDeployment'

cd('/')
create(JMS_STORE, 'FileStore')
cd('/FileStores/' + JMS_STORE)
set('Directory', JMS_STORE)
cd('/')
assign('FileStore', JMS_STORE, 'Target', MANAGED_SERVER)

cd('/')
create(JMS_SERVER, 'JMSServer')
cd('/JMSServers/' + JMS_SERVER)
set('PersistentStore', JMS_STORE)
cd('/')
assign('JMSServer', JMS_SERVER, 'Target', MANAGED_SERVER)

cd('/')
create(JMS_MODULE, 'JMSSystemResource')
cd('/')
assign('JMSSystemResource', JMS_MODULE, 'Target', CLUSTER)

cd('/JMSSystemResource/' + JMS_MODULE)
create(SUBDEPLOY, 'SubDeployment')
cd('/')
assign('JMSSystemResource.SubDeployment', JMS_MODULE + '.' + SUBDEPLOY, 'Target', JMS_SERVER)

cd('/JMSSystemResource/' + JMS_MODULE + '/JmsResource/NO_NAME_0')
cf = create('ScottCF', 'ConnectionFactory')
cf.setJNDIName('jms/CF')
cf.setSubDeploymentName(SUBDEPLOY)

cd('/JMSSystemResource/' + JMS_MODULE + '/JmsResource/NO_NAME_0')
queue = create('ScottQueueParams', 'Queue')
queue.setJNDIName('jms/scottQueue')
queue.setSubDeploymentName(SUBDEPLOY)


# ==============================================================================
# WRITE DOMAIN TO DISK
# ==============================================================================
print ">>> Writing domain to disk..."
setOption('OverwriteDomain', 'true')
writeDomain(domain_home)
closeTemplate()


# ==============================================================================
# BOOT IDENTITY FILES (so servers start without prompting)
# WebLogic encrypts these values on first start.
# ==============================================================================
def write_boot_properties(server_name):
    sec_dir = os.path.join(domain_home, 'servers', server_name, 'security')
    if not os.path.exists(sec_dir):
        os.makedirs(sec_dir)
    bp = os.path.join(sec_dir, 'boot.properties')
    f = open(bp, 'w')
    f.write('username=' + WLS_USER + '\n')
    f.write('password=' + WLS_PW + '\n')
    f.close()

write_boot_properties(ADMIN_SERVER)
write_boot_properties(MANAGED_SERVER)

print ">>> Domain successfully created at " + domain_home
exit(exitcode=0)