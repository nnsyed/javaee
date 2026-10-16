package com.example.servlet;

import java.io.IOException;
import java.io.PrintWriter;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet(name = "HelloServlet", urlPatterns = {"/hello"})
public class HelloServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        
        response.setContentType("text/html;charset=UTF-8");
        
        String name = request.getParameter("name");
        if (name == null || name.trim().isEmpty()) {
            name = "World";
        }

        try (PrintWriter out = response.getWriter()) {
            out.println("<!DOCTYPE html>");
            out.println("<html>");
            out.println("<head><title>Servlet Application</title></head>");
            out.println("<body>");
            out.println("<h1>Hello, " + name + "!</h1>");
            out.println("<form method='GET' action='hello'>");
            out.println("<label for='name'>Enter Name: </label>");
            out.println("<input type='text' id='name' name='name' />");
            out.println("<input type='submit' value='Submit' />");
            out.println("</form>");
            out.println("</body>");
            out.println("</html>");
        }
    }
}
