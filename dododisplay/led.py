#!/usr/bin/env python3
import RPi.GPIO as GPIO


class Led:
    _state = 0

    def __init__(self, pin):
        self._PIN = pin
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._PIN, GPIO.OUT)
        GPIO.output(self._PIN, GPIO.LOW)

    def toggle(self):
        if self._state:
            self._off()
            self._state = 0
        else:
            self._on()
            self._state = 1

    def _on(self):
        GPIO.output(self._PIN, GPIO.HIGH)

    def _off(self):
        GPIO.output(self._PIN, GPIO.LOW)

    def __exit__(self):
        GPIO.cleanup()
