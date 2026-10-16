import java.io.IOException;
import java.net.InetAddress;

public class JPing {
    public static void main(String[] args) {
        String host = "google.com";
        int timeout = 3000; // in milliseconds

        try {
            InetAddress inet = InetAddress.getByName(host);
            System.out.println("Sending Ping to " + host + " (" + inet.getHostAddress() + ") ...");
            
            boolean reachable = inet.isReachable(timeout);
            if (reachable) {
                System.out.println("Host is reachable.");
            } else {
                System.out.println("Host is not reachable or blocked by firewall.");
            }
        } catch (IOException e) {
            System.out.println("Exception: " + e.getMessage());
        }
    }
}

