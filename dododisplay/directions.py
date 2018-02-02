#!/usr/bin/env python3
import googlemaps
import math
import simplejson as json
import requests
from datetime import datetime
from pprint import pprint

TRAVEL_MODES = {
    "car": "driving",
    "bus": "transit",
    "male": "walking",
    "bicycle": "bicycling",
    "train": "transit"
}


class Directions:
    __GOOGLEMAPS_KEY = ""
    __GOOGLESHORT_KEY = ""
    __PADDING_TIME = 40
    __URL = "https://www.google.it/maps/dir/{}/{}/data={}"
    __PPRINT = False

    def __init__(self, work, home):
        self._gmaps = googlemaps.Client(key=self.__GOOGLEMAPS_KEY)
        self._shorturl = "https://www.googleapis.com/urlshortener/v1/url?key={}".format(
            self.__GOOGLESHORT_KEY)
        try:
            self.work_name = work.get("name")
            self.home_name = home.get("name")
            self.work_location = {
                "lat": work.get("lat"),
                "lng": work.get("lng")
            }
            self.home_location = {
                "lat": home.get("lat"),
                "lng": home.get("lng")
            }
        except:
            print("Format non correct for locations")

    # USE Google shortner
    def _url_shorten(self, url):
        data = {'longUrl': url}
        headers = {'Content-type': 'application/json'}
        response = requests.post(
            self._shorturl, data=json.dumps(data), headers=headers).json()
        return response.get("id")

    # Generate URL with GMaps directions
    def _generate_url(self, vehicle, transit_mode=None):
        """ GMaps use this econdings:
        !4m5 - map/image contents block, 5 elements
        - !4m4 - directions block, 4 elements
        - - !2m2 - route options, 2 elements
        - - - !4e2 - preferred transit route, 2 = fewer transfers
        - - -        (1 = best time; 3 = less walking)
        - - - !5e0 - preferred transit type, 0 = bus
        - - -        (1=subway, 2=train, 3=tram/lt rail)
        - - !3e3 - transportation mode, 3 = public transit"""

        transportation = {
            "driving": 0,
            "bicycling": 1,
            "walking": 2,
            "transit": 3,
        }
        if transit_mode:
            t_type = {
                "bus": 0,
                "train": 2,
            }
            data = "!4m4!4m3!2m1!5e{}!3e{}".format(
                t_type.get(transit_mode), transportation.get("transit"))
        else:
            data = "!4m2!4m1!3e{}".format(transportation.get(vehicle))
        u = self.__URL.format(self.home_name, self.work_name, data)
        return self._url_shorten(u)

    # Wrapper for _get_directions
    def get_directions(self,
                       vehicle,
                       arrival_time,
                       transit_routing_preference=None,
                       traffic_model=None):
        mode = TRAVEL_MODES[vehicle]
        transit_mode = None
        infos = None
        # Bus and train are "transit" vehicle
        if mode is "transit":
            transit_mode = vehicle

        # Get directions information and dispatch to the parser
        directions, url = self._get_directions(
            mode,
            arrival_time,
            transit_mode=transit_mode,
            transit_routing_preference=transit_routing_preference)
        if mode == "walking":
            infos = self.get_walk(directions)
        elif mode == "bicycling":
            # Bicycling is not always available
            fallback = False
            if not directions:
                directions = self.get_walk(directions)
                fallback = True
            infos = self.get_bicycle(directions, fallback)
        elif mode == "driving":
            infos = self.get_car(directions)
        elif mode == "transit" and transit_mode == "bus":
            infos = self.get_bus(directions)
        elif mode == "transit" and transit_mode == "train":
            infos = self.get_train(directions)
        return infos, url

    # Call to GMaps API
    # Default parameter:
    # "best_guess" for driving
    # transit_routing_preference is use only for transit and set to "less_walking"
    def _get_directions(self,
                        vehicle,
                        arrival_time,
                        transit_mode=None,
                        transit_routing_preference=None,
                        traffic_model="best_guess"):
        region = "it"
        if transit_mode:
            url = self._generate_url(vehicle, transit_mode)
            directions = self._gmaps.directions(
                self.home_location,
                self.work_location,
                alternatives=False,
                region=region,
                mode=vehicle,
                transit_routing_preference=transit_routing_preference,
                transit_mode=transit_mode,
                arrival_time=arrival_time)
        else:
            url = self._generate_url(vehicle, transit_mode)
            directions = self._gmaps.directions(
                self.home_location,
                self.work_location,
                alternatives=True,
                traffic_model=traffic_model,
                region=region,
                mode=vehicle,
                departure_time=arrival_time)
        try:
            # Return the best solution found
            return min(
                directions,
                key=lambda x: x.get("legs")[0].get("duration").get("value")
            ), url
        except (ValueError, TypeError):
            print("No direction found for:", vehicle.upper())
            return False

    # Return parsed informations from directions
    def get_bus(self, directions):
        print("|" + "-" * 80)
        print("Gettings directions for BUS transit")
        if self.__PPRINT:
            pprint(directions)
        legs = directions.get("legs")[0]
        departure_time = datetime.fromtimestamp(
            legs.get("departure_time").get("value")).strftime('%d %b - %H:%M')
        arrival_time = legs.get("arrival_time").get("text")
        duration = math.ceil(legs.get("duration").get("value") / 60)
        steps = directions.get("legs")[0].get("steps")
        departure_name = None
        line = None
        for s in steps:
            try:
                transit_details = s.get("transit_details")
                vehicle = transit_details.get("line").get("vehicle").get(
                    "name")
                if "bus" in json.dumps(transit_details.get("line")).lower():
                    departure_name = transit_details.get("departure_stop").get(
                        "name")
                    line = transit_details.get("line").get("short_name")
                    break
                if "train" in json.dumps(transit_details.get("line")).lower(
                ) or "heavy_rail" in json.dumps(transit_details).lower():
                    departure_name = transit_details.get("departure_stop").get(
                        "name")
                    line = transit_details.get("headsign")
                    vehicle += " (BUS not available)"
                    break
            except:
                pass
        infos = {
            "departure_time": departure_time,
            "departure_name": departure_name,
            "line": line,
            "arrival_time": arrival_time,
            "duration": duration,
            "vehicle": vehicle,
        }
        print("|" + "-" * 80)
        return infos

    # Return parsed informations from directions
    def get_train(self, directions):
        print("|" + "-" * 80)
        print("Gettings directions for TRAIN transit")
        if self.__PPRINT:
            pprint(directions)
        legs = directions.get("legs")[0]
        departure_time = datetime.fromtimestamp(
            legs.get("departure_time").get("value")).strftime('%d %b - %H:%M')
        arrival_time = legs.get("arrival_time").get("text")
        duration = math.ceil(legs.get("duration").get("value") / 60)
        steps = directions.get("legs")[0].get("steps")
        departure_name = None
        line = None
        for s in steps:
            try:
                transit_details = s.get("transit_details")
                vehicle = transit_details.get("line").get("vehicle").get(
                    "name")
                if "train" in json.dumps(transit_details.get("line")).lower(
                ) or "heavy_rail" in json.dumps(transit_details).lower():
                    departure_name = transit_details.get("departure_stop").get(
                        "name")
                    line = transit_details.get("headsign")
                    break
            except:
                pass
        if not line and departure_time:
            vehicle += " (BUS not available)"
            print("NOT TRAIN")
        infos = {
            "departure_time": departure_time,
            "departure_name": departure_name,
            "line": line,
            "arrival_time": arrival_time,
            "duration": duration,
            "vehicle": vehicle,
        }
        print("|" + "-" * 80)
        return infos

    # Return parsed informations from directions
    def get_car(self, directions):
        print("|" + "-" * 80)
        print("Gettings directions for CAR")
        if self.__PPRINT:
            pprint(directions)
        legs = directions.get("legs")[0]
        duration = math.ceil(legs.get("duration").get("value") / 60)
        distance = math.ceil(legs.get("distance").get("value") / 1000)
        infos = {
            "duration": duration,
            "distance": distance,
            "vehicle": "car",
            "via": directions.get("summary"),
        }
        print("|" + "-" * 80)
        return infos

    # Return parsed informations from directions
    def get_walk(self, directions):
        print("|" + "-" * 80)
        print("Gettings directions for WALK")
        if self.__PPRINT:
            pprint(directions)
        legs = directions.get("legs")[0]
        duration = math.ceil(legs.get("duration").get("value") / 60)
        distance = math.ceil(legs.get("distance").get("value") / 1000)
        infos = {
            "duration": duration,
            "distance": distance,
            "vehicle": "walking",
            "via": directions.get("summary"),
        }
        print("|" + "-" * 80)
        return infos

    # Return parsed informations from directions
    def get_bicycle(self, directions, fallback=True):
        print("|" + "-" * 80)
        print("Gettings directions for BICYCLE")
        if self.__PPRINT:
            pprint(directions)
        legs = directions.get("legs")[0]
        duration = math.ceil(legs.get("duration").get("value") / 60)

        # No walking route founds, use walking info but with less time duration
        if fallback:
            duration = int(duration / 1.5)

        distance = math.ceil(legs.get("distance").get("value") / 1000)
        infos = {
            "duration": duration,
            "distance": distance,
            "vehicle": "bicycle",
            "via": directions.get("summary"),
        }
        print("|" + "-" * 80)
        return infos
