#!/usr/bin/env python3
import session
import directions
import weather
import time
from datetime import timedelta
from dateutil.parser import parse
from pprint import pprint

# Debug print
PPRINT = False
TRAVEL_MODES = {
    "car": "driving",
    "bus": "transit",
    "male": "walking",
    "bicycle": "bicycling",
    "train": "transit"
}


# Clouds check (%)
# Rain check (volume for last 3h in mm), "light/medium rain", "rain"
# Wind check (m/s)
# Snow check (volume for last 3h in mm)
# Temp check (C)
def is_bad_weather(vehicle, work, home, e):
    w = weather.Weather()
    start_time = parse(e.get("start").get("dateTime"))
    end_time = parse(e.get("end").get("dateTime"))
    work_location = {"lat": work.get("lat"), "lng": work.get("lng")}
    home_location = {"lat": home.get("lat"), "lng": home.get("lng")}
    forecasts = []
    is_bad = False
    vehicle = TRAVEL_MODES[vehicle]

    # Get all weather information for both locations and times
    home_start_fc = w.get_forecast(work_location, start_time)
    forecasts.append(home_start_fc)

    work_start_fc = w.get_forecast(home_location, start_time)
    forecasts.append(work_start_fc)

    work_end_fc = w.get_forecast(work_location, end_time)
    forecasts.append(work_end_fc)

    home_end_fc = w.get_forecast(home_location, end_time)
    forecasts.append(home_end_fc)

    if PPRINT:
        pprint(home_start_fc)
        pprint(work_start_fc)
        pprint(work_end_fc)
        pprint(home_end_fc)

    # BAD: medium rain, heavy snow, powerful wind, prohibitive temps
    if vehicle == "walking":
        if all(
                bool(f.get("snow")) and f.get("snow").get("3h") > 3
                for f in forecasts):
            is_bad = True
        if all(f.get("temp").get("temp") < 5 for f in forecasts) or any(
                f.get("temp").get("temp") > 30 for f in forecasts):
            is_bad = True
        if any("rain" in f.get("stat")
               for f in forecasts) and all(not ("light" in f.get("stat"))
                                           for f in forecasts):
            is_bad = True
        if any(
                bool(f.get("rain")) and f.get("rain").get("3h") > 5
                for f in forecasts):
            is_bad = True
        if all(
                f.get("wind").get("speed") > 10 and f.get("clouds") > 80
                for f in forecasts):
            is_bad = True

    # BAD: snow, prohibitive temps, all not light rain, clouds with wind (possibile storm)
    if vehicle == "bicycling":
        if all(
                bool(f.get("snow")) and f.get("snow").get("3h") > 1
                for f in forecasts):
            is_bad = True
        if all(f.get("temp").get("temp") < 0 for f in forecasts) or any(
                f.get("temp").get("temp") > 35 for f in forecasts):
            is_bad = True
        if any("rain" in f.get("stat")
               for f in forecasts) and all(not ("light" in f.get("stat"))
                                           for f in forecasts):
            is_bad = True
        if any(
                bool(f.get("rain")) and f.get("rain").get("3h") > 1
                for f in forecasts):
            is_bad = True
        if all(
                f.get("wind").get("speed") > 5 and f.get("clouds") > 80
                for f in forecasts):
            is_bad = True

    # BAD: reschedule traffic
    if vehicle == "driving":
        if all(
                bool(f.get("snow")) and f.get("snow").get("3h") > 4
                for f in forecasts):
            is_bad = True
        if any("rain" in f.get("stat")
               for f in forecasts) and all(not ("light" in f.get("stat"))
                                           for f in forecasts):
            is_bad = True
        if any(
                bool(f.get("rain")) and f.get("rain").get("3h") > 1
                for f in forecasts):
            is_bad = True

    # BAD: avoid walking from home/work to station/stop
    if vehicle == "transit":
        if any("rain" in f.get("stat")
               for f in forecasts) and all(not ("light" in f.get("stat"))
                                           for f in forecasts):
            is_bad = True
        if any(
                bool(f.get("rain")) and f.get("rain").get("3h") > 3
                for f in forecasts):
            is_bad = True

    return is_bad


def find_optimal(event, primary, secondary, work, home, directions):
    PADDING = timedelta(minutes=65)  # UTC+1 plus 5 minutes of bonus
    start_date = parse(event.get("start").get("dateTime"))
    if is_bad_weather(primary, work, home, event):
        # If bad weather traffic model is pessismistic
        if primary == "driving":
            start_direction = time.time()
            d, url = directions.get_directions(
                primary, start_date - PADDING, traffic_model="pessimistic")
            print("Get directions time:", time.time() - start_direction)
        # If bad weather use less_walking parameter
        if primary == "bus" or primary == "train":
            start_direction = time.time()
            d, url = directions.get_directions(
                primary,
                start_date - PADDING,
                transit_routing_preference="less_walking")
            print("Get directions time:", time.time() - start_direction)
        # If bad weather switch to the second vehicle choice
        if primary == "male" or primary == "bicycle":
            if is_bad_weather(secondary, work, home, event):
                # Evaluate timing for the second choice
                if secondary == "bus" or secondary == "train":
                    start_direction = time.time()
                    d, url = directions.get_directions(
                        secondary,
                        start_date - PADDING,
                        transit_routing_preference="less_walking")
                    print("Get directions time:",
                          time.time() - start_direction)
                else:
                    start_direction = time.time()
                    d, url = directions.get_directions(
                        secondary,
                        start_date - PADDING,
                        traffic_model="pessimistic")
                    print("Get directions time:",
                          time.time() - start_direction)
            else:
                start_direction = time.time()
                d, url = directions.get_directions(secondary,
                                                   start_date - PADDING)
                print("Get directions time:", time.time() - start_direction)
    else:
        # Weather is good!
        start_direction = time.time()
        d, url = directions.get_directions(primary, start_date - PADDING)
        print("Get directions time:", time.time() - start_direction)
    return d, url


if __name__ == "__main__":
    start_main = time.time()
    print("Getting info...")
    session_data = session.Session()
    PADDING_WAKE_UP = 40
    w = weather.Weather()

    # Get events and session info
    start_get_events = time.time()
    events = session_data.get_events(3)
    print("Get Events time:", time.time() - start_get_events)
    work_full, work_name = session_data.get_work_location()
    home_full, home_name = session_data.get_home_location()
    primary_vehicle, secondary_vehicle = session_data.get_vehicles()

    work_location = {
        "lat": work_full.get("geometry").get("location").get("lat"),
        "lng": work_full.get("geometry").get("location").get("lng"),
        "name": work_name
    }
    home_location = {
        "lat": home_full.get("geometry").get("location").get("lat"),
        "lng": home_full.get("geometry").get("location").get("lng"),
        "name": home_name
    }
    # init direction with default locations
    directions = directions.Directions(work_location, home_location)

    for e in events:
        description = ""
        start_date = e.get("start").get("dateTime")
        start_find_optimal = time.time()
        # Use weather ad GMaps API to find the best solution
        d, url = find_optimal(e, primary_vehicle, secondary_vehicle,
                              work_location, home_location, directions)
        print("Find optimal time: ", time.time() - start_find_optimal)

        # PADDING: empiric time for wake up routine
        reminder = d.get("duration") + PADDING_WAKE_UP

        start_weather = time.time()
        ww = w.get_forecast(work_location, parse(start_date))
        print("Get weather time:", time.time() - start_weather)
        wh = w.get_forecast(
            home_location, parse(start_date) - timedelta(minutes=reminder))

        # Create the description string
        for i in d:
            description += "<b>{}</b>: {}\n".format(
                i.replace("_", " ").title(), d.get(i))
        description += "<b>Weather at work</b>: {}, {} °C\n".format(
            ww.get("stat"),
            ww.get("temp").get("temp"))
        description += "<b>Weather at home</b>: {}, {} °C\n".format(
            wh.get("stat"),
            wh.get("temp").get("temp"))
        description += "<b>URL</b>: {}".format(url)

        start_event_update = time.time()
        session_data.update_event(e, reminder, description=description)
        print("Event update time:", time.time() - start_event_update)

    print("Main time: ", time.time() - start_main)
