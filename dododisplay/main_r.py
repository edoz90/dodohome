import button
import display
import dill as pickle
import led
import multiprocessing as mp
import radar
import RPi.GPIO as GPIO
import session
import subprocess
import time
import weather
from dateutil.parser import parse
from pprint import pprint


def get_event_info(e, home):
    dateT = parse(e.get("start").get("dateTime"))
    date = dateT.strftime("%d %b - %H:%M")
    w = weather.Weather()
    reminder = e.get("reminders").get("overrides")[0].get("minutes")
    wt = w.get_forecast(home, dateT)
    st = {
        "line1": str(date) + " - rem: {}".format(reminder),
        "line2": str(e.get("summary")),
        "line3": "{} - {} °C".format(
            wt.get("stat"),
            wt.get("temp").get("temp")),
    }
    return st


def button_daemon(mng, event, lock, actions):
    def b_call(b):
        event.wait()
        d = mng[0]
        if b is "left":
            d["sleep"] = 60
            with lock:
                if d["events_count"] > 0:
                    d["events_count"] -= 1
                    actions.append("previous")
                e = d["events"][d["events_count"]]
                actions.append(get_event_info(e, mng[0]["home"]))
                mng[0] = d
        else:
            d["sleep"] = 60
            with lock:
                if d["events_count"] < 15 and d["events_count"] < len(
                        d["events"]) - 1:
                    d["events_count"] += 1
                    actions.append("next")

                e = d["events"][d["events_count"]]
                actions.append(get_event_info(e, mng[0]["home"]))
                mng[0] = d

    button.Button(23, "left", b_call)
    button.Button(24, "right", b_call)

    b_call("left")
    while True:
        pass


def radar_daemon(mng, event, lock):
    cmd = "ifconfig tplink | grep 'inet ' | awk '{print $2}'"
    ip = subprocess.check_output(cmd, shell=True).decode("utf-8")
    r = mng[0]["radar"]
    mng[0]["display"].simple_message(ip + "\nDodoHome")
    while True:
        if r.mean_range():
            print("ACTIVE")
            event.set()
            mng[0]["led"]._on()
            d = mng[0]
            with lock:
                d["sleep"] = 60
                mng[0] = d
        else:
            time.sleep(0.8)
            if (mng[0]["sleep"] <= 0):
                print("HIDLE")
                event.clear()
                mng[0]["led"]._off()
                mng[0]["display"].simple_message(ip + "\nDodoHome")
                with lock:
                    d = mng[0]
                    d["events_count"] = 0
                    mng[0] = d
            else:
                with lock:
                    d = mng[0]
                    d["sleep"] -= 1
                    mng[0] = d


def display_daemon(mng, event, lock, actions):
    ACTIONS = {
        "previous":
        pickle.dumps(
            lambda t=0: mng[0]["display"].draw_arrow("left", clear_time=t)),
        "next":
        pickle.dumps(
            lambda t=0: mng[0]["display"].draw_arrow("right", clear_time=t)),
        "display":
        pickle.dumps(lambda d, s, w: mng[0]["display"].set_message(d, s, w))
    }
    old_v = None
    old_w = 0
    while True:
        event.wait()
        if len(actions) > 0:
            v = None
            w = 0
            f = None
            with lock:
                print(actions)
                a = actions.pop(0)
                # If dict found, print it, else run proper function
                if isinstance(a, dict):
                    v, w = pickle.loads(ACTIONS["display"])(a.get("line1"),
                                                            a.get("line2"),
                                                            a.get("line3"))
                else:
                    f = pickle.loads(ACTIONS[a])
                    old_w = 0
            if not (v is None) and w > 0:
                i = 0
                old_v = v
                old_w = w
                while len(actions) <= 0 and i < w:
                    if i >= 0 and i <= 6:
                        time.sleep(0.4)
                    v.set_position((i, 0))
                    i += 7
            elif not (f is None) and len(actions) <= 1:
                f(0.5)
        elif old_w > 0 and not (old_v is None):
            i = 0
            pprint(mng[0]["events"])
            while event.is_set() and i < old_w:
                if i >= 0 and i <= 5:
                    time.sleep(0.4)
                old_v.set_position((i, 0))
                i += 5


def refresh_daemon(mng, lock):
    s = session.Session()
    while True:
        time.sleep(10000)
        events = s.get_events()
        with lock:
            print("Events updated")
            d = mng[0]
            d["events"] = events
            mng[0] = d


if __name__ == "__main__":
    try:
        s = session.Session()
        home_f, _ = s.get_home_location()
        home = {
            "lat": home_f.get("geometry").get("location").get("lat"),
            "lng": home_f.get("geometry").get("location").get("lng"),
        }
        mng = mp.Manager().list()
        mng.append({})
        arg = mng[0]
        arg["led"] = led.Led(25)
        arg["radar"] = radar.Radar()
        arg["display"] = display.OLed()
        arg["events"] = s.get_events()
        arg["home"] = home
        arg["events_count"] = 0
        arg["sleep"] = 30
        mng[0] = arg
    except Exception as e:
        cmd = "ifconfig tplink | grep 'inet ' | awk '{print $2}'"
        ip = subprocess.check_output(cmd, shell=True).decode("utf-8")
        display.OLed().simple_message(ip + "\nDodoHome")
        print(e)
        import sys
        sys.exit(-1)

    event = mp.Event()
    lock = mp.Lock()
    actions = mp.Manager().list()
    tasks = []
    tasks.append(
        mp.Process(
            target=display_daemon,
            daemon=False,
            args=(mng, event, lock, actions)))
    tasks.append(
        mp.Process(
            target=button_daemon,
            daemon=False,
            args=(mng, event, lock, actions)))
    tasks.append(
        mp.Process(target=radar_daemon, daemon=False, args=(mng, event, lock)))
    tasks.append(
        mp.Process(target=refresh_daemon, daemon=False, args=(mng, lock)))
    try:
        list(map(lambda x: x.start(), tasks))
        list(map(lambda x: x.join(), tasks))
    except:
        pass
    finally:
        list(map(lambda x: x.terminate(), tasks))
        GPIO.cleanup()
