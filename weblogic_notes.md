
# 1. cleanup
sudo chown -R $(id -u):$(id -g) scripts domains artifacts
podman rm -f $(podman ps -a | grep oracle-ai-scott | awk '{print $1}')
podman network rm oracle-net

# 2. run the builds
mvn clean package

# 3. Set the passwords
export ORACLE_SYS_PASSWORD=YourPassword123
export WLS_USER=weblogic
export WLS_PW=Welcome1
export DB_USER_PW=tiger

# 4. Create the docker/podman network and the start the oracle db container.
podman network create oracle-net
podman run -d  --name oracle-ai-scott --network oracle-net -p 1521:1521 -p 5500:5500 -e ORACLE_PWD=$ORACLE_SYS_PASSWORD -v $HOME/oradata:/opt/oracle/oradata:Z localhost/oracle-ai-scott:v1


# 5. Run the weblogic container
podman run --rm -it \
  --name weblogic-container \
  --network oracle-net \
  -p 7001:7001 -p 9001:9001 \
  -v /home/nnsyed/t_work/javaee-applications/domains:/u01/oracle/user_projects/domains:Z,U \
  -v /home/nnsyed/t_work/javaee-applications/scripts:/u01/oracle/scripts:Z,U \
  -v /home/nnsyed/t_work/javaee-applications/artifacts:/u01/oracle/artifacts:Z,U \
  -e WLS_USER=$WLS_USER \
  -e WLS_PW=$WLS_PW \
  -e DB_PW=$DB_USER_PW \
  container-registry.oracle.com/middleware/fmw-infrastructure:14.1.2.0-jdk21-ol9-250424 \
  /bin/bash -c "/u01/oracle/oracle_common/common/bin/wlst.sh /u01/oracle/scripts/weblogic/config_domain.py; /bin/bash"


# 5. Runtime tests

http://localhost:9001/servlet/hello

http://localhost:9001/ejb-app/index.jsp
http://localhost:9001/ejb-app/greet

http://localhost:9001/restapp/api/items

http://localhost:9001/scottdbapp/emp

http://localhost:9001/scottapp/
http://localhost:9001/scottapp/emp
http://localhost:9001/scottapp/jms/send

http://localhost:9001/scottapp/jms/receive

#
# cleanup
sudo chown -R $(id -u):$(id -g) scripts domains 


#
# misc. Db connection tests
/u01/jdk/bin/javac EmpTable.java
/u01/jdk/bin/java -cp .:ojdbc11-23.26.3.0.0.jar EmpTable
