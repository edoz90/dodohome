from flask import session, current_app
from requests_oauthlib import OAuth2Session
from google.auth.transport.requests import AuthorizedSession
import google.oauth2.credentials
import simplejson as json
from datetime import datetime

TRAVELS_MODE = {
    "car": "driving",
    "bus": "transit",
    "male": "walking",
    "bicycle": "bicycling",
    "train": "transit",
}
PADDING_MINUTES = 50


def get_directions(fr, to, gmaps):
    if "location_work" in session and "location_home" in session:
        vehicle = session["primary_vehicle"]
        now = datetime.now()
        directions_result = gmaps.directions(
            fr, to, mode=TRAVELS_MODE[vehicle], departure_time=now)
        # Duration in seconds
        duration = directions_result[0]["legs"][0].get("duration").get("value")
        update_calendar(int(duration) / 60 + 20)
        return directions_result
    else:
        return -1


def update_calendar(reminder):
    # PUT https://www.googleapis.com/calendar/v3/users/me/calendarList/calendarId
    headers = {'Content-type': 'application/json'}
    authed_session = get_credentials()
    url = "https://www.googleapis.com/calendar/v3/users/me/calendarList/{}".format(
        session["default_calendar"])
    reminders = [{"method": "popup", "minutes": (PADDING_MINUTES + reminder)}]
    response = authed_session.put(
        url,
        data=json.dumps({
            "defaultReminders": reminders,
        }),
        headers=headers).json()
    print(response)
    return response


def get_work_location(gmaps):
    if "location_work" in session and "location_work_full" in session:
        return session["location_work_full"], session["location_work"]
    cal_info = get_calendar_info("location")
    geocode_result = [-1]
    if not (cal_info is None):
        geocode_result = gmaps.geocode(cal_info)
        if not (geocode_result and "geometry" in geocode_result[0]):
            r = get_latest(10, session["default_calendar"])
            try:
                location_work_full = [
                    e["location"] for e in r if "location" in e
                ][0]
                # Geocoding an address
                geocode_result = gmaps.geocode(location_work_full)
            except IndexError:
                return -1, -1
        else:
            location_work_full = cal_info
    else:
        location_work_full = cal_info
    return location_work_full, geocode_result[0]


def get_calendar_list():
    authed_session = get_credentials()
    response = authed_session.get(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        params={
            "maxResults": 20,
            "showHidden": "true",
        }).json()
    real_cals = []
    if not ("calendars" in session):
        session["calendars"] = ",".join([x["id"] for x in response["items"]])
    for i in response["items"]:
        if not ("group.v.calendar.google.com" in i["id"]):
            real_cals.append(i)
    return real_cals


def get_calendar_info(key=None):
    authed_session = get_credentials()
    response = authed_session.get(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList/{}".
        format(session["default_calendar"])).json()
    if key:
        if key in response:
            return response[key]
        else:
            return None
    return response


def get_latest(n, cal=None):
    now = datetime.utcnow().isoformat() + "Z"
    authed_session = get_credentials()
    url = "https://www.googleapis.com/calendar/v3/calendars/{}/events".format(
        cal if cal else session["default_calendar"])
    response = authed_session.get(
        url,
        params={
            "maxResults": n,
            "timeMin": now,
            "orderBy": "startTime",
            "singleEvents": "true"
        }).json()
    return response["items"]


def get_credentials():
    automatic_refresh()
    token = session["oauth_token"]
    credentials = google.oauth2.credentials.Credentials(
        token["access_token"],
        refresh_token=token["refresh_token"],
        client_id=current_app.config.get("CLIENT_ID"),
        client_secret=current_app.config.get("CLIENT_SECRET"))
    authed_session = AuthorizedSession(credentials)
    return (authed_session)


def get_user():
    if not ("username" in session):
        authed_session = get_credentials()
        response = authed_session.get(
            "https://www.googleapis.com/oauth2/v1/userinfo").json()
        session["username"] = response
    return session["username"]


def manual_refresh():
    extra = {
        "client_id": current_app.config.get("CLIENT_ID"),
        "client_secret": current_app.config.get("CLIENT_SECRET"),
    }
    g = OAuth2Session(
        current_app.config.get("CLIENT_ID"), token=session["oauth_token"])
    # Trigger the update
    g.get("https://www.googleapis.com/oauth2/v1/userinfo")
    token_saver(
        g.refresh_token(current_app.config.get("REFRESH_URL"), **extra))


def automatic_refresh():
    extra = {
        "client_id": current_app.config.get("CLIENT_ID"),
        "client_secret": current_app.config.get("CLIENT_SECRET"),
    }
    old = session["oauth_token"]["expires_at"]
    g = OAuth2Session(
        current_app.config.get("CLIENT_ID"),
        token=session["oauth_token"],
        auto_refresh_kwargs=extra,
        auto_refresh_url=current_app.config.get("REFRESH_URL"),
        token_updater=token_saver)
    # Trigger the update
    g.get("https://www.googleapis.com/oauth2/v1/userinfo")
    if old < session["oauth_token"]["expires_at"]:
        print("Token Updated")


def print_session_decoded(session_cookie):
    import base64
    print(session_cookie)
    if session_cookie[0] == ".":
        import zlib
        print(
            zlib.decompress(
                base64.urlsafe_b64decode(
                    session_cookie.split(".")[1] + "===")))
    else:
        print(base64.urlsafe_b64decode(session_cookie.split(".")[0] + "==="))


def token_saver(token):
    session["oauth_token"] = token
    session["refresh_token"] = token["refresh_token"]
