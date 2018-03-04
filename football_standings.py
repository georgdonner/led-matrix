#!/usr/bin/python

import argparse
import json
import os
import re
import requests
import thread
import time
import sys

from difflib import SequenceMatcher
from os.path import join, dirname
from dotenv import load_dotenv

from bs4 import BeautifulSoup

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
headers = {'X-Auth-Token': app_key}

def str_to_ascii(string):
    return re.sub(r'\W', '', string.encode('ascii', errors='ignore').decode())

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio() if a and b else 0

def get_teams(team_id):
    url = 'http://api.football-data.org/v1/competitions/{0}/teams'.format(team_id)
    res = requests.get(url, headers=headers)
    return res.json()['teams']

def get_fixtures(league_code, status):
    time_frame = 'p4' if status == 'finished' else 'n7'
    url = 'http://api.football-data.org/v1/fixtures?league={0}&timeFrame={1}'.format(league_code, time_frame)
    res = requests.get(url, headers=headers)
    fixtures = res.json()['fixtures']
    return list(filter(lambda f: f['status'] == status.upper(), fixtures))

def get_team_code(team_name, teams):
    for team in teams:
        if similar(team_name, team['name']) > 0.6 or similar(team_name, team['shortName']) > 0.6:
            name = team['code'] or team['shortName'] or team['name']
            return str_to_ascii(name).upper()[:3]
    return str_to_ascii(team_name).upper()[:3]

def get_live_standings(league, teams):
    url = 'http://www.kicker.de/news/fussball{0}/2017-18/spieltag.html'.format(league['live'])
    res = requests.get(url)
    html = res.content
    soup = BeautifulSoup(html, "html.parser")
    standings = soup.find_all('tr', 'fest')
    current_standings = []
    for s in standings:
        goals = None
        halftime = r'-:-\(\d+:\d+\)'
        goals_tag = s.find('td', 'alignleft')
        live_goals_tag = s.find('span') # has span tag if in play
        goals_text = goals_tag.text.encode('ascii', errors='ignore')
        first_half = re.search(r'\d+:\d+', goals_text).group(0) if goals_text and re.search(halftime, goals_text) else None
        if live_goals_tag:
            goals = live_goals_tag.text.encode('ascii', errors='ignore').split(':')
        elif first_half:
            goals = first_half.split(':')
        if goals:
            team_links = list(filter(lambda el: len(el.text.encode('ascii', errors='ignore')) > 2, s.find_all('a', 'ovVrn')))
            team_names = list(map(lambda l: get_team_code(l.text.encode('ascii', errors='ignore'), teams), team_links))
            formatted = {'homeTeam': team_names[0], 'awayTeam': team_names[1], 'homeGoals': goals[0], 'awayGoals': goals[1]}
            current_standings.append(formatted)
    return current_standings

def get_standings(league_code, status):
    global global_standings
    with open('leagues.json') as json_data:
        leagues = json.load(json_data)
        league = next((l for l in leagues if l['code'] == league_code), None)
        if not league:
            global_standings = 'league not found'
            sys.exit()
        teams = get_teams(league['id']) if league['id'] else []
        if status == 'in_play':
            while True:
                global_standings = get_live_standings(league, teams)
                time.sleep(30)
        elif not league['id']:
            sys.exit('League is live results only')
        else:
            fixtures = get_fixtures(league_code, status)
            def format_fixture(fixture):
                home_team = get_team_code(fixture['homeTeamName'], teams)
                away_team = get_team_code(fixture['awayTeamName'], teams)
                home_goals = fixture['result']['goalsHomeTeam']
                away_goals = fixture['result']['goalsAwayTeam']
                return {'homeTeam': home_team, 'awayTeam': away_team, 'homeGoals': home_goals, 'awayGoals': away_goals}
            global_standings = list(map(format_fixture, fixtures))

def get_fixture_string(fixture):
    home_goals = fixture['homeGoals']
    away_goals = fixture['awayGoals']
    score = '{0}{1}'.format(home_goals, away_goals) if home_goals is not None and away_goals is not None else '-'
    return '{0}{2}{1}'.format(fixture['homeTeam'], fixture['awayTeam'], score)

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
        if 'global_standings' in globals():
            with canvas(device) as draw:
                if type(global_standings) == str:
                    sys.exit(global_standings)
                elif len(global_standings) == 0:
                    text(draw, (0, 0), 'No match', fill="white", font=proportional(TINY_FONT))    
                else:
                    text(draw, (0, 0), get_fixture_string(global_standings[match]), fill="white", font=proportional(TINY_FONT))
                    match = match + 1 if (match + 1) < len(global_standings) else 0
            time.sleep(5)
        else:
            with canvas(device) as draw:
                draw_loader(progress, draw)
            progress += 1
            time.sleep(0.15)

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Get football results for one league.')
        status_list = ['in_play', 'finished', 'timed']
        parser.add_argument('league', type=str, help='league code - e.g. PL for Premier League')
        parser.add_argument('-s', '--status', metavar='<status>', type=str, default='in_play', choices=status_list, help='match status')
        args = parser.parse_args()

        thread.start_new_thread(get_standings, (args.league, args.status))
        display()
    except KeyboardInterrupt:
        pass
