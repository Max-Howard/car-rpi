import obd
import time

# Enable logging
obd.logger.setLevel(obd.logging.DEBUG)

# Find all available OBD2 ports
ports = obd.scan_serial()
print("Available ports:", ports)

if not ports:
    print("No OBD2 devices found. Ensure the device is properly connected and visible as a COM port.")
    exit()

# Attempt to connect to the first available port
connection = obd.OBD(ports[0])

if not connection.is_connected():
    print("Failed to connect to the OBD2 scanner.\nExiting program.")
    exit()
else:
    print("Successfully connected to the OBD2 scanner!")

# Send a command to the car
try:
    while True:
        time.sleep(1)
        cmd = obd.commands.RPM
        response = connection.query(cmd)

        if response and response.value is not None:
            print("Engine RPM:", response.value)
        else:
            print("Failed to retrieve RPM data or no data received.")
except KeyboardInterrupt:
    print("Exiting program.")
    connection.close()

# Close the connection
connection.close()
