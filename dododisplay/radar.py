#!/usr/bin/env python3
import wiringpi
import time


class Radar:
    _trigger = 15
    _echo = 13
    _SPEED_OF_SOUND = 34029
    _threshold = 20
    _time = 1

    def __init__(self):
        wiringpi.wiringPiSetupPhys()
        wiringpi.pinMode(self._trigger, 1)
        wiringpi.pinMode(self._echo, 0)
        wiringpi.digitalWrite(self._trigger, 0)

    # Send a pulse signal
    def _pulse(self):
        wiringpi.digitalWrite(self._trigger, 1)
        time.sleep(0.00001)
        wiringpi.digitalWrite(self._trigger, 0)
        start = time.time()
        stop = start
        while wiringpi.digitalRead(self._echo) == 0:
            start = time.time()
        while wiringpi.digitalRead(self._echo) == 1:
            stop = time.time()
        return (stop - start) * self._SPEED_OF_SOUND / 2.0

    # Return the mean distance within _time second
    def mean_range(self, precision=2):
        start = time.time()
        data = []
        while time.time() <= start + self._time:
            d = round(self._pulse(), precision)
            data.append(d)
            time.sleep(0.15)
        return sum(data) / len(data) < self._threshold


if __name__ == '__main__':
    r = Radar()
    print(r.mean_range())
