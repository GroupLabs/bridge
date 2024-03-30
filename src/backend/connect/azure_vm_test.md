Steps to spin up VM and set it up so you can connect to MySql

1. configure vm in azure, specifying the right inbound permissions in network settings
2. connect to vm using rdp, install mysql server and mysql workbench
3. find my.imi and add bind-address=0.0.0.0 under [mysqld] section
4. Run CREATE USER 'username'@'host' IDENTIFIED BY 'password'; where host is local IP
5. Run GRANT ALL PRIVILEGES ON database_name.* TO 'username'@'host';
6. add local IP address to a port rule after the vm is operational. Add 3306 (mysql standard ip) as destination port
7. connect to the server locally using vm's IP as the host for mysql connection (in python)

Specific steps I took for Postgres

1. ensured listen_addresses equals to '*' to listen to all IPs in postgressql.cong
2. added (at the end of the file) an extra line to pg_hba.conf to allow conections from my local IP address:
    host    all             all             my_local_ip/32            scram-sha-256
3. added an inbound rule on azure for the vm for port 5432 (postgres standard)
4. troublshot vm firewall to allow inbound connections for postgress:
    Press Win + R, type control, and press Enter to open the Control Panel.
    Navigate to System and Security > Windows Defender Firewall
    click on Advanced settings on the left pane
    click on Inbound Rules in the left
    choose 'Port' as rule type,choose 'TCP', specify port #5432, Save