package com.example.web;

import com.example.ejb.GreetingService;
import java.io.IOException;
import javax.ejb.EJB;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet(name = "GreetingServlet", urlPatterns = {"/greet"})
public class GreetingServlet extends HttpServlet {

    @EJB
    private GreetingService greetingService;

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        
        String username = request.getParameter("username");
        String message = greetingService.constructGreeting(username);
        
        request.setAttribute("greetingMessage", message);
        request.getRequestDispatcher("/index.jsp").forward(request, response);
    }
    
    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        request.getRequestDispatcher("/index.jsp").forward(request, response);
    }
}
