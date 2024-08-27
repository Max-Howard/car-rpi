import obd
import os
import csv
import json
import time
#from datetime import datetime

LOG_PATH = "./logs/"

# Create logs directory if it doesn't exist
if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)

def read_json(filename:str = "trips") -> dict:
    with open(f"{LOG_PATH}/{filename}.json", 'r') as f:
        return json.load(f)

def update_trip_json(filename:str = "trips") -> None:
    with open(f"{LOG_PATH}/{filename}.json", 'r') as f:
        trips_data = json.load(f)
    trips_data[current_trip_id]= current_trip
    with open(f"{LOG_PATH}/{filename}.json", 'w') as f:
        json.dump(trips_data, f)

def connect_obd():
    start_time = time.time()
    global connection
    while (time.time() - start_time) < 30:
        connection = obd.OBD()
        if connection.is_connected():
            return True
        time.sleep(1)
    log_failure("Connection Timeout")
    return False

def get_odometer_reading():
    response = connection.query(obd.commands.ODOMETER)
    if not response.is_null():
        return response.value.magnitude
    return None

def get_fuel_level():
    response = connection.query(obd.commands.FUEL_LEVEL)
    if response.value:
        return response.value.magnitude
    return None

def get_fuel_rate():
    response = connection.query(obd.commands.FUEL_RATE)
    if response.value:
        return response.value.magnitude
    return None

def get_location():
    return 1    # TODO: Implement location retrieval

def select_driver():
    return 1 #TODO: Implement driver selection
    with open(f"{LOG_PATH}/drivers.csv", 'r') as csvfile:
        drivers = csvfile.readlines()
        return drivers[int(input(f"Select driver (1-{len(drivers)}): ")) - 1].strip()

# Logging functions

def log_failure(failure_type):
    with open(f"{LOG_PATH}/connection_failures.csv", 'a', newline='') as csvfile:
        fieldnames = ['Timestamp',"Failure Type"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()
        writer.writerow({'Timestamp': time.time(), 'Failure Type': failure_type})


def log_trip_start(current_driver):
    """
    Loads the trips json file and updates it with the start of a new trip.
    """
    odometer_start = get_odometer_reading()
    location_start = get_location()
    if not odometer_start or not location_start:
        log_failure("Location or Odometer Reading Unavailable")
        return False

    global current_trip
    global current_trip_id
    current_trip_id = int(time.time())
    time_start = time.time()
    current_trip = {
        "Driver": current_driver,
        "Start Time": time_start,
        "End Time": time_start,
        "Start Location": location_start,
        "End Location": location_start,
        "Start Odometer": odometer_start,
        "End Odometer": odometer_start,
        "Total Fuel Burn (L)": 0
        }

    update_trip_json()
    return True


# def log_refill_event(odometer_reading, previous_fuel_level, current_fuel_level, fuel_usage_per_driver):
#     with open(f"{LOG_PATH}/refill_events.csv", 'a', newline='') as csvfile:
#         fieldnames = ['Timestamp', 'Odometer Reading', 'Previous Fuel Level (%)', 'Current Fuel Level (%)'] + list(fuel_usage_per_driver.keys())
#         writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
#         if csvfile.tell() == 0:
#             writer.writeheader()
#         row = {'Timestamp': datetime.now(), 'Odometer Reading': odometer_reading, 'Previous Fuel Level (%)': previous_fuel_level, 'Current Fuel Level (%)': current_fuel_level}
#         row.update(fuel_usage_per_driver)
#         writer.writerow(row)


def main():
    current_driver = select_driver()
    print(f"Tracking fuel usage for {current_driver}")

    if not connect_obd():
        print("Connection to OBD-II failed. Exiting...")
        exit()

    trip_started = False
    while not trip_started:
        trip_started = log_trip_start(current_driver)

    last_json_write = time.time()

    while True:
        fuel_rate = get_fuel_rate()
        if fuel_rate:
            current_time = time.time()
            last_update_time = current_trip['End Time']
            fuel_burn_since_last_update = fuel_rate * (current_time - last_update_time) / 3600  # converting L/h to L
            current_trip.update({
                'End Time': current_time,
                'Total Fuel Burn (L)': current_trip['Total Fuel Burn (L)'] + fuel_burn_since_last_update
                })

            if current_time - last_json_write > 60:
                odometer_reading = get_odometer_reading()
                current_location = get_location()
                if current_location and odometer_reading:
                    current_trip.update({'End Odometer': odometer_reading,"End Location": current_location})
                    update_trip_json()
                    last_json_write = current_time
                else:
                    log_failure("Location or Odometer Reading Unavailable")
            time.sleep(max(0, 0.05 - (time.time() - last_update_time)))  # maintain 0.05s loop cycle

        else:
            log_failure("Fuel Rate Unavailable")
            # break


if __name__ == "__main__":
    print(get_location())
    main()