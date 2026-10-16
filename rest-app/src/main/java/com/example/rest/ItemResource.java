package com.example.rest;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import javax.ws.rs.Consumes;
import javax.ws.rs.GET;
import javax.ws.rs.POST;
import javax.ws.rs.Path;
import javax.ws.rs.Produces;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;

@Path("/items")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ItemResource {

    private static final ConcurrentHashMap<String, Item> store = new ConcurrentHashMap<>();

    static {
        store.put("101", new Item("101", "Enterprise Server License", 4999.99));
        store.put("102", new Item("102", "Developer Workstation", 1250.00));
    }

    @GET
    public List<Item> getAllItems() {
        return new ArrayList<>(store.values());
    }

    @POST
    public Response createItem(Item item) {
        if (item == null || item.getId() == null) {
            return Response.status(Response.Status.BAD_REQUEST).entity("Invalid item payload").build();
        }
        store.put(item.getId(), item);
        return Response.status(Response.Status.CREATED).entity(item).build();
    }
}
