import requests
import json
import schedule
import time
from datetime import datetime, timedelta

POLLUTION_SENSOR_ID = 56949
WEATHER_SENSOR_ID = 56950

JSON_PATH = 'localSensor.json'

INTERVAL_SECONDS = 5


def filterPm10(obj):
    return True if obj["value_type"] == "P1" else False


def filterPm25(obj):
    return True if obj["value_type"] == "P2" else False


def filterByTimestamp(obj, timestamp):
    return obj["timestamp"] == timestamp


def floor_to_nearest_minute(timestamp_str):
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

    minute_difference = timestamp.second + timestamp.microsecond / 1e6
    rounded_timestamp = timestamp - timedelta(seconds=minute_difference)

    return rounded_timestamp.strftime('%Y-%m-%d %H:%M:%S')


def fetch_data_from_api():
    try:
        response = requests.get(f"https://data.sensor.community/airrohr/v1/sensor/{POLLUTION_SENSOR_ID}/")
        response.raise_for_status()
        pollution = response.json()

        response = requests.get(f"https://data.sensor.community/airrohr/v1/sensor/{WEATHER_SENSOR_ID}/")
        response.raise_for_status()
        weather = response.json()
        data = []
        for res in pollution:
            pm25Obj = next(filter(filterPm25, res["sensordatavalues"]))
            pm10Obj = next(filter(filterPm10, res["sensordatavalues"]))
            customJson = {
                "timestamp": floor_to_nearest_minute(res["timestamp"]),
                "pm25": pm25Obj["value"],
                "pm10": pm10Obj["value"]
            }
            data.append(customJson)
        for item in data:
            matchingWeatherEntry = next(
                filter(lambda x: (floor_to_nearest_minute(x["timestamp"]) == item["timestamp"]), weather), None)
            if matchingWeatherEntry is not None:
                item["temperature"] = next(
                    filter(lambda x: (x["value_type"] == "temperature"), matchingWeatherEntry["sensordatavalues"]), None)["value"]
                item["pressure"] = next(
                    filter(lambda x: (x["value_type"] == "pressure"), matchingWeatherEntry["sensordatavalues"]), None)["value"]
                item["humidity"] = next(
                    filter(lambda x: (x["value_type"] == "humidity"), matchingWeatherEntry["sensordatavalues"]), None)["value"]

        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None


def appendToJsonFile(data):
    try:
        with open(JSON_PATH, 'r') as file:
            existing_data = json.load(file)
    except FileNotFoundError:
        existing_data = []

    for item in data:
        existing_data.append(item)

    with open(JSON_PATH, 'w') as file:
        json.dump(existing_data, file, indent=2)


def my_function():
    data = fetch_data_from_api()
    appendToJsonFile(data)


schedule.every(INTERVAL_SECONDS).seconds.do(my_function)

while True:
    schedule.run_pending()
    time.sleep(1) 
