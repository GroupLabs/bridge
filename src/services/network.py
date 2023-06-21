import subprocess
from manuf import manuf

class NETWORK:
    def __init__(self):

        self.p = manuf.MacParser(update=True)

        # Define the command to execute
        self.ip_command = "arp -a | awk '{print $2}' | sed 's/[()]//g'"
        self.mac_command = "arp -a | awk '{print $4}' | sed 's/[()]//g'"

    def ping_network(self):
        ## Find all devices on the network

        # Execute the command and capture the output
        ip_output = subprocess.check_output(self.ip_command, shell=True, universal_newlines=True)
        mac_output = subprocess.check_output(self.mac_command, shell=True, universal_newlines=True)

        # Process the output to extract IP addresses
        available_devices = []
        for line in zip(ip_output.splitlines(), mac_output.splitlines()):
            available_devices.append(line)

        return available_devices

    def get_network_device_descriptions(self):
        devices = self.ping_network()

        device_descriptions = []

        # print(f"Device IP: {device[0]}, MAC Address: {device[1]}, Device Type: {self.p.get_all(device[1]).manuf_long}")

        for device in devices:
            try:
                device_descriptions.append((device[0], device[1], self.p.get_all(device[1]).manuf_long))
            except ValueError:
                device_descriptions.append((device[0], device[1], "Unknown"))

        return device_descriptions

if __name__ == "__main__":
    from pprint import pprint

    print("Performing tests on NETWORK class")

    n = NETWORK()

    print("\nTesting ping_network() method\n")
    pprint(n.ping_network())
    print('-'*50)

    print("\nTesting get_network_device_descriptions() method\n")
    pprint(n.get_network_device_descriptions())
    print('-'*50)

    print("\nTests complete")