# Starting wildfly container

# 1. cleanup
sudo chown -R $(id -u):$(id -g) scripts domains artifacts
podman unshare chown -R 0:0 artifacts scripts domain
chmod -R a+rX artifacts scripts

podman rm -f $(podman ps -a | grep oracle-ai-scott | awk '{print $1}')
podman rm -f $(podman ps -a | grep wildfly-container | awk '{print $1}')
podman network rm oracle-net

# 2. run the builds
mvn clean package

# 3. Set the passwords
export ORACLE_SYS_PASSWORD=
export DB_USER_PW=

# 4. Create the docker/podman network and the start the oracle db container.
podman network create oracle-net
podman run -d  --name oracle-ai-scott --network oracle-net -p 1521:1521 -p 5500:5500 -e ORACLE_PWD=$ORACLE_SYS_PASSWORD -v $HOME/oradata:/opt/oracle/oradata:Z localhost/oracle-ai-scott:v1

# 5. Run the container
podman run -d --name wildfly-container \
  --network oracle-net \
  -p 8080:8080 -p 9001:9001 -p 9990:9990 \
  -v "$PWD/scripts":/opt/jboss/scripts:Z \
  -v "$PWD/artifacts":/opt/jboss/artifacts:Z \
  -v "$PWD/scripts/db":/opt/jboss/db:Z \
  -e DB_PW="$DB_USER_PW" \
  localhost/wildfly-admin:26

# Wait until the Domain Controller answers
until podman exec wildfly-container /opt/jboss/wildfly/bin/jboss-cli.sh -c \
      ":read-attribute(name=launch-type)" 2>/dev/null | grep -q DOMAIN; do
  echo "waiting for WildFly..."; sleep 5
done

# Confirm the version: it should print 26.1.3.Final
podman exec wildfly-container /opt/jboss/wildfly/bin/jboss-cli.sh -c ":read-attribute(name=product-version)"

# 6. Configure and deploy
# a. Create a management user, for the console and remote CLI:
podman exec wildfly-container /opt/jboss/wildfly/bin/add-user.sh -u admin -p 'YourPassword1!' -s

# b. Create the Oracle JDBC driver module. The CLI must be disconnected here, so there’s no -c:
podman exec wildfly-container /opt/jboss/wildfly/bin/jboss-cli.sh \
  --command="module add --name=com.oracle.ojdbc --resources=/opt/jboss/db/ojdbc11-23.26.3.0.0.jar --dependencies=javax.api,javax.transaction.api"

# c. Put the host controller’s name into the script. WildFly 26 may name it master rather than primary. # This reads the actual name and updates hostName in prerequisite for you:
HOST=$(podman exec wildfly-container /opt/jboss/wildfly/bin/jboss-cli.sh -c \
       ":read-children-names(child-type=host)" | tr -d '\n' | sed -n 's/.*"result" => \[ *"\([^"]*\)".*/\1/p')
echo "Host controller: $HOST"
sed -i "s/^set hostName=.*/set hostName=$HOST/" scripts/jboss/setup_domain.cli

# d. run the script 
podman exec wildfly-container /opt/jboss/wildfly/bin/jboss-cli.sh -c \
  --file=/opt/jboss/scripts/jboss/setup_domain.cli


# Runtime URLS:

http://localhost:9001/servlet/hello

http://localhost:9001/ejb-app/index.jsp
http://localhost:9001/ejb-app/greet

http://localhost:9001/restapp/api/items

http://localhost:9001/scottdbapp/emp

http://localhost:9001/scottapp/
http://localhost:9001/scottapp/emp
http://localhost:9001/scottapp/jms/send

http://localhost:9001/scottapp/jms/receive




# --------------------------------------------------------------------------------------
# image setup instructions
# --------------------------------------------------------------------------------------

# Step 1: Build the image
Create container/Containerfile:

# --------------------------------------------------------------------------------
# WildFly 26.1.3 = Java EE 8 (javax.*), matching WebLogic 14.1.x
FROM quay.io/wildfly/wildfly:26.1.3.Final-jdk11

# Mount points for the scripts, artifacts and JDBC driver
USER root
RUN mkdir -p /opt/jboss/scripts /opt/jboss/artifacts /opt/jboss/db && \
    chown -R jboss:jboss /opt/jboss/scripts /opt/jboss/artifacts /opt/jboss/db
USER jboss

# Start in managed domain mode, listening on all interfaces
CMD ["/opt/jboss/wildfly/bin/domain.sh", "-b", "0.0.0.0", "-bmanagement", "0.0.0.0"]
# --------------------------------------------------------------------------------

# build the image
podman build -t localhost/wildfly-admin:26 -f container/Containerfile container/

