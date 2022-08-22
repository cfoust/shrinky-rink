from datetime import datetime, date
from flask import Flask, request
from common import ShrinkyException
from shrinkyrink import sign_up, validate
from shrinkyrink_metro import sign_up as metro_sign_up

app = Flask(__name__)

@app.route("/today/<username>/<password>/<_time>")
def handle_today(username, password, _time):
    try:
        validate(_time)
        sign_up(date.today(), _time, username, password)
    except ShrinkyException as e:
        return "An error occurred: %s" % str(e), 400

    return "OK"

@app.route("/date/<username>/<password>/<_date>/<_time>")
def handle_date(username, password, _date, _time):
    try:
        validate(_time, _date)

        parsed = datetime.strptime(_date, "%d.%m.%y")

        sign_up(date(parsed.year, parsed.month, parsed.day), _time, username, password)
    except ShrinkyException as e:
        return "An error occurred: %s" % str(e), 400

    return "OK"


def handle_metro(_date, _time, _cookie):
    validate(_time, _date)

    parsed = datetime.strptime(_date, "%d.%m.%y")

    metro_sign_up(date(parsed.year, parsed.month, parsed.day), _time, _cookie)

@app.route("/metro/today/<_time>")
def handle_metro_today(_time):
    _cookie = request.args.get('cookie')

    if not _cookie:
        return "No cookie present", 400

    _date = date.today()

    try:
        if ',' in _time:
            for _target in _time.split(','):
                validate(_target)
                metro_sign_up(_date, _target, _cookie)
        else:
            validate(_time)
            metro_sign_up(_date, _time, _cookie)
    except ShrinkyException as e:
        return "An error occurred: %s" % str(e), 400

    return "OK"

@app.route("/metro/date/<_date>/<_time>")
def handle_metro_date(_date, _time):
    _cookie = request.args.get('cookie')

    if not _cookie:
        return "No cookie present", 400

    try:
        if ',' in _time:
            for _target in _time.split(','):
                handle_metro(_date, _target, _cookie)
        else:
            handle_metro(_date, _time, _cookie)
    except ShrinkyException as e:
        return "An error occurred: %s" % str(e), 400

    return "OK"

