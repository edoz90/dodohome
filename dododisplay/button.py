#!/usr/bin/env python3
import asyncio
import RPi.GPIO as GPIO


class Button:
    def __init__(self, pin, name, callback):
        self._pin = pin
        self.name = name
        self._callback = callback
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # Bind callback function to RISING event
        GPIO.add_event_detect(
            self._pin,
            GPIO.RISING,
            callback=lambda x: self._callback(self.name),
            bouncetime=300)

    def __exit__(self):
        GPIO.cleanup()


# This code is ignored when imported
def button_f(s):
    print(s)


def button_sensor(f, s):
    loop.call_soon_threadsafe(f, s)


if __name__ == '__main__':
    b_left = Button(23, "left", lambda x: button_sensor(button_f, "left"))
    b_right = Button(24, "right", lambda x: button_sensor(button_f, "right"))
    try:
        # run the event loop
        loop = asyncio.get_event_loop()
        loop.run_forever()
        loop.close()
    except KeyboardInterrupt:
        GPIO.cleanup()
