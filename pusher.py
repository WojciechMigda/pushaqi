#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import logging
from pathlib import Path
import plac
from typing import Dict, List, Set, Tuple, Union, Any

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from xml.dom import minidom


MASTODON_HOST = ''
MASTODON_TOKEN = ''

AQI_PM25_LEVELS = {
    'Good' : dict(hi=12.0,
                  img='pics/00E400.gif',
                  sensitive=None,
                  regular=None),
    'Moderate': dict(hi=25.4,
                     img='pics/FFFF00.gif',
                     sensitive='Unusually sensitive people should consider reducing prolonged or heavy exertion.',
                     regular=None),
    'Unhealthy for Sensitive Groups': dict(hi=55.4,
                                           img='pics/FF7E00.gif',
                                           sensitive='People with heart or lung disease, older adults, children, and people of lower socioeconomic status should reduce prolonged or heavy exertion.',
                                           regular=None),
    'Unhealthy': dict(hi=150.4,
                      img='pics/FF0000.gif',
                      sensitive='People with heart or lung disease, older adults, children, and people of lower socioeconomic status should avoid prolonged or heavy exertion.',
                      regular='Everyone else should reduce prolonged or heavy exertion'),
    'Very Unhealthy': dict(hi=250.4,
                           img='pics/8F3F97.gif',
                           sensitive='People with heart or lung disease, older adults, children, and people of lower socioeconomic status should avoid all physical activity outdoors',
                           regular='Everyone else should avoid prolonged or heavy exertion.'),
    'Hazardous': dict(hi=500.4,
                      img='pics/7E0023.gif',
                      sensitive='People with heart or lung disease, older adults, children, and people of lower socioeconomic status should remain indoors and keep activity levels low.',
                      regular='Everyone should avoid all physical activity outdoors.'),
}


"""
pm10        ug/m3
pm25        ug/m3
pm1         ug/m3
pressure    mbar
humidity    %
temperature F
wind        mph
"""
SENSORS = {
    'Mikolajska':       'https://airly.org/widget/v2/?width=280&height=380&displayMeasurements=true&displayCAQI=false&autoHeight=true&autoWidth=false&language=en&indexType=AIRLY_US_AQI&unitSpeed=imperial&unitTemperature=fahrenheit&latitude=50.062006&longitude=19.940984&locationId=8077',
    'Szpitalna':        'https://airly.org/widget/v2/?width=280&height=380&displayMeasurements=true&displayCAQI=false&autoHeight=true&autoWidth=false&language=en&indexType=AIRLY_US_AQI&unitSpeed=imperial&unitTemperature=fahrenheit&latitude=50.064539&longitude=19.942561&locationId=10213',
    'Franciszkanska':   'https://airly.org/widget/v2/?width=280&height=380&displayMeasurements=true&displayCAQI=false&autoHeight=true&autoWidth=false&language=en&indexType=AIRLY_US_AQI&unitSpeed=imperial&unitTemperature=fahrenheit&latitude=50.059085&longitude=19.933919&locationId=10211',
    'Warszawska':       'https://airly.org/widget/v2/?width=280&height=380&displayMeasurements=true&displayCAQI=false&autoHeight=true&autoWidth=false&language=en&indexType=AIRLY_US_AQI&unitSpeed=imperial&unitTemperature=fahrenheit&latitude=50.070088&longitude=19.943812&locationId=10048',
    'Studencka':        'https://airly.org/widget/v2/?width=280&height=380&displayMeasurements=true&displayCAQI=false&autoHeight=true&autoWidth=false&language=en&indexType=AIRLY_US_AQI&unitSpeed=imperial&unitTemperature=fahrenheit&latitude=50.062418&longitude=19.928368&locationId=9910',
    'Straszewskiego':   'https://airly.org/widget/v2/?width=280&height=380&displayMeasurements=true&displayCAQI=false&autoHeight=true&autoWidth=false&language=en&indexType=AIRLY_US_AQI&unitSpeed=imperial&unitTemperature=fahrenheit&latitude=50.057224&longitude=19.933157&locationId=57570',
}


CHAR_MAP = {
    '-': 'M* 14.13L* 14.13L* 12.35L* 12.35L* 14.13Z',
    '0': 'M* 18.23L* 18.23Q* * * 16.56Q* * * 11.68L* 11.68Q* * * 6.80Q* * * 5.13L* 5.13Q* * * 6.80Q* * * 11.66L* 11.66Q* * * 16.56Q* * * 18.23ZM* 16.43L* 16.43Q* * * 15.29Q* * * 11.66L* 11.66Q* * * 8.08Q* * * 6.97L* 6.97Q* * * 8.09Q* * * 11.66L* 11.66Q* * * 15.29Q* * * 16.43Z',
    '1': 'M* 17.03L* 17.03L* 6.98L* 7.24L* 9.50L* 7.43L* 5.27L* 5.27L* 17.03ZM* 18.09L* 18.09L* 16.22L* 16.22L* 18.09Z',
    '2': 'M* 18.09L* 18.09L* 16.38L* 11.68Q* * * 10.13Q* * * 8.75L* 8.75Q* * * 7.42Q* * * 6.97L* 6.97Q* * * 7.30Q* * * 8.30L* 8.30L* 6.61Q* * * 5.53Q* * * 5.13L* 5.13Q* * * 5.54Q* * * 6.74Q* * * 8.60L* 8.60Q* * * 10.68Q* * * 12.85L* 12.85L* 16.99L* 16.22L* 16.22L* 18.09Z',
    '3': 'M* 18.22L* 18.22Q* * * 17.83Q* * * 16.74L* 16.74L* 15.05Q* * * 16.05Q* * * 16.38L* 16.38Q* * * 15.90Q* * * 14.42L* 14.42Q* * * 12.98Q* * * 12.51L* 12.51L* 12.51L* 10.67L* 10.67Q* * * 10.21Q* * * 8.80L* 8.80Q* * * 7.43Q* * * 6.97L* 6.97Q* * * 7.30Q* * * 8.30L* 8.30L* 6.61Q* * * 5.53Q* * * 5.13L* 5.13Q* * * 5.54Q* * * 6.72Q* * * 8.51L* 8.51Q* * * 10.47Q* * * 11.59L* 11.59L* 11.41Q* * * 12.52Q* * * 14.62L* 14.62Q* * * 17.25Q* * * 18.22Z',
    '4': 'M* 18.09L* 18.09L* 8.14L* 8.14L* 14.49L* 13.75L* 13.75L* 15.57L* 15.57L* 13.86L* 5.27L* 5.27L* 18.09Z',
    '5': 'M* 18.22L* 18.22Q* * * 17.82Q* * * 16.74L* 16.74L* 15.05Q* * * 16.04Q* * * 16.38L* 16.38Q* * * 15.78Q* * * 14.06L* 14.06Q* * * 12.82Q* * * 12.01Q* * * 11.72L* 11.72Q* * * 12.00Q* * * 12.82L* 12.82L* 12.82L* 5.27L* 5.27L* 7.09L* 7.09L* 11.32L* 11.21Q* * * 10.22Q* * * 9.88L* 9.88Q* * * 10.40Q* * * 11.84Q* * * 13.99L* 13.99Q* * * 16.21Q* * * 17.69Q* * * 18.22Z',
    '6': 'M* 18.23L* 18.23Q* * * 16.61Q* * * 11.92L* 11.92Q* * * 8.25Q* * * 5.93Q* * * 5.13L* 5.13Q* * * 5.51Q* * * 6.61L* 6.61L* 8.30Q* * * 7.28Q* * * 6.97L* 6.97Q* * * 8.24Q* * * 11.88L* 11.88L* 12.85L* 12.40Q* * * 11.06Q* * * 10.18Q* * * 9.86L* 9.86Q* * * 10.40Q* * * 11.85Q* * * 13.99L* 13.99Q* * * 16.19Q* * * 17.69Q* * * 18.23ZM* 16.40L* 16.40Q* * * 15.76Q* * * 14.06L* 14.06Q* * * 12.36Q* * * 11.72L* 11.72Q* * * 12.02Q* * * 12.84Q* * * 14.06L* 14.06Q* * * 15.28Q* * * 16.10Q* * * 16.40Z',
    '7': 'M* 7.00L* 18.09L* 18.09L* 6.43L* 7.15L* 7.15L* 5.27L* 5.27L* 7.00Z',
    '8': 'M* 18.22L* 18.22Q* * * 17.79Q* * * 16.56Q* * * 14.63L* 14.63Q* * * 12.43Q* * * 11.38L* 11.38L* 11.65Q* * * 10.56Q* * * 8.57L* 8.57Q* * * 6.73Q* * * 5.54Q* * * 5.13L* 5.13Q* * * 5.54Q* * * 6.73Q* * * 8.57L* 8.57Q* * * 10.58Q* * * 11.65L* 11.65L* 11.38Q* * * 12.46Q* * * 14.63L* 14.63Q* * * 16.56Q* * * 17.79Q* * * 18.22ZM* 16.42L* 16.42Q* * * 15.92Q* * * 14.47L* 14.47Q* * * 13.02Q* * * 12.35L* 12.35Q* * * 13.02Q* * * 14.47L* 14.47Q* * * 15.92Q* * * 16.42ZM* 10.87L* 10.87Q* * * 10.20Q* * * 8.80L* 8.80Q* * * 7.41Q* * * 6.93L* 6.93Q* * * 7.41Q* * * 8.80L* 8.80Q* * * 10.20Q* * * 10.87Z',
    '9': 'M* 5.13L* 5.13Q* * * 6.76Q* * * 11.45L* 11.45Q* * * 15.11Q* * * 17.43Q* * * 18.23L* 18.23Q* * * 17.86Q* * * 16.76L* 16.76L* 15.07Q* * * 16.08Q* * * 16.40L* 16.40Q* * * 15.13Q* * * 11.48L* 11.48L* 10.51L* 10.96Q* * * 12.30Q* * * 13.19Q* * * 13.50L* 13.50Q* * * 12.97Q* * * 11.51Q* * * 9.38L* 9.38Q* * * 7.17Q* * * 5.67Q* * * 5.13ZM* 6.97L* 6.97Q* * * 7.61Q* * * 9.31L* 9.31Q* * * 11.01Q* * * 11.65L* 11.65Q* * * 11.35Q* * * 10.52Q* * * 9.31L* 9.31Q* * * 8.08Q* * * 7.26Q* * * 6.97Z',
}


def svg_path_reduce(path: str) -> str:
    # 1. remove isolated numbers
    # 2. remove numbers which follow uppercase letter
    path = re.sub(r'(?<= )[\d.]+(?= )', '*', path)
    return re.sub(r'(?<=[A-Z])[\d.]+', '*', path)


def svg_path_to_number(path: str) -> str:
    path = svg_path_reduce(path)
    for char, signature in CHAR_MAP.items():
        path = path.replace(signature, f'|{char}|')
    return path.replace('|', '')


def test_character_recognition():
    test_vector: Dict[str, str] = {
        # -
        'M6.66 14.13L1.24 14.13L1.24 12.35L6.66 12.35L6.66 14.13Z': '-',
        # 0_1
        'M5.40 18.23L5.40 18.23Q3.13 18.23 1.93 16.56Q0.72 14.89 0.72 11.68L0.72 11.68Q0.72 8.48 1.92 6.80Q3.11 5.13 5.40 5.13L5.40 5.13Q7.69 5.13 8.88 6.80Q10.08 8.48 10.08 11.66L10.08 11.66Q10.08 14.89 8.87 16.56Q7.67 18.23 5.40 18.23ZM5.40 16.43L5.40 16.43Q6.64 16.43 7.22 15.29Q7.79 14.15 7.79 11.66L7.79 11.66Q7.79 9.20 7.22 8.08Q6.64 6.97 5.40 6.97L5.40 6.97Q4.16 6.97 3.58 8.09Q3.01 9.22 3.01 11.66L3.01 11.66Q3.01 14.15 3.58 15.29Q4.16 16.43 5.40 16.43Z': '0',
        # 0_2
        'M16.20 18.23L16.20 18.23Q13.93 18.23 12.73 16.56Q11.52 14.89 11.52 11.68L11.52 11.68Q11.52 8.48 12.72 6.80Q13.91 5.13 16.20 5.13L16.20 5.13Q18.49 5.13 19.68 6.80Q20.88 8.48 20.88 11.66L20.88 11.66Q20.88 14.89 19.67 16.56Q18.47 18.23 16.20 18.23ZM16.20 16.43L16.20 16.43Q17.44 16.43 18.02 15.29Q18.59 14.15 18.59 11.66L18.59 11.66Q18.59 9.20 18.02 8.08Q17.44 6.97 16.20 6.97L16.20 6.97Q14.96 6.97 14.38 8.09Q13.81 9.22 13.81 11.66L13.81 11.66Q13.81 14.15 14.38 15.29Q14.96 16.43 16.20 16.43Z': '0',
        # 0_4
        'M37.80 18.23L37.80 18.23Q35.53 18.23 34.33 16.56Q33.12 14.89 33.12 11.68L33.12 11.68Q33.12 8.48 34.32 6.80Q35.51 5.13 37.80 5.13L37.80 5.13Q40.09 5.13 41.28 6.80Q42.48 8.48 42.48 11.66L42.48 11.66Q42.48 14.89 41.27 16.56Q40.07 18.23 37.80 18.23ZM37.80 16.43L37.80 16.43Q39.04 16.43 39.62 15.29Q40.19 14.15 40.19 11.66L40.19 11.66Q40.19 9.20 39.62 8.08Q39.04 6.97 37.80 6.97L37.80 6.97Q36.56 6.97 35.98 8.09Q35.41 9.22 35.41 11.66L35.41 11.66Q35.41 14.15 35.98 15.29Q36.56 16.43 37.80 16.43Z': '0',
        # 1_1
        'M7.13 17.03L4.81 17.03L4.81 6.98L5.98 7.24L2.21 9.50L2.21 7.43L5.78 5.27L7.13 5.27L7.13 17.03ZM9.94 18.09L2.02 18.09L2.02 16.22L9.94 16.22L9.94 18.09Z': '1',
        # 1_2
        'M17.93 17.03L15.61 17.03L15.61 6.98L16.78 7.24L13.01 9.50L13.01 7.43L16.58 5.27L17.93 5.27L17.93 17.03ZM20.74 18.09L12.82 18.09L12.82 16.22L20.74 16.22L20.74 18.09Z': '1',
        # neg 1_1
        'M15.01 17.03L12.69 17.03L12.69 6.98L13.86 7.24L10.10 9.50L10.10 7.43L13.66 5.27L15.01 5.27L15.01 17.03ZM17.82 18.09L9.90 18.09L9.90 16.22L17.82 16.22L17.82 18.09Z': '1',
        # 2_1
        'M9.88 18.09L1.30 18.09L1.30 16.38L5.63 11.68Q6.39 10.84 6.75 10.13Q7.11 9.43 7.11 8.75L7.11 8.75Q7.11 7.87 6.61 7.42Q6.10 6.97 5.15 6.97L5.15 6.97Q4.28 6.97 3.41 7.30Q2.54 7.63 1.67 8.30L1.67 8.30L0.88 6.61Q1.66 5.92 2.84 5.53Q4.03 5.13 5.26 5.13L5.26 5.13Q6.52 5.13 7.45 5.54Q8.39 5.96 8.89 6.74Q9.40 7.52 9.40 8.60L9.40 8.60Q9.40 9.72 8.93 10.68Q8.46 11.65 7.34 12.85L7.34 12.85L3.44 16.99L3.17 16.22L9.88 16.22L9.88 18.09Z': '2',
        # 2_2
        'M20.68 18.09L12.10 18.09L12.10 16.38L16.43 11.68Q17.19 10.84 17.55 10.13Q17.91 9.43 17.91 8.75L17.91 8.75Q17.91 7.87 17.41 7.42Q16.90 6.97 15.95 6.97L15.95 6.97Q15.08 6.97 14.21 7.30Q13.34 7.63 12.47 8.30L12.47 8.30L11.68 6.61Q12.46 5.92 13.64 5.53Q14.83 5.13 16.06 5.13L16.06 5.13Q17.32 5.13 18.25 5.54Q19.19 5.96 19.69 6.74Q20.20 7.52 20.20 8.60L20.20 8.60Q20.20 9.72 19.73 10.68Q19.26 11.65 18.14 12.85L18.14 12.85L14.24 16.99L13.97 16.22L20.68 16.22L20.68 18.09Z': '2',
        # 2_3
        'M31.48 18.09L22.90 18.09L22.90 16.38L27.23 11.68Q27.99 10.84 28.35 10.13Q28.71 9.43 28.71 8.75L28.71 8.75Q28.71 7.87 28.21 7.42Q27.70 6.97 26.75 6.97L26.75 6.97Q25.88 6.97 25.01 7.30Q24.14 7.63 23.27 8.30L23.27 8.30L22.48 6.61Q23.26 5.92 24.44 5.53Q25.63 5.13 26.86 5.13L26.86 5.13Q28.12 5.13 29.05 5.54Q29.99 5.96 30.49 6.74Q31.00 7.52 31.00 8.60L31.00 8.60Q31.00 9.72 30.53 10.68Q30.06 11.65 28.94 12.85L28.94 12.85L25.04 16.99L24.77 16.22L31.48 16.22L31.48 18.09Z': '2',
        # 3_1
        'M5.17 18.22L5.17 18.22Q3.87 18.22 2.67 17.83Q1.48 17.44 0.70 16.74L0.70 16.74L1.49 15.05Q2.34 15.71 3.23 16.05Q4.12 16.38 5.08 16.38L5.08 16.38Q6.32 16.38 6.91 15.90Q7.51 15.43 7.51 14.42L7.51 14.42Q7.51 13.45 6.89 12.98Q6.28 12.51 5.00 12.51L5.00 12.51L3.31 12.51L3.31 10.67L4.70 10.67Q5.94 10.67 6.56 10.21Q7.18 9.74 7.18 8.80L7.18 8.80Q7.18 7.90 6.64 7.43Q6.10 6.97 5.15 6.97L5.15 6.97Q4.27 6.97 3.38 7.30Q2.50 7.63 1.67 8.30L1.67 8.30L0.88 6.61Q1.66 5.92 2.84 5.53Q4.03 5.13 5.27 5.13L5.27 5.13Q6.53 5.13 7.46 5.54Q8.39 5.96 8.89 6.72Q9.40 7.49 9.40 8.51L9.40 8.51Q9.40 9.67 8.80 10.47Q8.21 11.27 7.13 11.59L7.13 11.59L7.11 11.41Q8.37 11.70 9.05 12.52Q9.72 13.34 9.72 14.62L9.72 14.62Q9.72 16.29 8.49 17.25Q7.25 18.22 5.17 18.22Z': '3',
        # 3_2
        'M15.97 18.22L15.97 18.22Q14.67 18.22 13.47 17.83Q12.28 17.44 11.50 16.74L11.50 16.74L12.29 15.05Q13.14 15.71 14.03 16.05Q14.92 16.38 15.88 16.38L15.88 16.38Q17.12 16.38 17.71 15.90Q18.31 15.43 18.31 14.42L18.31 14.42Q18.31 13.45 17.69 12.98Q17.08 12.51 15.80 12.51L15.80 12.51L14.11 12.51L14.11 10.67L15.50 10.67Q16.74 10.67 17.36 10.21Q17.98 9.74 17.98 8.80L17.98 8.80Q17.98 7.90 17.44 7.43Q16.90 6.97 15.95 6.97L15.95 6.97Q15.07 6.97 14.18 7.30Q13.30 7.63 12.47 8.30L12.47 8.30L11.68 6.61Q12.46 5.92 13.64 5.53Q14.83 5.13 16.07 5.13L16.07 5.13Q17.33 5.13 18.26 5.54Q19.19 5.96 19.69 6.72Q20.20 7.49 20.20 8.51L20.20 8.51Q20.20 9.67 19.60 10.47Q19.01 11.27 17.93 11.59L17.93 11.59L17.91 11.41Q19.17 11.70 19.85 12.52Q20.52 13.34 20.52 14.62L20.52 14.62Q20.52 16.29 19.29 17.25Q18.05 18.22 15.97 18.22Z': '3',
        # 3_3
        'M26.77 18.22L26.77 18.22Q25.47 18.22 24.27 17.83Q23.08 17.44 22.30 16.74L22.30 16.74L23.09 15.05Q23.94 15.71 24.83 16.05Q25.72 16.38 26.68 16.38L26.68 16.38Q27.92 16.38 28.51 15.90Q29.11 15.43 29.11 14.42L29.11 14.42Q29.11 13.45 28.49 12.98Q27.88 12.51 26.60 12.51L26.60 12.51L24.91 12.51L24.91 10.67L26.30 10.67Q27.54 10.67 28.16 10.21Q28.78 9.74 28.78 8.80L28.78 8.80Q28.78 7.90 28.24 7.43Q27.70 6.97 26.75 6.97L26.75 6.97Q25.87 6.97 24.98 7.30Q24.10 7.63 23.27 8.30L23.27 8.30L22.48 6.61Q23.26 5.92 24.44 5.53Q25.63 5.13 26.87 5.13L26.87 5.13Q28.13 5.13 29.06 5.54Q29.99 5.96 30.49 6.72Q31.00 7.49 31.00 8.51L31.00 8.51Q31.00 9.67 30.40 10.47Q29.81 11.27 28.73 11.59L28.73 11.59L28.71 11.41Q29.97 11.70 30.65 12.52Q31.32 13.34 31.32 14.62L31.32 14.62Q31.32 16.29 30.09 17.25Q28.85 18.22 26.77 18.22Z': '3',
        # 4_1
        'M8.55 18.09L6.26 18.09L6.26 8.14L6.80 8.14L2.38 14.49L2.39 13.75L10.37 13.75L10.37 15.57L0.70 15.57L0.70 13.86L6.70 5.27L8.55 5.27L8.55 18.09Z': '4',
        # 4_2
        'M19.35 18.09L17.06 18.09L17.06 8.14L17.60 8.14L13.18 14.49L13.19 13.75L21.17 13.75L21.17 15.57L11.50 15.57L11.50 13.86L17.50 5.27L19.35 5.27L19.35 18.09Z': '4',
        # 5_1
        'M5.40 18.22L5.40 18.22Q4.21 18.22 3.03 17.82Q1.85 17.42 1.10 16.74L1.10 16.74L1.87 15.05Q2.74 15.70 3.63 16.04Q4.52 16.38 5.44 16.38L5.44 16.38Q6.62 16.38 7.27 15.78Q7.92 15.17 7.92 14.06L7.92 14.06Q7.92 13.34 7.62 12.82Q7.33 12.29 6.79 12.01Q6.25 11.72 5.51 11.72L5.51 11.72Q4.77 11.72 4.10 12.00Q3.44 12.28 2.90 12.82L2.90 12.82L1.51 12.82L1.51 5.27L9.54 5.27L9.54 7.09L3.78 7.09L3.78 11.32L3.08 11.21Q3.62 10.57 4.37 10.22Q5.13 9.88 6.08 9.88L6.08 9.88Q7.29 9.88 8.20 10.40Q9.11 10.93 9.62 11.84Q10.13 12.76 10.13 13.99L10.13 13.99Q10.13 15.25 9.55 16.21Q8.96 17.17 7.91 17.69Q6.86 18.22 5.40 18.22Z': '5',
        # 5_2
        'M16.20 18.22L16.20 18.22Q15.01 18.22 13.83 17.82Q12.65 17.42 11.90 16.74L11.90 16.74L12.67 15.05Q13.54 15.70 14.43 16.04Q15.32 16.38 16.24 16.38L16.24 16.38Q17.42 16.38 18.07 15.78Q18.72 15.17 18.72 14.06L18.72 14.06Q18.72 13.34 18.42 12.82Q18.13 12.29 17.59 12.01Q17.05 11.72 16.31 11.72L16.31 11.72Q15.57 11.72 14.90 12.00Q14.24 12.28 13.70 12.82L13.70 12.82L12.31 12.82L12.31 5.27L20.34 5.27L20.34 7.09L14.58 7.09L14.58 11.32L13.88 11.21Q14.42 10.57 15.17 10.22Q15.93 9.88 16.88 9.88L16.88 9.88Q18.09 9.88 19.00 10.40Q19.91 10.93 20.42 11.84Q20.93 12.76 20.93 13.99L20.93 13.99Q20.93 15.25 20.35 16.21Q19.76 17.17 18.71 17.69Q17.66 18.22 16.20 18.22Z': '5',
        # 5_4
        'M37.80 18.22L37.80 18.22Q36.61 18.22 35.43 17.82Q34.25 17.42 33.50 16.74L33.50 16.74L34.27 15.05Q35.14 15.70 36.03 16.04Q36.92 16.38 37.84 16.38L37.84 16.38Q39.02 16.38 39.67 15.78Q40.32 15.17 40.32 14.06L40.32 14.06Q40.32 13.34 40.02 12.82Q39.73 12.29 39.19 12.01Q38.65 11.72 37.91 11.72L37.91 11.72Q37.17 11.72 36.50 12.00Q35.84 12.28 35.30 12.82L35.30 12.82L33.91 12.82L33.91 5.27L41.94 5.27L41.94 7.09L36.18 7.09L36.18 11.32L35.48 11.21Q36.02 10.57 36.77 10.22Q37.53 9.88 38.48 9.88L38.48 9.88Q39.69 9.88 40.60 10.40Q41.51 10.93 42.02 11.84Q42.53 12.76 42.53 13.99L42.53 13.99Q42.53 15.25 41.95 16.21Q41.36 17.17 40.31 17.69Q39.26 18.22 37.80 18.22Z': '5',
        # 6_1
        'M5.81 18.23L5.81 18.23Q3.40 18.23 2.08 16.61Q0.76 14.98 0.76 11.92L0.76 11.92Q0.76 9.77 1.38 8.25Q2.00 6.73 3.18 5.93Q4.36 5.13 5.98 5.13L5.98 5.13Q7.13 5.13 8.22 5.51Q9.31 5.89 10.12 6.61L10.12 6.61L9.32 8.30Q8.44 7.60 7.62 7.28Q6.80 6.97 6.07 6.97L6.07 6.97Q4.61 6.97 3.83 8.24Q3.04 9.50 3.04 11.88L3.04 11.88L3.04 12.85L2.79 12.40Q2.95 11.63 3.44 11.06Q3.92 10.49 4.64 10.18Q5.35 9.86 6.19 9.86L6.19 9.86Q7.34 9.86 8.23 10.40Q9.11 10.93 9.61 11.85Q10.12 12.78 10.12 13.99L10.12 13.99Q10.12 15.23 9.56 16.19Q9.00 17.15 8.04 17.69Q7.07 18.23 5.81 18.23ZM5.71 16.40L5.71 16.40Q6.70 16.40 7.30 15.76Q7.90 15.12 7.90 14.06L7.90 14.06Q7.90 13.00 7.30 12.36Q6.70 11.72 5.69 11.72L5.69 11.72Q5.02 11.72 4.51 12.02Q4.00 12.31 3.71 12.84Q3.42 13.37 3.42 14.06L3.42 14.06Q3.42 14.76 3.71 15.28Q4.00 15.80 4.51 16.10Q5.02 16.40 5.71 16.40Z': '6',
        # 6_2
        'M16.61 18.23L16.61 18.23Q14.20 18.23 12.88 16.61Q11.56 14.98 11.56 11.92L11.56 11.92Q11.56 9.77 12.18 8.25Q12.80 6.73 13.98 5.93Q15.16 5.13 16.78 5.13L16.78 5.13Q17.93 5.13 19.02 5.51Q20.11 5.89 20.92 6.61L20.92 6.61L20.12 8.30Q19.24 7.60 18.42 7.28Q17.60 6.97 16.87 6.97L16.87 6.97Q15.41 6.97 14.63 8.24Q13.84 9.50 13.84 11.88L13.84 11.88L13.84 12.85L13.59 12.40Q13.75 11.63 14.24 11.06Q14.72 10.49 15.44 10.18Q16.15 9.86 16.99 9.86L16.99 9.86Q18.14 9.86 19.03 10.40Q19.91 10.93 20.41 11.85Q20.92 12.78 20.92 13.99L20.92 13.99Q20.92 15.23 20.36 16.19Q19.80 17.15 18.84 17.69Q17.87 18.23 16.61 18.23ZM16.51 16.40L16.51 16.40Q17.50 16.40 18.10 15.76Q18.70 15.12 18.70 14.06L18.70 14.06Q18.70 13.00 18.10 12.36Q17.50 11.72 16.49 11.72L16.49 11.72Q15.82 11.72 15.31 12.02Q14.80 12.31 14.51 12.84Q14.22 13.37 14.22 14.06L14.22 14.06Q14.22 14.76 14.51 15.28Q14.80 15.80 15.31 16.10Q15.82 16.40 16.51 16.40Z': '6',
        # 6_4
        'M38.21 18.23L38.21 18.23Q35.80 18.23 34.48 16.61Q33.16 14.98 33.16 11.92L33.16 11.92Q33.16 9.77 33.78 8.25Q34.40 6.73 35.58 5.93Q36.76 5.13 38.38 5.13L38.38 5.13Q39.53 5.13 40.62 5.51Q41.71 5.89 42.52 6.61L42.52 6.61L41.72 8.30Q40.84 7.60 40.02 7.28Q39.20 6.97 38.47 6.97L38.47 6.97Q37.01 6.97 36.23 8.24Q35.44 9.50 35.44 11.88L35.44 11.88L35.44 12.85L35.19 12.40Q35.35 11.63 35.84 11.06Q36.32 10.49 37.04 10.18Q37.75 9.86 38.59 9.86L38.59 9.86Q39.74 9.86 40.63 10.40Q41.51 10.93 42.01 11.85Q42.52 12.78 42.52 13.99L42.52 13.99Q42.52 15.23 41.96 16.19Q41.40 17.15 40.44 17.69Q39.47 18.23 38.21 18.23ZM38.11 16.40L38.11 16.40Q39.10 16.40 39.70 15.76Q40.30 15.12 40.30 14.06L40.30 14.06Q40.30 13.00 39.70 12.36Q39.10 11.72 38.09 11.72L38.09 11.72Q37.42 11.72 36.91 12.02Q36.40 12.31 36.11 12.84Q35.82 13.37 35.82 14.06L35.82 14.06Q35.82 14.76 36.11 15.28Q36.40 15.80 36.91 16.10Q37.42 16.40 38.11 16.40Z': '6',
        # 7_1
        'M9.86 7.00L4.05 18.09L1.57 18.09L7.76 6.43L7.81 7.15L0.94 7.15L0.94 5.27L9.86 5.27L9.86 7.00Z': '7',
        # 7_2
        'M20.66 7.00L14.85 18.09L12.37 18.09L18.56 6.43L18.61 7.15L11.74 7.15L11.74 5.27L20.66 5.27L20.66 7.00Z': '7',
        # 7_4
        'M42.26 7.00L36.45 18.09L33.97 18.09L40.16 6.43L40.21 7.15L33.34 7.15L33.34 5.27L42.26 5.27L42.26 7.00Z': '7',
        # 8_1
        'M5.40 18.22L5.40 18.22Q3.98 18.22 2.90 17.79Q1.82 17.37 1.22 16.56Q0.61 15.75 0.61 14.63L0.61 14.63Q0.61 13.28 1.49 12.43Q2.38 11.57 3.91 11.38L3.91 11.38L3.83 11.65Q2.48 11.38 1.69 10.56Q0.90 9.74 0.90 8.57L0.90 8.57Q0.90 7.51 1.49 6.73Q2.07 5.96 3.09 5.54Q4.10 5.13 5.40 5.13L5.40 5.13Q6.70 5.13 7.71 5.54Q8.73 5.96 9.32 6.73Q9.90 7.51 9.90 8.57L9.90 8.57Q9.90 9.76 9.11 10.58Q8.32 11.41 6.98 11.65L6.98 11.65L6.91 11.38Q8.44 11.59 9.32 12.46Q10.19 13.32 10.19 14.63L10.19 14.63Q10.19 15.75 9.59 16.56Q8.98 17.37 7.90 17.79Q6.82 18.22 5.40 18.22ZM5.40 16.42L5.40 16.42Q6.61 16.42 7.31 15.92Q8.01 15.43 8.01 14.47L8.01 14.47Q8.01 13.55 7.28 13.02Q6.55 12.49 5.40 12.35L5.40 12.35Q4.25 12.49 3.52 13.02Q2.79 13.55 2.79 14.47L2.79 14.47Q2.79 15.43 3.49 15.92Q4.19 16.42 5.40 16.42ZM5.40 10.87L5.40 10.87Q6.39 10.71 7.04 10.20Q7.69 9.68 7.69 8.80L7.69 8.80Q7.69 7.88 7.07 7.41Q6.44 6.93 5.40 6.93L5.40 6.93Q4.36 6.93 3.74 7.41Q3.11 7.88 3.11 8.80L3.11 8.80Q3.11 9.68 3.76 10.20Q4.41 10.71 5.40 10.87Z': '8',
        # 8_2
        'M16.20 18.22L16.20 18.22Q14.78 18.22 13.70 17.79Q12.62 17.37 12.02 16.56Q11.41 15.75 11.41 14.63L11.41 14.63Q11.41 13.28 12.29 12.43Q13.18 11.57 14.71 11.38L14.71 11.38L14.63 11.65Q13.28 11.38 12.49 10.56Q11.70 9.74 11.70 8.57L11.70 8.57Q11.70 7.51 12.29 6.73Q12.87 5.96 13.89 5.54Q14.90 5.13 16.20 5.13L16.20 5.13Q17.50 5.13 18.51 5.54Q19.53 5.96 20.12 6.73Q20.70 7.51 20.70 8.57L20.70 8.57Q20.70 9.76 19.91 10.58Q19.12 11.41 17.78 11.65L17.78 11.65L17.71 11.38Q19.24 11.59 20.12 12.46Q20.99 13.32 20.99 14.63L20.99 14.63Q20.99 15.75 20.39 16.56Q19.78 17.37 18.70 17.79Q17.62 18.22 16.20 18.22ZM16.20 16.42L16.20 16.42Q17.41 16.42 18.11 15.92Q18.81 15.43 18.81 14.47L18.81 14.47Q18.81 13.55 18.08 13.02Q17.35 12.49 16.20 12.35L16.20 12.35Q15.05 12.49 14.32 13.02Q13.59 13.55 13.59 14.47L13.59 14.47Q13.59 15.43 14.29 15.92Q14.99 16.42 16.20 16.42ZM16.20 10.87L16.20 10.87Q17.19 10.71 17.84 10.20Q18.49 9.68 18.49 8.80L18.49 8.80Q18.49 7.88 17.87 7.41Q17.24 6.93 16.20 6.93L16.20 6.93Q15.16 6.93 14.54 7.41Q13.91 7.88 13.91 8.80L13.91 8.80Q13.91 9.68 14.56 10.20Q15.21 10.71 16.20 10.87Z': '8',
        # 9_1
        'M4.99 5.13L4.99 5.13Q7.42 5.13 8.73 6.76Q10.04 8.39 10.04 11.45L10.04 11.45Q10.04 13.59 9.42 15.11Q8.80 16.63 7.63 17.43Q6.46 18.23 4.82 18.23L4.82 18.23Q3.67 18.23 2.58 17.86Q1.49 17.48 0.68 16.76L0.68 16.76L1.48 15.07Q2.38 15.77 3.19 16.08Q4.00 16.40 4.75 16.40L4.75 16.40Q6.21 16.40 6.98 15.13Q7.76 13.86 7.76 11.48L7.76 11.48L7.76 10.51L8.01 10.96Q7.85 11.74 7.36 12.30Q6.88 12.87 6.17 13.19Q5.45 13.50 4.61 13.50L4.61 13.50Q3.47 13.50 2.58 12.97Q1.69 12.44 1.19 11.51Q0.68 10.58 0.68 9.38L0.68 9.38Q0.68 8.14 1.24 7.17Q1.80 6.21 2.77 5.67Q3.74 5.13 4.99 5.13ZM5.11 6.97L5.11 6.97Q4.10 6.97 3.50 7.61Q2.90 8.24 2.90 9.31L2.90 9.31Q2.90 10.37 3.50 11.01Q4.10 11.65 5.11 11.65L5.11 11.65Q5.78 11.65 6.30 11.35Q6.82 11.05 7.10 10.52Q7.38 9.99 7.38 9.31L7.38 9.31Q7.38 8.60 7.10 8.08Q6.82 7.56 6.30 7.26Q5.78 6.97 5.11 6.97Z': '9',
        # 9_2
        'M15.79 5.13L15.79 5.13Q18.22 5.13 19.53 6.76Q20.84 8.39 20.84 11.45L20.84 11.45Q20.84 13.59 20.22 15.11Q19.60 16.63 18.43 17.43Q17.26 18.23 15.62 18.23L15.62 18.23Q14.47 18.23 13.38 17.86Q12.29 17.48 11.48 16.76L11.48 16.76L12.28 15.07Q13.18 15.77 13.99 16.08Q14.80 16.40 15.55 16.40L15.55 16.40Q17.01 16.40 17.78 15.13Q18.56 13.86 18.56 11.48L18.56 11.48L18.56 10.51L18.81 10.96Q18.65 11.74 18.16 12.30Q17.68 12.87 16.97 13.19Q16.25 13.50 15.41 13.50L15.41 13.50Q14.27 13.50 13.38 12.97Q12.49 12.44 11.99 11.51Q11.48 10.58 11.48 9.38L11.48 9.38Q11.48 8.14 12.04 7.17Q12.60 6.21 13.57 5.67Q14.54 5.13 15.79 5.13ZM15.91 6.97L15.91 6.97Q14.90 6.97 14.30 7.61Q13.70 8.24 13.70 9.31L13.70 9.31Q13.70 10.37 14.30 11.01Q14.90 11.65 15.91 11.65L15.91 11.65Q16.58 11.65 17.10 11.35Q17.62 11.05 17.90 10.52Q18.18 9.99 18.18 9.31L18.18 9.31Q18.18 8.60 17.90 8.08Q17.62 7.56 17.10 7.26Q16.58 6.97 15.91 6.97Z': '9',
        # 9_4
        'M37.39 5.13L37.39 5.13Q39.82 5.13 41.13 6.76Q42.44 8.39 42.44 11.45L42.44 11.45Q42.44 13.59 41.82 15.11Q41.20 16.63 40.03 17.43Q38.86 18.23 37.22 18.23L37.22 18.23Q36.07 18.23 34.98 17.86Q33.89 17.48 33.08 16.76L33.08 16.76L33.88 15.07Q34.78 15.77 35.59 16.08Q36.40 16.40 37.15 16.40L37.15 16.40Q38.61 16.40 39.38 15.13Q40.16 13.86 40.16 11.48L40.16 11.48L40.16 10.51L40.41 10.96Q40.25 11.74 39.76 12.30Q39.28 12.87 38.57 13.19Q37.85 13.50 37.01 13.50L37.01 13.50Q35.87 13.50 34.98 12.97Q34.09 12.44 33.59 11.51Q33.08 10.58 33.08 9.38L33.08 9.38Q33.08 8.14 33.64 7.17Q34.20 6.21 35.17 5.67Q36.14 5.13 37.39 5.13ZM37.51 6.97L37.51 6.97Q36.50 6.97 35.90 7.61Q35.30 8.24 35.30 9.31L35.30 9.31Q35.30 10.37 35.90 11.01Q36.50 11.65 37.51 11.65L37.51 11.65Q38.18 11.65 38.70 11.35Q39.22 11.05 39.50 10.52Q39.78 9.99 39.78 9.31L39.78 9.31Q39.78 8.60 39.50 8.08Q39.22 7.56 38.70 7.26Q38.18 6.97 37.51 6.97Z': '9',
    }
    for path, char in test_vector.items():
        assert CHAR_MAP[char] == svg_path_reduce(path), f'Char {char}\nexpected {CHAR_MAP[char]}\nfound {svg_path_reduce(path)}'


def test_number_recognition():
    test_vector = {
        'M7.13 17.03L4.81 17.03L4.81 6.98L5.98 7.24L2.21 9.50L2.21 7.43L5.78 5.27L7.13 5.27L7.13 17.03ZM9.94 18.09L2.02 18.09L2.02 16.22L9.94 16.22L9.94 18.09ZM16.20 18.23L16.20 18.23Q13.93 18.23 12.73 16.56Q11.52 14.89 11.52 11.68L11.52 11.68Q11.52 8.48 12.72 6.80Q13.91 5.13 16.20 5.13L16.20 5.13Q18.49 5.13 19.68 6.80Q20.88 8.48 20.88 11.66L20.88 11.66Q20.88 14.89 19.67 16.56Q18.47 18.23 16.20 18.23ZM16.20 16.43L16.20 16.43Q17.44 16.43 18.02 15.29Q18.59 14.15 18.59 11.66L18.59 11.66Q18.59 9.20 18.02 8.08Q17.44 6.97 16.20 6.97L16.20 6.97Q14.96 6.97 14.38 8.09Q13.81 9.22 13.81 11.66L13.81 11.66Q13.81 14.15 14.38 15.29Q14.96 16.43 16.20 16.43ZM31.48 18.09L22.90 18.09L22.90 16.38L27.23 11.68Q27.99 10.84 28.35 10.13Q28.71 9.43 28.71 8.75L28.71 8.75Q28.71 7.87 28.21 7.42Q27.70 6.97 26.75 6.97L26.75 6.97Q25.88 6.97 25.01 7.30Q24.14 7.63 23.27 8.30L23.27 8.30L22.48 6.61Q23.26 5.92 24.44 5.53Q25.63 5.13 26.86 5.13L26.86 5.13Q28.12 5.13 29.05 5.54Q29.99 5.96 30.49 6.74Q31.00 7.52 31.00 8.60L31.00 8.60Q31.00 9.72 30.53 10.68Q30.06 11.65 28.94 12.85L28.94 12.85L25.04 16.99L24.77 16.22L31.48 16.22L31.48 18.09ZM37.80 18.22L37.80 18.22Q36.61 18.22 35.43 17.82Q34.25 17.42 33.50 16.74L33.50 16.74L34.27 15.05Q35.14 15.70 36.03 16.04Q36.92 16.38 37.84 16.38L37.84 16.38Q39.02 16.38 39.67 15.78Q40.32 15.17 40.32 14.06L40.32 14.06Q40.32 13.34 40.02 12.82Q39.73 12.29 39.19 12.01Q38.65 11.72 37.91 11.72L37.91 11.72Q37.17 11.72 36.50 12.00Q35.84 12.28 35.30 12.82L35.30 12.82L33.91 12.82L33.91 5.27L41.94 5.27L41.94 7.09L36.18 7.09L36.18 11.32L35.48 11.21Q36.02 10.57 36.77 10.22Q37.53 9.88 38.48 9.88L38.48 9.88Q39.69 9.88 40.60 10.40Q41.51 10.93 42.02 11.84Q42.53 12.76 42.53 13.99L42.53 13.99Q42.53 15.25 41.95 16.21Q41.36 17.17 40.31 17.69Q39.26 18.22 37.80 18.22Z': '1025',
        'M5.40 18.22L5.40 18.22Q3.98 18.22 2.90 17.79Q1.82 17.37 1.22 16.56Q0.61 15.75 0.61 14.63L0.61 14.63Q0.61 13.28 1.49 12.43Q2.38 11.57 3.91 11.38L3.91 11.38L3.83 11.65Q2.48 11.38 1.69 10.56Q0.90 9.74 0.90 8.57L0.90 8.57Q0.90 7.51 1.49 6.73Q2.07 5.96 3.09 5.54Q4.10 5.13 5.40 5.13L5.40 5.13Q6.70 5.13 7.71 5.54Q8.73 5.96 9.32 6.73Q9.90 7.51 9.90 8.57L9.90 8.57Q9.90 9.76 9.11 10.58Q8.32 11.41 6.98 11.65L6.98 11.65L6.91 11.38Q8.44 11.59 9.32 12.46Q10.19 13.32 10.19 14.63L10.19 14.63Q10.19 15.75 9.59 16.56Q8.98 17.37 7.90 17.79Q6.82 18.22 5.40 18.22ZM5.40 16.42L5.40 16.42Q6.61 16.42 7.31 15.92Q8.01 15.43 8.01 14.47L8.01 14.47Q8.01 13.55 7.28 13.02Q6.55 12.49 5.40 12.35L5.40 12.35Q4.25 12.49 3.52 13.02Q2.79 13.55 2.79 14.47L2.79 14.47Q2.79 15.43 3.49 15.92Q4.19 16.42 5.40 16.42ZM5.40 10.87L5.40 10.87Q6.39 10.71 7.04 10.20Q7.69 9.68 7.69 8.80L7.69 8.80Q7.69 7.88 7.07 7.41Q6.44 6.93 5.40 6.93L5.40 6.93Q4.36 6.93 3.74 7.41Q3.11 7.88 3.11 8.80L3.11 8.80Q3.11 9.68 3.76 10.20Q4.41 10.71 5.40 10.87ZM15.97 18.22L15.97 18.22Q14.67 18.22 13.47 17.83Q12.28 17.44 11.50 16.74L11.50 16.74L12.29 15.05Q13.14 15.71 14.03 16.05Q14.92 16.38 15.88 16.38L15.88 16.38Q17.12 16.38 17.71 15.90Q18.31 15.43 18.31 14.42L18.31 14.42Q18.31 13.45 17.69 12.98Q17.08 12.51 15.80 12.51L15.80 12.51L14.11 12.51L14.11 10.67L15.50 10.67Q16.74 10.67 17.36 10.21Q17.98 9.74 17.98 8.80L17.98 8.80Q17.98 7.90 17.44 7.43Q16.90 6.97 15.95 6.97L15.95 6.97Q15.07 6.97 14.18 7.30Q13.30 7.63 12.47 8.30L12.47 8.30L11.68 6.61Q12.46 5.92 13.64 5.53Q14.83 5.13 16.07 5.13L16.07 5.13Q17.33 5.13 18.26 5.54Q19.19 5.96 19.69 6.72Q20.20 7.49 20.20 8.51L20.20 8.51Q20.20 9.67 19.60 10.47Q19.01 11.27 17.93 11.59L17.93 11.59L17.91 11.41Q19.17 11.70 19.85 12.52Q20.52 13.34 20.52 14.62L20.52 14.62Q20.52 16.29 19.29 17.25Q18.05 18.22 15.97 18.22Z': '83',
        'M5.81 18.23L5.81 18.23Q3.40 18.23 2.08 16.61Q0.76 14.98 0.76 11.92L0.76 11.92Q0.76 9.77 1.38 8.25Q2.00 6.73 3.18 5.93Q4.36 5.13 5.98 5.13L5.98 5.13Q7.13 5.13 8.22 5.51Q9.31 5.89 10.12 6.61L10.12 6.61L9.32 8.30Q8.44 7.60 7.62 7.28Q6.80 6.97 6.07 6.97L6.07 6.97Q4.61 6.97 3.83 8.24Q3.04 9.50 3.04 11.88L3.04 11.88L3.04 12.85L2.79 12.40Q2.95 11.63 3.44 11.06Q3.92 10.49 4.64 10.18Q5.35 9.86 6.19 9.86L6.19 9.86Q7.34 9.86 8.23 10.40Q9.11 10.93 9.61 11.85Q10.12 12.78 10.12 13.99L10.12 13.99Q10.12 15.23 9.56 16.19Q9.00 17.15 8.04 17.69Q7.07 18.23 5.81 18.23ZM5.71 16.40L5.71 16.40Q6.70 16.40 7.30 15.76Q7.90 15.12 7.90 14.06L7.90 14.06Q7.90 13.00 7.30 12.36Q6.70 11.72 5.69 11.72L5.69 11.72Q5.02 11.72 4.51 12.02Q4.00 12.31 3.71 12.84Q3.42 13.37 3.42 14.06L3.42 14.06Q3.42 14.76 3.71 15.28Q4.00 15.80 4.51 16.10Q5.02 16.40 5.71 16.40Z': '6',
        'M6.66 14.13L1.24 14.13L1.24 12.35L6.66 12.35L6.66 14.13ZM15.01 17.03L12.69 17.03L12.69 6.98L13.86 7.24L10.10 9.50L10.10 7.43L13.66 5.27L15.01 5.27L15.01 17.03ZM17.82 18.09L9.90 18.09L9.90 16.22L17.82 16.22L17.82 18.09Z': '-1',
    }
    for path, number in test_vector.items():
        assert svg_path_to_number(path) == number, f'Number expected {number} found {svg_path_to_number(path)}'


def requests_retry_session(
    retries: int=3,
    backoff_factor: float=0.3,
    status_forcelist: Tuple[int]=(500, 502, 503, 504),
    session: Union[requests.Session, None]=None,
) -> requests.Session:
    session: requests.Session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def collate_svg_paths(svg: str) -> str:
    doc = minidom.parseString(svg)

    paths: List[str] = [path.getAttribute('d')
                        for path in doc.getElementsByTagName('path')]
    doc.unlink()
    return ''.join(paths)


def pull_measurements(retries: int, timeout: int) -> Dict[str, Dict[str, str]]:
    session: requests.Session = requests_retry_session(retries=retries)
    meas: Dict[str, Dict[str, str]] = {}

    def download(url: str):
        try:
            res = session.get(url, timeout=timeout)
        except requests.exceptions.HTTPError as e:
            logging.error(f"Http failure: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection failure: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logging.error(f"Network timeout failure: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Core requests failure: {e}")
            return None

        if res.status_code < 200 or 300 <= res.status_code:
            logging.error(f'Http error: status={res.status_code}')
            return None

        return res

    for sensor, url in SENSORS.items():
        res = download(url)
        if res is None:
            logging.warning(f'Pulling measurements for sensor {sensor} failed.')
            continue

        html: str = res.text
        from lxml import etree
        parser = etree.HTMLParser()
        root = etree.fromstring(html, parser=parser)
        maybe_address: etree._Element = root.find('.//td[@class="summary__address"]')#.text.strip()
        if not hasattr(maybe_address, 'text'):
            print(f"[!] Sensor {sensor} does not seem to exist. It is missing 'summary__address' class element.")
            continue
        address: str = maybe_address.text.strip()

        m: List[etree._Element] = root.findall('.//div[@class="measurement"]')

        if len(m) == 0:
            logging.warning(f'Sensor {sensor} has no measurements.')
            continue

        #KEYS = set(('PM10', 'PM2.5', 'PM1', 'PRESSURE', 'HUMIDITY', 'TEMPERATURE', 'WIND_SPEED')) # API v1
        KEYS = set(('PM10', 'PM2.5', 'PM1')) # API v2
        measurement: etree._Element
        for measurement in m:
            name: str = measurement.find('.//h2[@class="measurement__name"]').text.strip()
            value: etree._Element = measurement.find('.//div[@class="measurement__value"]')
            path: str = value.find('.//path').attrib.get('d', '')
            if name in KEYS:
                params = meas.get(sensor, {})
                params[name.lower()] = svg_path_to_number(path)
                meas[sensor] = params
            pass
    return meas


def aqi_by_pm25(pm25: float) -> str:
    for name, d in AQI_PM25_LEVELS.items():
        if pm25 <= d['hi']:
            return name
    return 'Hazardous'


def status_post(status: str, media_ids: List[str],
        session: requests.Session, timeout: int
    ) -> Tuple[bool, Union[requests.Response, None]]:
    url: str = f'{MASTODON_HOST}/api/v1/statuses'
    data = {
        'status': status,
        'media_ids[]': media_ids,
    }
    try:
        res: requests.Response = session.post(url, timeout=timeout,
            data=data, headers=dict(Authorization=f'Bearer {MASTODON_TOKEN}'))

        if res.status_code < 200 or 300 <= res.status_code:
            logging.error(f'Http error: status={res.status_code}')
            return False, res

        return True, res
    except requests.exceptions.HTTPError as e:
        logging.error(f"Http failure: {e}")
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection failure: {e}")
    except requests.exceptions.Timeout as e:
        logging.error(f"Network timeout failure: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Core requests failure: {e}")
    return False, None


def attach_media(path: str, description: str,
        session: requests.Session, timeout: int
    ) -> Tuple[bool, Union[requests.Response, None]]:
    url: str = f'{MASTODON_HOST}/api/v1/media'
    data = {
        'description': description,
    }
    files = {
        'file': (
            os.path.basename(path),
            Path(path).open('rb'),
            'application/octet-stream'
        )
    }
    try:
        res: requests.Response = session.post(url, timeout=timeout,
            data=data, files=files, headers=dict(Authorization=f'Bearer {MASTODON_TOKEN}'))

        if res.status_code < 200 or 300 <= res.status_code:
            logging.error(f'Http error: status={res.status_code}')
            return False, res

        return True, res
    except requests.exceptions.HTTPError as e:
        logging.error(f"Http failure: {e}")
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection failure: {e}")
    except requests.exceptions.Timeout as e:
        logging.error(f"Network timeout failure: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Core requests failure: {e}")
    return False, None


def push_aqi_status(
        measurements: Dict[str, Dict[str, str]],
        former_bad_aqi: Union[bool, None],
        retries=3,
        timeout=5,
    ):
    pm25: List[float] = [float(data['pm2.5'])for _, data in measurements.items() if 'pm2.5' in data]
    logging.info(f'PM2.5 concentrations: {pm25}')
    pm25 = pm25[:3]
    if len(pm25) == 0:
        logging.error(f'Not a single one PM2.5 measurement was found retrieved data. {measurements}')
        return
    pm25_avg: float = sum(pm25) / len(pm25)
    aqi: str = aqi_by_pm25(pm25_avg)

    bad_aqi_flag: bool = aqi != 'Good'
    with open('aqi_status.txt', 'wt') as ofile:
        ofile.write(f'{aqi}')
    with open('aqi_flag.txt', 'wt') as ofile:
        ofile.write(f'{int(bad_aqi_flag)}')

    send_flag: bool = (former_bad_aqi is None) or (bad_aqi_flag) or (not bad_aqi_flag and former_bad_aqi)
    if not send_flag:
        return

    if bad_aqi_flag:
        status: str = (
            f"Kraków bad air quality alert ⚠ {aqi.upper()}\n\n"
            f"PM2.5 level is {pm25_avg:.0f} μg/m³"
        )
        if AQI_PM25_LEVELS[aqi]['regular']:
            status += f"\n\n{AQI_PM25_LEVELS[aqi]['regular']}"
        if AQI_PM25_LEVELS[aqi]['sensitive']:
            status += f"\n\n{AQI_PM25_LEVELS[aqi]['sensitive']}"
        status += "\n\n#SMOG #KRAKÓW #KrakówSmog"
        pass
    else:
        status: str = f"Kraków air quality is back to normal. 🍃\n\nPM2.5 level is {pm25_avg:.0f} μg/m³"

    session: requests.Session = requests_retry_session(retries=retries)

    ok, res = attach_media(AQI_PM25_LEVELS[aqi]['img'], aqi, session=session, timeout=timeout)
    if ok:
        media_id = res.json().get('id', '')
        logging.info(f'Attaching media_id={media_id}')
        media_ids = [media_id]
    else:
        media_ids = []
    ok, res = status_post(status, media_ids, session=session, timeout=timeout)
    if ok:
        logging.info(f'Status POST: {res.json()}')
    return


def main(
    test_chars: ("Test character recognition", "flag", "tc"),
    test_nums: ("Test number recognition", "flag", "tn"),
    report: ("Report live values", "flag", "R"),
    retries: ("Number of HTTP(s) retries.", "option", 'r', int)=5,
    timeout: ("HTTP(s) timeout, in seconds.", "option", 't', int)=5,
    former_aqi: ("Previous AQI status, False=good, True=polluted.", 'positional', None, int)=None,
    ):

    former_aqi = bool(former_aqi)
    logging.basicConfig(level=logging.INFO)

    if test_chars:
        test_character_recognition()
    elif test_nums:
        test_number_recognition()
    elif report:
        measurements = pull_measurements(retries=retries, timeout=timeout)
        sensor: str
        data: dict
        for sensor, data in measurements.items():
            print(f'{sensor}')
            name: str
            value: str
            for name, value in data.items():
                print(f' {name:>12s}{value:>8s}')
    else:
        global MASTODON_HOST
        global MASTODON_TOKEN
        MASTODON_HOST = os.environ['SERVER']
        MASTODON_TOKEN = os.environ['TOKEN']
        measurements = pull_measurements(retries=retries, timeout=timeout)
        push_aqi_status(measurements, former_bad_aqi=former_aqi,
            retries=retries, timeout=timeout)

    return os.EX_OK

if __name__ == '__main__':
    sys.exit(plac.call(main))
