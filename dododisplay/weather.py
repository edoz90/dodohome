import pyowm


class Weather:
    __OWM_KEY = ""

    def __init__(self):
        # Init API library
        self._owm = pyowm.OWM(self.__OWM_KEY)

    # Get actual weather for a location
    def get_weather(self, loc):
        obs = self._owm.weather_at_coords(loc["lat"], loc["lng"])
        w = obs.get_weather()
        weather = {
            "clouds": w.get_clouds(),
            "rain": w.get_rain(),
            "snow": w.get_snow(),
            "wind": w.get_wind(),
            "temp": w.get_temperature(unit='celsius'),
            "stat": w.get_detailed_status()
        }
        return weather

    # Get forecast for a location in from a specific time range
    def get_forecast(self, loc, time):
        try:
            fc = self._owm.three_hours_forecast_at_coords(
                loc["lat"], loc["lng"])
            w = fc.get_weather_at(time)
            weather = {
                "clouds": w.get_clouds(),
                "rain": w.get_rain(),
                "snow": w.get_snow(),
                "wind": w.get_wind(),
                "temp": w.get_temperature(unit='celsius'),
                "stat": w.get_detailed_status()
            }
        except pyowm.exceptions.not_found_error.NotFoundError:
            # If time range is in the presente the library will return an error
            # if is present use the get_weather function
            print("Forecast not found for {} at {}".format(loc, time))
            weather = self.get_weather(loc)
        finally:
            return weather
