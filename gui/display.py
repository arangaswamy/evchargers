from __future__ import print_function
from __future__ import division

import logging
import loggly.handlers
import anyconfig


credentials = anyconfig.load("private_config.json")['credentials']



logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
loggly_handler = loggly.handlers.HTTPSHandler(url="{}{}".format(credentials["Loggly"]["url"],"gui"))
loggly_handler.setLevel(logging.DEBUG)
logger.addHandler(loggly_handler)
logging.getLogger("newrelic").setLevel(logging.INFO)
logging.getLogger("anyconfig").setLevel(logging.INFO)
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.INFO)


from flask import Flask, render_template, jsonify, request
from flask.ext.cache import Cache
import redis

import os

import json
import datetime
import time
from pprint import pprint
from datetime import timedelta
from babel.dates import format_timedelta
import newrelic.agent




newrelic.agent.initialize('newrelic.ini')
garage_data = anyconfig.load("private_config.json")['garage_data']

r = redis.Redis(
    host=credentials['Redis']['server'],
    db=credentials['Redis']['database'],
    password=credentials['Redis']['password'],
    port=credentials['Redis']['port']
)

app = Flask(__name__)
app.debug = False




cache = Cache(app, config={'CACHE_TYPE': 'simple'})

def find_avail(garage_name):
    current = hget("current", "data")
    return [station for station in current[garage_name]['stations'] if current[garage_name]['stations'][station] > 0]

def find_count(garage_name):
    current = hget("current", "data")
    total = 0
    for station in current[garage_name]['stations']:
        total += current[garage_name]['stations'][station]
    return total

def garages_for_company(company):
    garages = []
    current = hget("current", "data")
    for garage_name,garage_info in current.iteritems():
        if garage_info['company'] == company:
            garages.append(garage_name)
    return garages


def sites_for_garage(garage):
    return hget("current", "data")[garage]['stations']



@cache.memoize(300)
def hget(which,key):
    return json.loads(r.hget(which, key))

@app.route("/get_all_garage_data")
def get_all():
    return jsonify(
        data=hget("current", "data")
    )

@app.route("/garage/<garage>/avail_stations")
def garage_avail(garage,use_json=True):
    if use_json:
        return jsonify(
            data=find_avail(garage)
        )
    else:
        return find_avail(garage)

@app.route("/garage/<garage>/avail_count")
def garage_count(garage):
    return jsonify(
        data=find_count(garage)
    )

@app.route("/garage")
def list_garage(use_json=True):
    if use_json:
        return jsonify(
            data=hget("current","data").keys()
        )
    else:
        return hget("current", "data").keys()


@cache.cached(timeout=300)
@app.route("/")
def index():
    delta_val = int(hget("current", "timestamp")) - time.time()
    delta = timedelta(seconds=delta_val)
    how_old = format_timedelta(delta, add_direction=True)

    avails = {}
    for garage_name in list_garage(use_json=False):
        avails[garage_name] = garage_avail(garage_name, use_json=False)

    return render_template(
        "index.html",
        data=hget("current", "data"),
        available=avails,
        time=how_old
    )

@app.route("/garage/<garage_name>")
def garage(garage_name):
    delta_val = int(hget("current", "timestamp")) - time.time()
    delta = timedelta(seconds=delta_val)
    how_old = format_timedelta(delta, add_direction=True)

    avails = {}
    avails[garage_name] = garage_avail(garage_name, use_json=False)

    return render_template(
        "index.html",
        data={garage_name: hget("current", "data")[garage_name]},
        available=avails,
        time=how_old
    )


@app.route("/company/<company_name>")
def company(company_name):

    delta_val = int(hget("current", "timestamp")) - time.time()
    delta = timedelta(seconds=delta_val)
    how_old = format_timedelta(delta, add_direction=True)

    avails = {}
    data = {}
    garage_names = garages_for_company(company_name)
    for garage_name in garage_names:
        avails[garage_name] = garage_avail(garage_name, use_json=False)
        data[garage_name] = hget("current", "data")[garage_name]

    return render_template(
        "index.html",
        data=data,
        available=avails,
        time=how_old

    )


if __name__ == "__main__":
    port = int(os.getenv('PORT', '5000'))
    logging.info("Running on port {}".format(port))
    app.run(host='0.0.0.0', port=port)
