# Overview

Web service consists of 4 parts: 
- Authentication and authorization: There are two types of users - admins and officials. Registration, login and deletion of an user (with admin priviledges) is taken care of by this part of the web service,
- Admin application: Admins take care of elections: creating them, adding participants, processing votes and generating results,
- Official application: Officials take care of submitting votes to the daemon application, and
- Daemon application: Daemon application waits (indefinetly) until an official submits votes. Once the votes come in, it checks if the votes are regular and registers them into a database.

# Implementation Details

- *Docker* containers are used for each application to run separately. It is ensured that no container can access something outside of its scope. Databases have additional volumes to store redundant data if recovering original data is needed.
- Authentication and authorization part of the web service uses *JSON Web Tokens*.
- Official application, daemon application and databases communicate through the *redis* service.
- Textual file `Docker Swarm - Komande za pokretanje.txt` contains step-by-step tutorial on setting up a *Docker Swarm* for the full web service to be run on.
