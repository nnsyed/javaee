# 1. Add Oracle JDBC module / driver (assuming ojdbc11.jar is available locally)
module add --name=com.oracle.jdbc --resources=./ojdbc11.jar --dependencies=javax.api,javax.transaction.api

# 2. Register Driver in subsystem
/subsystem=datasources/jdbc-driver=oracle:add(driver-name=oracle,driver-module-name=com.oracle.jdbc,driver-class-name=oracle.jdbc.OracleDriver)

# 3. Create Data Source
data-source add \
    --name=scottDS \
    --jndi-name=java:/jboss/datasources/scottDS \
    --driver-name=oracle \
    --connection-url=jdbc:oracle:thin:@//localhost:1521/FREEPDB1 \
    --user-name=scott \
    --password=tiger \
    --valid-connection-checker-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleValidConnectionChecker \
    --exception-sorter-class-name=org.jboss.jca.adapters.jdbc.extensions.oracle.OracleExceptionSorter

echo "WildFly Data Source created successfully."

# WildFly comes with a default Connection Factory (java:/ConnectionFactory), 
# so we only need to create the JMS Queue destination.
/subsystem=messaging-activemq/server=default/jms-queue=scottQueue:add(entries=["java:/jms/queue/scottQueue"])

echo "WildFly JMS Queue created successfully."