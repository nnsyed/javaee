<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<!DOCTYPE html>
<html>
<head>
    <title>EJB + Servlet + JSP App</title>
</head>
<body>
    <h2>JavaEE EJB + Servlet + JSP Application</h2>
    
    <form action="greet" method="POST">
        <label for="username">User Name:</label>
        <input type="text" id="username" name="username" />
        <input type="submit" value="Invoke EJB" />
    </form>

    <% 
        String message = (String) request.getAttribute("greetingMessage");
        if (message != null) {
    %>
        <hr/>
        <h3>Response from EJB:</h3>
        <p style="color: green;"><%= message %></p>
    <% 
        } 
    %>
</body>
</html>
