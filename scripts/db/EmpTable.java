import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

public class EmpTable {

    // Connection configuration parameters
    private static final String JDBC_URL = "jdbc:oracle:thin:@//oracle-ai-scott:1521/FREEPDB1";
    private static final String USER = "scott";
    private static final String PASSWORD = "tiger"; 

    public static void main(String[] args) {
        String query = "SELECT empno, ename, job, sal, deptno FROM emp";

        System.out.println("Connecting to Oracle Database at: " + JDBC_URL);

        try {
            // Force registration of the Oracle JDBC driver to bypass service resolution limits
            Class.forName("oracle.jdbc.OracleDriver");

            // Open and automatically manage SQL resources
            try (Connection connection = DriverManager.getConnection(JDBC_URL, USER, PASSWORD);
                 Statement statement = connection.createStatement();
                 ResultSet resultSet = statement.executeQuery(query)) {

                System.out.println("\nConnection successful! Fetching records from EMP table:\n");
                System.out.printf("%-10s %-12s %-12s %-10s %-6s%n", "EMPNO", "ENAME", "JOB", "SALARY", "DEPTNO");
                System.out.println("---------------------------------------------------------");

                while (resultSet.next()) {
                    int empNo = resultSet.getInt("empno");
                    String eName = resultSet.getString("ename");
                    String job = resultSet.getString("job");
                    double salary = resultSet.getDouble("sal");
                    int deptNo = resultSet.getInt("deptno");

                    System.out.printf("%-10d %-12s %-12s %-10.2f %-6d%n", empNo, eName, job, salary, deptNo);
                }

            }
        } catch (ClassNotFoundException e) {
            System.err.println("\nError: Oracle JDBC Driver was not found on your classpath!");
            System.err.println("Verify that 'ojdbc11-23.26.3.0.0.jar' is inside the current directory.");
            e.printStackTrace();
        } catch (SQLException e) {
            System.err.println("\nDatabase operation failed!");
            System.err.println("SQLState: " + e.getSQLState());
            System.err.println("Error Code: " + e.getErrorCode());
            e.printStackTrace();
        }
    }
}
