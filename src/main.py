import obd
import os
import csv
import json
import time
from typing import Optional


LOG_PATH = "./logs/"
JSON_WRITE_INTERVAL = 15  # seconds

# Create logs directory if it doesn't exist
if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)


def read_json(filename: str = "trips") -> dict:
    with open(f"{LOG_PATH}/{filename}.json", "r") as f:
        return json.load(f)


def save_trip_to_json(filename: str = "trips") -> None:
    """
    Updates the trips json file with the current trip data.
    """
    with open(f"{LOG_PATH}/{filename}.json", "r") as f:
        trips_data = json.load(f)
    trips_data[current_trip_id] = current_trip
    with open(f"{LOG_PATH}/{filename}.json", "w") as f:
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


def get_location():
    return 1  # TODO: Implement location retrieval


def load_drivers():
    global drivers
    drivers = {}
    with open(f"{LOG_PATH}/drivers.csv", "r") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip the header row
        for row in reader:
            driver_id = int(row[0])
            driver_name = row[1]
            drivers[driver_id] = {"name": driver_name, "fuel_usage": 0}


def select_driver() -> int:
    current_driver_id = drivers[input(f"Select driver (1-{len(drivers)}): ")]
    return current_driver_id


def track_fuel_usage():
    global current_trip
    response = connection.query(obd.commands.FUEL_RATE)
    if response.value:
        current_time = time.time()
        last_update_time = current_trip["End Time"]
        fuel_rate = response.value.magnitude
        fuel_burn_since_last_update = fuel_rate * (current_time - last_update_time) / 3600  # converting L/h to L
        current_trip.update(
            {"End Time": current_time, "Total Fuel Burn (L)": current_trip["Total Fuel Burn (L)"] + fuel_burn_since_last_update}
        )
    else:
        log_failure("Fuel Rate Unavailable")


def update_trip_end() -> Optional[float]:
    odometer_reading = get_odometer_reading()
    current_location = get_location()
    current_fuel_level = get_fuel_level()
    if current_location and odometer_reading and current_fuel_level:  # Do not overwrite if any of the values are None
        current_trip.update({"End Odometer": odometer_reading, "End Location": current_location})
        save_trip_to_json()
        print("JSON Write Successful")
        last_json_update = time.time()
    else:
        print("JSON Write Failed")
        log_failure("Location, Odometer Reading, or Current Fuel Level Unavailable")
        last_json_update = None
    return last_json_update


# Logging functions


def log_failure(failure_type):
    print(f"Logging Failure: {failure_type}")
    with open(f"{LOG_PATH}/connection_failures.csv", "a", newline="") as csvfile:
        fieldnames = ["Timestamp", "Failure Type"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:
            writer.writeheader()
        writer.writerow({"Timestamp": time.time(), "Failure Type": failure_type})


def log_trip_start():
    """
    Loads the trips json file and updates it with the start of a new trip.
    """
    current_driver_id = select_driver()

    while True:
        odometer_start = get_odometer_reading()
        location_start = get_location()
        fuel_level_start = get_fuel_level()
        if odometer_start and location_start and fuel_level_start:
            break
        log_failure("Location, Odometer Reading, or Current Fuel Level Unavailable")

    global current_trip
    global current_trip_id
    current_trip_id = int(time.time())
    time_start = current_trip_id
    current_trip = {
        "Driver_ID": current_driver_id,
        "Start Time": time_start,
        "End Time": time.time(),
        "Start Location": location_start,
        "End Location": location_start,
        "Start Odometer": odometer_start,
        "End Odometer": odometer_start,
        "Fuel Level End": fuel_level_start,  # Initially fuel level at start of trip is same as end
        "Total Fuel Burn (L)": 0,
    }

    save_trip_to_json()
    print(f"Tracking fuel usage for {drivers[current_driver_id]['name']}")


def log_refill_event(trips, previous_fuel_level, current_fuel_level):
    trips = read_json()
    if len(trips) < 0:
        return

    previous_trip_id = max(trips.keys())
    previous_trip = trips[previous_trip_id]
    previous_fuel_level = previous_trip["fuel_level_end"]
    current_fuel_level = get_fuel_level()

    if previous_fuel_level < current_fuel_level - 5:  # Fuel level has increased by more than 5% since last trip
        print("Refuel event detected")
        total_fuel_burn = 0
        for trip in trips:
            drivers[trip["Driver_ID"]]["fuel_usage"] += trip["Total Fuel Burn (L)"]
            total_fuel_burn += trip["Total Fuel Burn (L)"]

        with open(f"{LOG_PATH}/refill_events.csv", "a", newline="") as csvfile:
            fieldnames = [
                "Timestamp",
                "Odometer Reading",
                "Previous Fuel Level (%)",
                "Current Fuel Level (%)",
                "Total Fuel Burn (L)",
            ] + list(drivers.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if csvfile.tell() == 0:
                writer.writeheader()
            row = {
                "Timestamp": time.time(),
                "Odometer Reading": get_odometer_reading(),
                "Previous Fuel Level (%)": previous_fuel_level,
                "Current Fuel Level (%)": current_fuel_level,
            }
            for driver_id in drivers.keys():
                row[driver_id] = drivers[driver_id]["fuel_usage"]
            writer.writerow(row)
        print("Refill event logged")


def main():
    if not connect_obd():
        print("Connection to OBD-II failed. Exiting...")
        exit()

    load_drivers()
    log_refill_event()
    log_trip_start()

    last_json_update = time.time()

    while True:
        time.sleep(max(0, 0.05 - (time.time() - current_trip["End Time"])))  # maintain 0.05s loop cycle
        track_fuel_usage()

        if time.time() - last_json_update > JSON_WRITE_INTERVAL:  # Update JSON file every JSON_WRITE_INTERVAL seconds
            last_json_update = update_trip_end()


if __name__ == "__main__":
    print(get_location())
    main()
