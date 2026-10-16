package com.example;

import javax.annotation.Resource;
import javax.servlet.ServletException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;


import javax.sql.DataSource;
import java.io.IOException;
import java.io.PrintWriter;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

@WebServlet("/emp")
public class EmpServlet extends HttpServlet {

    @Resource(lookup = "jdbc/scottDS")
    private DataSource dataSource;

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) 
            throws ServletException, IOException {
        response.setContentType("text/html;charset=UTF-8");
        PrintWriter out = response.getWriter();

        out.println("<!DOCTYPE html>");
        out.println("<html><head><title>Scott Schema - Employees</title>");
        out.println("<style>");
        out.println("body { font-family: Arial, sans-serif; margin: 40px; background: #f4f4f9; }");
        out.println("h2 { color: #333; }");
        out.println("table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }");
        out.println("th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }");
        out.println("th { background-color: #007bff; color: white; }");
        out.println("tr:hover { background-color: #f1f1f1; }");
        out.println("</style></head><body>");

        out.println("<h2>Scott Schema: Employee Directory</h2>");
        out.println("<table>");
        out.println("<tr><th>Emp ID</th><th>Name</th><th>Job</th><th>Department</th><th>Salary</th></tr>");

        String query = "SELECT e.empno, e.ename, e.job, d.dname, e.sal FROM emp e JOIN dept d ON e.deptno = d.deptno ORDER BY e.empno";

        try (Connection conn = dataSource.getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query);
             ResultSet rs = pstmt.executeQuery()) {

            while (rs.next()) {
                out.println("<tr>");
                out.println("<td>" + rs.getInt("empno") + "</td>");
                out.println("<td>" + rs.getString("ename") + "</td>");
                out.println("<td>" + rs.getString("job") + "</td>");
                out.println("<td>" + rs.getString("dname") + "</td>");
                out.println("<td>$" + rs.getDouble("sal") + "</td>");
                out.println("</tr>");
            }

        } catch (SQLException e) {
            out.println("<tr><td colspan='5' style='color:red;'>Database Error: " + e.getMessage() + "</td></tr>");
            e.printStackTrace();
        }

        out.println("</table></body></html>");
    }
}
