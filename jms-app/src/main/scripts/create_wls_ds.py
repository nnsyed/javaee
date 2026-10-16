connect('weblogic', 'your_admin_password', 't3://localhost:7001')
edit()
startEdit()

# 1. Create JDBC System Resource
create('scottDS', 'JDBCSystemResource')
cd('/JDBCSystemResources/scottDS/JDBCResource/scottDS/JDBCDataSourceParams/scottDS')
set('GlobalNames', 'scottDS')

cd('/JDBCSystemResources/scottDS/JDBCResource/scottDS/JDBCDriverParams/scottDS')
set('DriverName', 'oracle.jdbc.OracleDriver')
set('URL', 'jdbc:oracle:thin:@//localhost:1521/FREEPDB1')
set('PasswordEncrypted', 'tiger')

# 2. Set Database User property
props = cmo.getProperties()
prop = create('user', 'Properties')
prop.setValue('scott')

cd('/JDBCSystemResources/scottDS/JDBCResource/scottDS/JDBCConnectionPoolParams/scottDS')
set('TestTableName', 'SQL SELECT 1 FROM DUAL')

# Target to AdminServer or cluster
assign('JDBCSystemResource', 'scottDS', 'Target', 'AdminServer')


# 3. Create JMS Server
create('ScottJMSServer', 'JMSServer')
assign('JMSServer', 'ScottJMSServer', 'Target', 'AdminServer')

# 4. Create JMS System Module & Subdeployment
create('ScottJMSModule', 'JMSSystemModule')
cd('/JMSSystemModules/ScottJMSModule')
assign('JMSSystemResource', 'ScottJMSModule', 'Target', 'AdminServer')
create('ScottSubDeployment', 'SubDeployment')
cd('SubDeployments/ScottSubDeployment')
set('Targets', jarray.array([ObjectName('com.bea:Name=ScottJMSServer,Type=JMSServer')], ObjectName))

# 5. Create Connection Factory
cd('/JMSSystemModules/ScottJMSModule/JMSResource/ScottJMSModule')
cf = create('ScottCF', 'ConnectionFactoryParams')
cf.setJNDIName('jms/CF')


# 6. Create Queue
queue = create('ScottQueueParams', 'QueueParams')
queue.setJNDIName('jms/scottQueue')
queue.setJNDICompatModeEnabled(True)


save()
activate(block="true")
print("WebLogic JDBC DataSource created successfully.")
print("WebLogic JMS resources created successfully.")
exit()