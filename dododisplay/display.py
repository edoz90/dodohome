#!/usr/bin/env python3
import os
import time
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from luma.core.virtual import viewport
from PIL import ImageFont


class OLed():
    def __init__(self):
        # Set I2C port
        self.__serial = i2c(port=1, address=0x3C)
        self._device = ssd1306(self.__serial)

    # Using Pillow create the default font
    def _make_font(self, name, size):
        font_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), 'fonts', name))
        return ImageFont.truetype(font_path, size)

    # display off
    def hide(self):
        self._device.hide()

    # Print a left or right side arrow
    def draw_arrow(self, side=None, clear_time=0.025):
        self._device = ssd1306(self.__serial)
        self._device.show()
        font_awesome = self._make_font("fontawesome-regular.ttf",
                                       self._device.height - 11)
        right_code = "\uf061"
        left_code = "\uf060"

        if side == "left":
            code = left_code
        else:
            code = right_code
        with canvas(self._device) as d:
            d.rectangle(
                (0, 0, self._device.width, self._device.height), fill="white")
            w, h = d.textsize(text=code, font=font_awesome)
            left = (self._device.width - w) / 2
            top = (self._device.height - h) / 2
            d.text((left, top), text=code, font=font_awesome, fill="black")
        time.sleep(clear_time)
        self._device.hide()

    def _set_canvas(self, line1, line2, line3):
        font = self._make_font("agave-r.ttf", 24)
        full_text = "{}\n{}\n{}".format(line1, line2, line3).replace("\n", " ")

        with canvas(self._device) as draw:
            w, h = draw.textsize(full_text, font)

        virtual = viewport(
            self._device,
            width=w + self._device.width,
            height=self._device.height)
        with canvas(virtual) as draw:
            draw.text((0, -5), line1, font=font, fill="white")
            draw.text((0, 19), line2, font=font, fill="white")
            draw.text((0, 41), line3, font=font, fill="white")

        return w, virtual

    def set_message(self, line1, line2, line3):
        w, virtual = self._set_canvas(line1, line2, line3)
        self._device.show()
        return virtual, w - 110

    # Show a message in 3 text line with horizontal scrolling
    def scroll_message(self, status, speed=3, clear_time=0.025):
        self._device.show()
        font = self._make_font("agave-r.ttf", 24)

        w, virtual = self.set_canvas(status["date"], status["text"],
                                     status["weather"], font)

        for i in range(0, w - 100, speed):
            virtual.set_position((i, 0))
            if i == 0:
                time.sleep(2)
        time.sleep(clear_time)

    # Show a text
    def simple_message(self, text, clear_time=1):
        self._device.show()
        font = self._make_font("agave-r.ttf", 18)

        # First measure the text size
        with canvas(self._device) as draw:
            draw.text((0, 0), text.replace(" ", "\n"), font=font, fill="white")
        time.sleep(clear_time)


if __name__ == "__main__":
    d = OLed()
    s = {"date": "asdsa", "text": "No scheduled events", "weather": ""}
    v, w = d.set_message(s["date"], s["text"], s["weather"])
    for i in range(0, w, 10):
        v.set_position((i, 0))
