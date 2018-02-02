#!/usr/bin/env python3
import button
import display
import multiprocessing
import RPi.GPIO as GPIO
import led
import radar
import session
import subprocess
import time
import dill as pickle
import weather
from dateutil.parser import parse
from datetime import datetime


def calendar_event(is_prev=True):
    if is_prev:
        e = calendar_s.get_prev_event()
    else:
        e = calendar_s.get_next_event()
    # Not an event (end/void calendar)
    if not e:
        return False
    dateT = parse(e.get("start").get("dateTime"))
    w = weather.Weather()
    date = dateT.strftime("%d %b %Y - %H:%M")
    summary = e["summary"]
    reminder = e.get("reminders").get("overrides")[0].get("minutes")
    date += " - reminder: {} min".format(reminder)
    wt = w.get_forecast(home_location, dateT)
    st = {
        "date": str(date),
        "text": str(summary),
        "weather": "{} - {} °C".format(
            wt.get("stat"),
            wt.get("temp").get("temp"))
    }
    return st


def button_daemon(actions, lock, event):
    def button_callback(button):
        event.wait()
        # Push actions like into a stack
        print(button)
        if button is "left":
            with lock:
                text = calendar_event(is_prev=True)
                if not (text is False):
                    actions.append("previous")
                    actions.append(text)
                    actions.append("display")
        else:
            with lock:
                text = calendar_event(is_prev=False)
                if not (text is False):
                    actions.append("next")
                    actions.append(text)
                    actions.append("display")

    button.Button(23, "left", button_callback)
    button.Button(24, "right", button_callback)
    with lock:
        text = calendar_event(is_prev=True)
        if not (text is False):
            actions.append(text)
        else:
            text = {
                "date": "{:%b %d %Y - %H:%M}".format(datetime.today()),
                "text": "No scheduled events",
                "weather": ""
            }
            actions.append(text)
        actions.append("display")
    while True:
        pass


def radar_daemon(event):
    global oled
    global lfeedback
    cmd = "ifconfig tplink | grep 'inet ' | awk '{print $2}'"
    ip = subprocess.check_output(cmd, shell=True).decode("utf-8")
    r = radar.Radar()
    oled.simple_message(ip)
    while True:
        if r.mean_range():
            print("ACTIVE")
            lfeedback._on()
            event.set()
            time.sleep(300)
        else:
            print("HIDLE")
            event.clear()
            lfeedback._off()
            oled.hide()


def display_daemon(actions, lock, event):
    global oled
    ACTIONS = {
        "previous":
        pickle.dumps(lambda t: oled.draw_arrow("left", clear_time=t)),
        "next":
        pickle.dumps(lambda t: oled.draw_arrow("right", clear_time=t)),
        "display":
        pickle.dumps(
            lambda t, c, s: oled.scroll_message(t, speed=s, clear_time=c))
    }
    old_f = None
    while True:
        event.wait()
        if len(actions) > 0:
            # Pop actions from the stack
            lock.acquire()
            try:
                a = actions.pop(0)
                if isinstance(a, dict):
                    f = pickle.loads(ACTIONS[actions.pop(0)])
                else:
                    f = None
            finally:
                lock.release()
            if not (f is None):
                display_cal = lambda x: f(a, 0, x)
                old_f = display_cal
                display_cal(7)
            else:
                pickle.loads(ACTIONS[a])(1)
        else:
            old_f(10)


def refresh_daemon():
    while True:
        calendar_s.get_events()
        time.sleep(6)


if __name__ == "__main__":
    print("Starting...")
    try:
        calendar_s = session.Session()
        home_full, home_name = calendar_s.get_home_location()
        home_location = {
            "lat": home_full.get("geometry").get("location").get("lat"),
            "lng": home_full.get("geometry").get("location").get("lng"),
        }
        oled = display.OLed()
        lfeedback = led.Led(25)
        lfeedback.__exit__()
    except Exception as e:
        print(e)
        import sys
        sys.exit(-1)
    GPIO.setwarnings(False)
    mgr = multiprocessing.Manager()
    lock = multiprocessing.Lock()
    actions = mgr.list()
    event = multiprocessing.Event()

    task = []
    task.append(
        multiprocessing.Process(
            target=button_daemon, daemon=True, args=(actions, lock, event)))
    task.append(
        multiprocessing.Process(
            target=radar_daemon, daemon=True, args=(event, )))
    task.append(
        multiprocessing.Process(
            target=display_daemon, daemon=True, args=(actions, lock, event)))
    task.append(multiprocessing.Process(target=refresh_daemon, daemon=True))
    try:
        list(map(lambda x: x.start(), task))
        list(map(lambda x: x.join(), task))
    except KeyboardInterrupt:
        pass
    finally:
        list(map(lambda x: x.terminate(), task))
        GPIO.cleanup()
