from datetime import datetime, date
from flask import Flask
from shrinkyrink import sign_up, validate, ShrinkyException

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
