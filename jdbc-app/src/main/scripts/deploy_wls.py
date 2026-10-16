connect('weblogic', 'your_admin_password', 't3://localhost:7001')
deploy('scott-app', '/path/to/target/scott-app.war', targets='AdminServer')
print("Deployed scott-app to WebLogic successfully.")
exit()
