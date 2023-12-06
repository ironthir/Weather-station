import requests
import json
import schedule
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

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

def get_data_set(data, prop):
    timestamps = [item["timestamp"] for item in data if prop in item]
    values = [float(x[prop]) for x in data if prop in x]
    return (timestamps, values)

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

def append_to_json_file(data):
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

TITLES = ["Temperatura - 24H",  "Ciśnienie - 24h", "Wilgotność - 24h", "Temperatura - 7d", "Ciśnienie - 7d",
          "Wilgotność - 7d", "PM 2.5 - 24h", "PM 10 - 24h", "PLACEHOLDER", "PM 2.5 - 7d", "PM 10 - 7d"]
Y_LABELS = ["°C", ""]

def display_plots_in_window(data_sets):
    root = tk.Tk()
    root.title("Pogoda w ostatnim czasie")


    num_rows = 4
    num_cols = 3

    for i, (x_values, y_values) in enumerate(data_sets):
        row = i // num_cols
        col = i % num_cols

        fig = Figure(figsize=(5, 3))
        ax = fig.add_subplot(111)
        ax.plot(x_values, y_values)
        ax.grid(True)
        ax.set_ylim(min(y_values) - 5, max(y_values) + 5)
        ax.set_title(TITLES[i])

        if row % 2 == 0:
            ax.xaxis.set_major_locator(plt.MaxNLocator(4))
            ax.set_xticklabels([])

            hours_delta = 6
            last_datetime = datetime.now()
            start_datetime = (last_datetime - timedelta(hours=24)).replace(minute=0, second=0, microsecond=0)
            custom_ticks = [start_datetime + timedelta(hours=i * hours_delta) for i in range(5)]
            ax.set_xticks(custom_ticks)
            ax.set_xticklabels([dt.strftime('%H:%M') for dt in custom_ticks])
        if row % 2 == 1:
            ax.xaxis.set_major_locator(plt.MaxNLocator(7))
            ax.set_xticklabels([])

            midnight_ticks = [datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i) for
                              i in range(7)]
            ax.set_xticks(midnight_ticks)
            ax.set_xticklabels([dt.strftime('%d/%m') for dt in midnight_ticks])

        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().grid(row=row, column=col)

    root.update_idletasks()  # Update the window to calculate layout
    root.update()  # Ensure the window updates before mainloop
    root.mainloop()

def get_existing_data():
    try:
        with open(JSON_PATH, 'r') as file:
            existing_data = json.load(file)
    except FileNotFoundError:
        existing_data = []

    return existing_data

def construct_data_and_show_plots(data_in_order):
    for item in data_in_order:
        item["timestamp"] = datetime.fromisoformat(item["timestamp"])
    current_time = datetime.now()
    last_24h = [item for item in data_in_order if current_time - item["timestamp"] <= timedelta(days=1)]
    last_7days = [item for item in data_in_order if current_time - item["timestamp"] <= timedelta(days=7)]

    lastDayAxis = np.arange(current_time - timedelta(hours=24), current_time, timedelta(hours=6))

    data_sets = [get_data_set(last_24h, "temperature"),
                 get_data_set(last_24h, "pressure"),
                 get_data_set(last_24h, "humidity"),
                 get_data_set(last_7days, "temperature"),
                 get_data_set(last_7days, "pressure"),
                 get_data_set(last_7days, "humidity"),
                 get_data_set(last_24h, "pm25"),
                 get_data_set(last_24h, "pm10"),
                 ([1], [1]),
                 get_data_set(last_7days, "pm25"),
                 get_data_set(last_7days, "pm10"),
                 ]
    display_plots_in_window(data_sets)

def my_function():
    data = fetch_data_from_api()
    append_to_json_file(data)
    data_in_order = get_existing_data()
    construct_data_and_show_plots(data_in_order)

schedule.every(INTERVAL_SECONDS).seconds.do(my_function)

while True:
    schedule.run_pending()
    time.sleep(1)
