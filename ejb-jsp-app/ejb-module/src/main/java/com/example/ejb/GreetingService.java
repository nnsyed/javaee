package com.example.ejb;

import javax.ejb.Local;

@Local
public interface GreetingService {
    String constructGreeting(String name);
}
