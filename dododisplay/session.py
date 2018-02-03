#!/usr/bin/env python3
import google.oauth2.credentials
import redis
import simplejson as json
from google.auth.transport.requests import AuthorizedSession
from datetime import datetime, timezone
from dateutil.parser import parse
from pprint import pprint
from requests_oauthlib import OAuth2Session


# Connect to redis DB using the localhost socket on default port
class Session():
    _redis_conn = redis.Redis(unix_socket_path="/run/redis/redis.sock")
    __REFRESH_URL = "https://www.googleapis.com/oauth2/v4/token"
    __CLIENT_ID = ""
    __CLIENT_SECRET = ""
    __PPRINT = True
    _url_calendars = "https://www.googleapis.com/calendar/v3/calendars/"
    _event_count = -1
    _events = None

    def __init__(self):
        try:
            # Retrieve the OAuth token
            self._session_key = [
                key.decode("utf-8") for key in self._redis_conn.scan_iter()
                if "oauth_token" in self._redis_conn.get(key).decode("utf-8")
            ][0]
            self._session_data = json.loads(
                self._redis_conn.get(self._session_key))
            self._calendar = self._session_data["default_calendar"]
            self.get_events()
        except:
            print("Session not found!")
            raise IndexError

    def _update_session(self):
        self._redis_conn.set(self._session_key, json.dumps(self._session_data))

    # If the token is updated sync the DB
    def _token_saver(self, token):
        self._session_data["oauth_token"] = token
        self._update_session()

    def _manual_refresh(self):
        extra = {
            "client_id": self.__CLIENT_ID,
            "client_secret": self.__CLIENT_SECRET,
        }
        g = OAuth2Session(
            self.__CLIENT_ID, token=self._session_data["oauth_token"])
        # Trigger update
        g.get("https://www.googleapis.com/oauth2/v1/userinfo")
        self._token_saver(g.refresh_token(self.__REFRESH_URL, **extra))

    def _automatic_refresh(self):
        extra = {
            "client_id": self.__CLIENT_ID,
            "client_secret": self.__CLIENT_SECRET,
        }
        old = self._session_data["oauth_token"]["expires_at"]
        g = OAuth2Session(
            self.__CLIENT_ID,
            token=self._session_data["oauth_token"],
            auto_refresh_kwargs=extra,
            auto_refresh_url=self.__REFRESH_URL,
            token_updater=self._token_saver)
        g.get("https://www.googleapis.com/oauth2/v1/userinfo")
        if old < self._session_data["oauth_token"]["expires_at"]:
            print("Token Updated")

    # Send the OAuth token to get the credential token
    def _get_credentials(self):
        self._automatic_refresh()
        token = self._session_data["oauth_token"]
        credentials = google.oauth2.credentials.Credentials(
            token["access_token"],
            refresh_token=token["refresh_token"],
            client_id=self.__CLIENT_ID,
            client_secret=self.__CLIENT_SECRET)
        return AuthorizedSession(credentials)

    def get_calendar_id(self):
        return self._calendar

    def get_work_location(self):
        return self._session_data["location_work"], self._session_data[
            "location_work_full"]

    def get_home_location(self):
        return self._session_data["location_home"], self._session_data[
            "location_home_full"]

    def get_vehicles(self):
        return self._session_data["primary_vehicle"], self._session_data[
            "secondary_vehicle"]

    def get_events(self, number_evts=15):
        now = datetime.utcnow().isoformat() + "Z"
        authed_session = self._get_credentials()
        url = self._url_calendars + "{}/events".format(self._calendar)
        response = authed_session.get(
            url,
            params={
                "maxResults": number_evts,
                "timeMin": now,
                "orderBy": "startTime",
                "singleEvents": "true"
            }).json()

        # Query could return the current/in progress event, not useful
        start_date = parse(response["items"][0].get("start").get("dateTime"))
        # needs to make datetime offset-aware: set timezone
        if start_date < datetime.now(timezone.utc):
            response["items"].pop(0)

        self._events = response["items"]
        return response["items"]

    # Update the reminder and description for a event
    def update_event(self, event, time, description=None):
        # PUT https://www.googleapis.com/calendar/v3/calendars/calendarId/events/eventId
        headers = {'Content-type': 'application/json'}
        authed_session = self._get_credentials()
        url = self._url_calendars + "{}/events/{}".format(
            self._calendar, event.get("id"))
        reminders = {
            "useDefault": False,
            "overrides": [{
                "method": "popup",
                "minutes": time
            }]
        }
        response = authed_session.put(
            url,
            data=json.dumps({
                "start": event.get("start"),
                "end": event.get("end"),
                "colorId": event.get("colorId"),
                "summary": event.get("summary"),
                "reminders": reminders,
                "description": description
            }),
            headers=headers).json()
        if self.__PPRINT:
            pprint(response)
        return response

    def get_next_event(self):
        if self._events is None:
            self.get_events()
        self._event_count += 1
        try:
            return self._events[self._event_count]
        except:
            return False

    def get_prev_event(self):
        if self._events is None:
            self.get_events()
        self._event_count = 0 if self._event_count <= 0 else self._event_count - 1
        try:
            return self._events[self._event_count]
        except:
            return False
