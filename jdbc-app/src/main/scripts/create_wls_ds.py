connect('weblogic', 'your_admin_password', 't3://localhost:7001')
edit()
startEdit()

# Create JDBC System Resource
create('scottDS', 'JDBCSystemResource')
cd('/JDBCSystemResources/scottDS/JDBCResource/scottDS/JDBCDataSourceParams/scottDS')
set('GlobalNames', 'scottDS')

cd('/JDBCSystemResources/scottDS/JDBCResource/scottDS/JDBCDriverParams/scottDS')
set('DriverName', 'oracle.jdbc.OracleDriver')
set('URL', 'jdbc:oracle:thin:@//localhost:1521/FREEPDB1')
set('PasswordEncrypted', 'tiger')

# Set Database User property
props = cmo.getProperties()
prop = create('user', 'Properties')
prop.setValue('scott')

cd('/JDBCSystemResources/scottDS/JDBCResource/scottDS/JDBCConnectionPoolParams/scottDS')
set('TestTableName', 'SQL SELECT 1 FROM DUAL')

# Target to AdminServer or cluster
assign('JDBCSystemResource', 'scottDS', 'Target', 'AdminServer')

save()
activate(block="true")
print("WebLogic JDBC DataSource created successfully.")
exit()