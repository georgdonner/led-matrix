#!/usr/bin/python

import os
import requests
import thread
import time
import sys

from os.path import join, dirname
from dotenv import load_dotenv

from luma.led_matrix.device import max7219
from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.core.legacy import text
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT, SINCLAIR_FONT, LCD_FONT

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
app_key = os.environ.get('APP_KEY_FOOTBALL')

if app_key is None:
    raise ValueError('APP_KEY_FOOTBALL in .env file is required')

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=-90, rotate=0)
team_codes = {}

def get_standings(league, status):
    global current_standings
    headers = {'X-Auth-Token': app_key}
    while True:
        try:
            r = requests.get('http://api.football-data.org/v1/fixtures?league={0}'.format(league), headers=headers)
        except:
            raise ValueError('No data available for ' + league)
        body = r.json()
        fixtures = [f for f in body['fixtures'] if f['status'] == status.upper()]
        standings = []
        for fixture in fixtures:
            home_team = fixture['homeTeamName']
            away_team = fixture['awayTeamName']
            home_goals = fixture['result']['goalsHomeTeam']
            away_goals = fixture['result']['goalsHomeTeam']
            if home_goals != None:
                home_score = str(home_goals)
                away_score = str(away_goals)
            else:
                # no result/standings yet
                home_score = '-'
                away_score = ''
            if home_team not in team_codes:
                r_home = requests.get(fixture['_links']['homeTeam']['href'], headers=headers)
                home_code = r_home.json()['code'] or r_home.json()['shortName'].upper()[:3] or home_team.upper()[:3]
                team_codes[home_team] = home_code
            if away_team not in team_codes:
                r_away = requests.get(fixture['_links']['awayTeam']['href'], headers=headers)
                away_code = r_away.json()['code'] or r_away.json()['shortName'].upper()[:3] or away_team.upper()[:3]
                team_codes[away_team] = away_code
            formatted = '{0}{2}{3}{1}'.format(team_codes[home_team], team_codes[away_team], home_score, away_score)
            standings.append(formatted)
        current_standings = standings
        time.sleep(30)

def get_circle_points(x_offset = 0, y_offset = 0):
    points = [[1,0],[2,0],[3,1],[3,2],[2,3],[1,3],[0,2],[0,1]]
    def offset(p): return [p[0] + x_offset, p[1] + y_offset]
    return map(offset, points)

def draw_loader(progress, draw):
    p = get_circle_points(14, 2)
    for i in range(len(p)):
        if i != progress % len(p) and i != (progress - 1) % len(p):
            draw.point((p[i][0], p[i][1]), fill="white")

def display():
    progress = 0
    match = 0
    while True:
        if 'current_standings' in globals():
            with canvas(device) as draw:
                if len(current_standings) == 0:
                    text(draw, (0, 0), 'No match', fill="white", font=proportional(TINY_FONT))    
                else:
                    text(draw, (0, 0), current_standings[match], fill="white", font=proportional(TINY_FONT))
                    match = match + 1 if (match + 1) < len(current_standings) else 0
            time.sleep(5)
        else:
            with canvas(device) as draw:
                draw_loader(progress, draw)
            progress += 1
            time.sleep(0.15)

if __name__ == '__main__':
    try:
        league = sys.argv[1] if len(sys.argv) > 1 else 'BL1'
        status = sys.argv[2] if len(sys.argv) > 2 else 'in_play'
        thread.start_new_thread(get_standings, (league, status))
        display()
    except KeyboardInterrupt:
        pass