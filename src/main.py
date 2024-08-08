import obd
import csv
import os
import time
import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Initialize geolocator
geolocator = Nominatim(user_agent="obd_fuel_tracker")

# Path to USB drive
usb_path = "/mnt/usbdrive"

# Create logs directory if it doesn't exist
if not os.path.exists(usb_path):
    os.makedirs(usb_path)

def get_odometer_reading():
    response = connection.query(obd.commands.ODOMETER)
    if response.value:
        return response.value.magnitude
    return "N/A"

def get_fuel_level():
    response = connection.query(obd.commands.FUEL_LEVEL)
    if response.value:
        return response.value.magnitude
    return None

def get_fuel_rate():
    response = connection.query(obd.commands.FUEL_RATE)
    if response.value:
        return response.value.magnitude
    return 0

def get_location():
    try:
        location = geolocator.geocode("Current Location")
        return (location.latitude, location.longitude) if location else (0, 0)
    except GeocoderTimedOut:
        return (0, 0)

def select_driver():
    with open(f"{usb_path}/drivers.csv", 'r') as csvfile:
        drivers = csvfile.readlines()
        return drivers[int(input(f"Select driver (1-{len(drivers)}): ")) - 1].strip()

# Logging functions

def log_failure(failure_type):
    with open(f"{usb_path}/connection_failures.csv", 'a', newline='') as csvfile:
        fieldnames = ['Timestamp', 'Odometer Reading',"Failure Type"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()
        writer.writerow({'Timestamp': datetime.now(), 'Odometer Reading': get_odometer_reading(), 'Failure Type': failure_type})


def log_trip_start(driver, trip_id, odometer_start):
    with open(f"{usb_path}/trip_{trip_id}.csv", 'w', newline='') as csvfile:
        fieldnames = ['Driver', 'Start Time', 'End Time', 'Start Location', 'End Location', 'Start Odometer', 'End Odometer', 'Total Fuel Burn (L)']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({'Driver': driver, 'Start Time': datetime.now(), 'End Time': '', 'Start Location': get_location(), 'End Location': '', 'Start Odometer': odometer_start, 'End Odometer': '', 'Total Fuel Burn (L)': 0})

def update_trip_end(trip_id, log_timestamp, end_location, odometer_end, total_fuel_burn):
    temp_file = f"{usb_path}/trip_{trip_id}.csv"
    temp_output = f"{usb_path}/trip_{trip_id}_temp.csv"

    with open(temp_file, 'r', newline='') as csvfile, open(temp_output, 'w', newline='') as tempcsvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(tempcsvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            if row['End Time'] == '':
                row['End Time'] = log_timestamp
                row['End Location'] = end_location
                row['End Odometer'] = odometer_end
                row['Total Fuel Burn (L)'] = total_fuel_burn
            writer.writerow(row)

    os.replace(temp_output, temp_file)


def log_refill_event(odometer_reading, previous_fuel_level, current_fuel_level, fuel_usage_per_driver):
    with open(f"{usb_path}/refill_events.csv", 'a', newline='') as csvfile:
        fieldnames = ['Timestamp', 'Odometer Reading', 'Previous Fuel Level (%)', 'Current Fuel Level (%)'] + list(fuel_usage_per_driver.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()
        row = {'Timestamp': datetime.now(), 'Odometer Reading': odometer_reading, 'Previous Fuel Level (%)': previous_fuel_level, 'Current Fuel Level (%)': current_fuel_level}
        row.update(fuel_usage_per_driver)
        writer.writerow(row)


def main():

    # Try to connect to OBD for 30 seconds
    start_time = time.time()
    global connection
    connection = obd.OBD()
    while not connection.is_connected() and (time.time() - start_time) < 30:
        time.sleep(1)
        connection = obd.OBD()

    if not connection.is_connected():
        log_failure("Connection Timeout")
        # exit()

    trip_id = int(time.time())
    current_driver = select_driver()
    print(f"Tracking fuel usage for {current_driver}")

    odometer_start = get_odometer_reading()
    log_trip_start(current_driver, trip_id, odometer_start)

    total_fuel_burn = 0
    previous_log_timestamp = datetime.now()

    while True:
        fuel_rate = get_fuel_rate()
        if fuel_rate:
            end_location = get_location()
            odometer_end = get_odometer_reading()

            time.sleep(max(0, 0.05 - (time.time() - previous_log_timestamp)))  # maintain 0.05s loop cycle

            log_timestamp = datetime.now()
            total_fuel_burn += (fuel_rate * (log_timestamp-previous_log_timestamp)) / 3600  # converting L/h to L
            update_trip_end(trip_id, log_timestamp, end_location, odometer_end, total_fuel_burn)
            previous_log_timestamp = log_timestamp
        else:
            log_failure("Fuel Rate Unavailable")
            # break


if __name__ == "__main__":
    main()