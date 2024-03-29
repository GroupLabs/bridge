Steps to spin up VM and set it up so you can connect to MySql

1. configure vm in azure, specifying the right inbound permissions in network settings
2. connect to vm using rdp, install mysql server and mysql workbench
3. find my.imi and add bind-address=0.0.0.0 under [mysqld] section
4. Run CREATE USER 'username'@'host' IDENTIFIED BY 'password'; where host is local IP
5. Run GRANT ALL PRIVILEGES ON database_name.* TO 'username'@'host';
6. add local IP address to a port rule after the vm is operational. Add 3306 (mysql standard ip) as destination port
7. connect to the server locally using vm's IP as the host for mysql connection (in python)