package com.example.ejb;

import javax.ejb.Stateless;

@Stateless
public class GreetingServiceBean implements GreetingService {

    @Override
    public String constructGreeting(String name) {
        if (name == null || name.trim().isEmpty()) {
            name = "Enterprise User";
        }
        return "Hello, " + name + "! Welcome to JavaEE EJB Architecture.";
    }
}
