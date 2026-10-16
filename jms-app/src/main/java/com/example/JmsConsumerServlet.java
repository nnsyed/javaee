package com.example;

import javax.annotation.Resource;
import javax.jms.ConnectionFactory;
import javax.jms.JMSContext;
import javax.jms.Queue;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.PrintWriter;

@WebServlet("/jms/receive")
public class JmsConsumerServlet extends HttpServlet {

    // 'name' = the reference declared in web.xml (java:comp/env/jms/connectionFactory).
    // weblogic.xml maps it to jms/CF; jboss-web.xml maps it to java:/JmsXA.
    @Resource(name = "jms/connectionFactory")
    private ConnectionFactory connectionFactory;

    // Maps to the resource-env-ref jms/scottQueue in web.xml.
    @Resource(name = "jms/scottQueue")
    private Queue scottQueue;

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        response.setContentType("text/html;charset=UTF-8");
        PrintWriter out = response.getWriter();

        out.println("<h2>JMS Queue Consumer</h2>");

        try (JMSContext context = connectionFactory.createContext()) {
            // Wait up to 1 second for a message
            String message = context.createConsumer(scottQueue).receiveBody(String.class, 1000);

            if (message != null) {
                out.println("<p style='color:green; font-size:18px;'>Received Message: <b>"
                        + escapeHtml(message) + "</b></p>");
            } else {
                out.println("<p>No messages currently in the queue.</p>");
            }

        } catch (Exception e) {
            // getMessage() is often null for JMS/JNDI errors; show the type too.
            out.println("<p style='color:red;'>JMS Error: " + e.getClass().getName()
                    + ": " + escapeHtml(String.valueOf(e.getMessage())) + "</p>");
            log("JMS receive failed", e);
        }

        // Build the link from the real context root instead of hard-coding it.
        out.println("<p><a href='" + request.getContextPath()
                + "/jms/send?msg=TestMessage'>Send another message</a></p>");
    }

    private static String escapeHtml(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\"", "&quot;").replace("'", "&#39;");
    }
}