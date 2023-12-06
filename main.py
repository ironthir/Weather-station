import requests
import json
import schedule
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from enum import Enum

from matplotlib.dates import DateFormatter
from matplotlib.ticker import MaxNLocator

POLLUTION_SENSOR_ID = 56949
WEATHER_SENSOR_ID = 56950

JSON_PATH = 'localSensor.json'

INTERVAL_SECONDS = 300


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
    sortedData = sorted(existing_data, key=lambda x: x["timestamp"])
    with open(JSON_PATH, 'w') as file:
        json.dump(sortedData, file, indent=2)


TITLES = ["Temperatura - 24H",  "Ciśnienie - 24h", "Wilgotność - 24h", "Temperatura - 7d", "Ciśnienie - 7d", "Wilgotność - 7d"]
Y_LABELS = ["°C", ""]

def display_multiple_graphs(data_sets):
    def round_to_nearest_hour(dt):
        return dt.replace(second=0, microsecond=0, minute=0)
    num_rows = 3
    num_cols = 3

    fig, axes = plt.subplots(num_rows, num_cols, figsize=(12, 8))
    fig.suptitle("Pogoda w ostatnim czasie", fontsize=16)

    for i, (x_values, y_values) in enumerate(data_sets):
        row = i // num_cols
        col = i % num_cols

        axes[row, col].plot(x_values, y_values)
        axes[row, col].grid(True)
        print(row)
        if row % 2 == 0:
            axes[row, col].xaxis.set_major_locator(plt.MaxNLocator(4))
            axes[row, col].set_xticklabels([])  # Remove default x-axis labels

            # Set custom x-axis labels
            hours_delta = 6
            last_datetime = datetime.now()
            start_datetime = (last_datetime - timedelta(hours=24)).replace(minute=0, second=0, microsecond=0)
            custom_ticks = [start_datetime + timedelta(hours=i * hours_delta) for i in range(5)]
            axes[row, col].set_xticks(custom_ticks)
            axes[row, col].set_xticklabels([dt.strftime('%H:%M') for dt in custom_ticks])
        if row % 2 == 1:
            # Customize x-axis ticks
            axes[row, col].xaxis.set_major_locator(plt.MaxNLocator(7))
            axes[row, col].set_xticklabels([])  # Remove default x-axis labels

            # Set custom x-axis labels for the last 7 days, at midnight
            midnight_ticks = [datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i) for
                              i in range(7)]
            axes[row, col].set_xticks(midnight_ticks)
            axes[row, col].set_xticklabels([dt.strftime('%d/%m') for dt in midnight_ticks])

    plt.tight_layout(rect=[0, 0, 1, 0.96])  # Adjust layout to prevent overlap
    plt.show()





def getExistingData():
    try:
        with open(JSON_PATH, 'r') as file:
            existing_data = json.load(file)
    except FileNotFoundError:
        existing_data = []

    return existing_data

def constructDataAndShowPlots(dataInOrder):
    for item in dataInOrder:
        item["timestamp"] = datetime.fromisoformat(item["timestamp"])
    current_time = datetime.now()
    last_24h = [item for item in dataInOrder if current_time - item["timestamp"] <= timedelta(days=1)]
    last_7days = [item for item in dataInOrder if current_time - item["timestamp"] <= timedelta(days=7)]

    lastDayAxis = np.arange(current_time - timedelta(hours=24), current_time, timedelta(hours=6))



    #last7DaysAxis = np.arange(current_time - timedelta(days=7), current_time, timedelta(hours=12))
    #last7DayAxisFormatted = [np.datetime64(dt).astype(datetime).strftime("%m/%d") for dt in last7DaysAxis]

    dataSets = [([item["timestamp"] for item in last_24h], [float(x["temperature"]) for x in last_24h]),
                ([item["timestamp"] for item in last_24h], [float(x["pressure"])/100 for x in last_24h]),
                ([item["timestamp"] for item in last_24h], [float(x["humidity"]) for x in last_24h]),
                ([item["timestamp"] for item in last_7days], [float(x["temperature"]) for x in last_7days]),
                ([item["timestamp"] for item in last_7days], [float(x["pressure"]) / 100 for x in last_7days]),
                ([item["timestamp"] for item in last_7days], [float(x["humidity"]) for x in last_7days]),

                ]
    display_multiple_graphs(dataSets)



def my_function():
    data = fetch_data_from_api()
    appendToJsonFile(data)
    #dataInOrder = getExistingData()
    #constructDataAndShowPlots(dataInOrder)


schedule.every(INTERVAL_SECONDS).seconds.do(my_function)

while True:
    schedule.run_pending()
    time.sleep(1) 
