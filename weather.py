#!/usr/bin/python

import math
import os
import requests
import sys
import thread
import time

from os.path import join, dirname
from dotenv import load_dotenv

from luma.led_matrix.device import max7219
from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.core.legacy import text
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT, SINCLAIR_FONT, LCD_FONT

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
app_key = os.environ.get('APP_KEY')

if app_key is None:
    raise ValueError('APP_KEY in .env file is required')

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=-90, rotate=0)

def get_temp(city):
    global temp
    global weather
    while True:
        print('starting request...')
        try:
            r = requests.get('https://api.openweathermap.org/data/2.5/weather?q={0}&units=metric&APPID={1}'.format(city, app_key))
        except:
            raise ValueError('No data available for ' + city)
        print('...request finished')
        body = r.json()
        if 'message' in body:
            raise ValueError(body['message'])
        temp = str(round(body['main']['temp'], 1))
        weather = body['weather'][0]
        time.sleep(15 * 60)

def temp_width(temp):
    width = 0
    for c in temp:
        if c == '.':
            width += 3
        elif c == '1':
            width += 4
        else:
            width += 6
    return width - 1

def get_circle_points(x_offset = 0, y_offset = 0):
    points = [[1,0],[2,0],[3,1],[3,2],[2,3],[1,3],[0,2],[0,1]]
    def offset(p): return [p[0] + x_offset, p[1] + y_offset]
    return map(offset, points)

def draw_circle(x_offset, draw):
    p = get_circle_points(x_offset, 0)
    for i in range(len(p)):
        draw.point((p[i][0], p[i][1]), fill="white")

'''
def draw_loader(progress, draw):
    for i in range(4):
        y = 3 if progress % 4 == i else 4
        draw.point((i + 14, y), fill="white")
'''

def draw_loader(progress, draw):
    p = get_circle_points(14, 2)
    for i in range(len(p)):
        if i != progress % len(p) and i != (progress - 1) % len(p):
            draw.point((p[i][0], p[i][1]), fill="white")

def display():
    progress = 0
    show_temp = True
    while True:
        if 'temp' in globals() and 'weather' in globals():
            str_width = temp_width(temp) + 1
            circle_width = 4
            total_offset = (32 - (str_width + circle_width)) / 2
            circle_offset = str_width + total_offset
            with canvas(device) as draw:
                if show_temp:
                    text(draw, (total_offset, 0), temp, fill="white", font=proportional(LCD_FONT))
                    draw_circle(circle_offset, draw)
                else:
                    text(draw, (0, 0), weather['description'], fill="white", font=proportional(TINY_FONT))
            time.sleep(3)
            show_temp = not show_temp
        else:
            with canvas(device) as draw:
                draw_loader(progress, draw)
            progress += 1
            time.sleep(0.15)

if __name__ == '__main__':
    try:
        city = sys.argv[1] if len(sys.argv) > 1 else 'Berlin'
        thread.start_new_thread(get_temp, (city,))
        display()
    except KeyboardInterrupt:
        pass