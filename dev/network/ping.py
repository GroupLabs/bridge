import subprocess

from manuf import manuf
p = manuf.MacParser(update=True)

# Define the command to execute
ip_command = "arp -a | awk '{print $2}' | sed 's/[()]//g'"
mac_command = "arp -a | awk '{print $4}' | sed 's/[()]//g'"

# Execute the command and capture the output
ip_output = subprocess.check_output(ip_command, shell=True, universal_newlines=True)
mac_output = subprocess.check_output(mac_command, shell=True, universal_newlines=True)

# Process the output to extract IP addresses
available_devices = []
for line in zip(ip_output.splitlines(), mac_output.splitlines()):
    available_devices.append(line)

for device in available_devices:
    try:
        print(f"Device IP: {device[0]}, MAC Address: {device[1]}, Device Type: {p.get_all(device[1])}")
    except ValueError:
        print(f"Device IP: {device[0]}, MAC Address: {device[1]}, Device Type: Unknown")