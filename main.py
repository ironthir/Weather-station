import sys

import requests
import json
import schedule
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from tkinter import ttk
import numpy as np
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

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


def get_data_set(data, prop):
    timestamps = [item["timestamp"] for item in data if prop in item]

    if prop == "pressure":
        values = [float(x[prop]) / 100 for x in data if prop in x]
    else:
        values = [float(x[prop]) for x in data if prop in x]

    # Ensure timestamps are sorted
    sorted_indices = np.argsort(timestamps)
    timestamps = [timestamps[i] for i in sorted_indices]
    values = [values[i] for i in sorted_indices]

    # Insert NaN for gaps larger than 3 minutes
    for i in range(1, len(timestamps)):
        time_diff = timestamps[i] - timestamps[i - 1]
        if time_diff > timedelta(minutes=30):
            timestamps.insert(i, timestamps[i - 1] + timedelta(minutes=3))
            values.insert(i, np.nan)

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

def on_mouse_wheel(event, canvas):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

def on_horizontal_scroll(*args, canvas):
    canvas.xview(*args)

def on_closing():
    sys.exit()



def display_plots_in_window(data_sets, root, most_recent):

    num_cols = 3

    # Create vertical and horizontal scrollbars
    v_scrollbar = ttk.Scrollbar(root, orient="vertical")
    h_scrollbar = ttk.Scrollbar(root, orient="horizontal")
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar.pack(side="bottom", fill="x")

    canvas_frame = tk.Frame(root)
    canvas_frame.pack(side="left", fill="both", expand=True)

    canvas_frame.grid_rowconfigure(0, weight=1)
    canvas_frame.grid_columnconfigure(0, weight=1)

    canvas = tk.Canvas(canvas_frame, yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")

    v_scrollbar.config(command=canvas.yview)
    h_scrollbar.config(command=lambda *args: on_horizontal_scroll(canvas=canvas, *args))


    frame = tk.Frame(canvas, bg="white")
    canvas.create_window((0, 0), window=frame, anchor="nw")

    for i, (x_values, y_values) in enumerate(data_sets):
        row = i // num_cols
        col = i % num_cols
        if(x_values is None or y_values is None):
            timestamp = most_recent["timestamp"].strftime("%d/%m/%Y %H:%M")
            recentTemp = most_recent["temperature"]
            recentPressure = float(most_recent["pressure"])/100
            recentHumidity = most_recent["humidity"]
            recentPm25 = most_recent["pm25"]
            recentPm10 = most_recent["pm10"]
            label = tk.Label(frame, bg="white", text=f"Ostatni pomiar: {timestamp}\nTemperatura: {recentTemp} °C\nCiśnienie: {recentPressure} hPa\nWilgotność: {recentHumidity} %H\nPM 2.5: {recentPm25} µg/m³\nPM 10: {recentPm10} µg/m³\n", font=("Helvetica", 25), justify="left")
            label.grid(row=row, column=col, sticky="w")
            continue

        def custom_formatter(value, pos, curr_col=col, curr_row=row):
            if (curr_col % 3 == 0 and curr_row < 2):
                return f"{value} °C"
            elif curr_col % 3 == 1 and curr_row < 2:
                return f"{value} hPa"
            elif curr_col % 3 == 2 and curr_row < 2:
                return f"{value} %H"
            else:
                return f"{value} µg/m³"

        fig = Figure(figsize=(6.5, 3))
        fig.subplots_adjust(left=0.15)
        ax = fig.add_subplot(111)
        ax.plot(x_values, y_values)
        ax.grid(True)
        ax.set_ylim(min(y_values) - 5, max(y_values) + 5)
        ax.set_title(TITLES[i])

        ax.yaxis.set_major_formatter(FuncFormatter(custom_formatter))

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

        canvas_widget = FigureCanvasTkAgg(fig, master=frame)
        canvas_widget.get_tk_widget().grid(row=row, column=col, padx=5, pady=5)

    frame.update_idletasks()

    canvas.config(scrollregion=canvas.bbox("all"))
    canvas.bind_all("<MouseWheel>", lambda event: on_mouse_wheel(event, canvas))
    root.mainloop()

def get_existing_data():
    try:
        with open(JSON_PATH, 'r') as file:
            existing_data = json.load(file)
    except FileNotFoundError:
        existing_data = []

    return existing_data

def construct_data_and_show_plots(data_in_order, root):
    for item in data_in_order:
        item["timestamp"] = datetime.fromisoformat(item["timestamp"])
    current_time = datetime.now()
    last_24h = [item for index, item in enumerate(data_in_order) if current_time - item["timestamp"] <= timedelta(days=1) and index % 3 ==0]
    last_7days = [item for index, item in enumerate(data_in_order) if
                  current_time - item["timestamp"] <= timedelta(days=7) and index % 5 == 0]

    data_sets = [get_data_set(last_24h, "temperature"),
                 get_data_set(last_24h, "pressure"),
                 get_data_set(last_24h, "humidity"),
                 get_data_set(last_7days, "temperature"),
                 get_data_set(last_7days, "pressure"),
                 get_data_set(last_7days, "humidity"),
                 get_data_set(last_24h, "pm25"),
                 get_data_set(last_24h, "pm10"),
                 (None, None),
                 get_data_set(last_7days, "pm25"),
                 get_data_set(last_7days, "pm10"),
                 ]

    display_plots_in_window(data_sets, root, most_recent=last_24h[-1])




root = tk.Tk()
root.title("Pogoda w ostatnim czasie")
root.protocol("WM_DELETE_WINDOW", lambda: on_closing())

root.configure(bg="white", width=1920, height=1000)
data = get_existing_data()
construct_data_and_show_plots(data, root)


def on_exit():
    sys.exit()


def my_function():
    data = fetch_data_from_api()
    append_to_json_file(data)
    data_in_order = get_existing_data()
    construct_data_and_show_plots(data_in_order, root)


schedule.every(INTERVAL_SECONDS).seconds.do(my_function)

while True:
    schedule.run_pending()
    time.sleep(1)
