from bs4 import BeautifulSoup as soup
from collections import namedtuple
from datetime import datetime, date, timedelta
import inquirer
from inquirer.themes import GreenPassion
import json
import re
import requests
import sys
from pytz import utc, timezone

EASTERN = timezone('US/Eastern')

from common import ShrinkyException

Session = namedtuple('Session', ['id', 'time', 'data'])

def validate(_time, _date=None):
    if not re.match("^\d\d:\d\d$", _time):
        raise ShrinkyException('Time is in invalid format')

    if _date and not re.match("^\d\d.\d\d.\d\d$", _date):
        raise ShrinkyException('Date is in invalid format')

def log_in(cookie):
    session = requests.Session()

    home = session.get("https://opensports.net/my-games", headers={
        "cookie": "oswebsite=%s" % cookie,
    }, )

    if home.status_code != 200:
        raise ShrinkyException('Failed to get home page')

    games = soup(home.text, "html.parser")

    info_tag = games.find(id="__NEXT_DATA__")

    if not info_tag:
        raise ShrinkyException('Could not find JSON info')

    info = json.loads(info_tag.contents[0])

    auth = info['props']['initialState']['auth']['user']
    auth_spread = {
        "os-token-id": str(auth['os-token-id']),
        "os-token-value": auth['os-token-value'],
        "os-user-id": str(auth['os-user-id']),
    }

    return (session, auth, auth_spread)


def build_session(data):
    time = utc.localize(datetime.strptime(data['start'][:16], "%Y-%m-%dT%H:%M"))
    return Session(data['id'], time, data)


def get_sessions(handle):
    session, auth, auth_spread = handle

    sessions = session.get("https://osapi.opensports.ca/app/posts/listFiltered", params={
        'limit': 200,
        'groupIDs[]': 1905,
    }, headers=auth_spread).json()

    sessions = sessions['result']

    freestyles = []
    for _session in sessions:
        if not 'Freestyle Session' in _session['title']: continue
        freestyles.append(build_session(_session))

    return freestyles


def get_enrolled(handle):
    session, auth, auth_spread = handle

    going = session.get(
        "https://osapi.opensports.ca/app/posts/listMyGoing",
        headers=auth_spread
    ).json()

    freestyles = []
    for _session in going['result']:
        freestyles.append(build_session(_session))

    return freestyles


def cancel(handle, target):
    session, auth, auth_spread = handle

    data = session.get(
        "https://opensports.net/api/posts/loadOne?aliasID=%s" % target.data['aliasID'],
        headers={
            "buildnumber": "202070",
            "content-type": "application/json",
            "source": "oswebsite",
            **auth_spread
        },
    )

    if data.status_code != 200:
        raise ShrinkyException('Call to hold failed')

    data = data.json()['result']

    for order in data['userOrders']:
        response = session.post("https://osapi.opensports.ca/app/posts/cancelOrder",
            headers={
                "buildnumber": "202070",
                "content-type": "application/json",
                "source": "oswebsite",
                **auth_spread
            },
            data=json.dumps(
                {
                    "orderID": order['id'],
                }
            )
        )


def sign_up(handle, target):
    data = target.data
    session, auth, auth_spread = handle

    going = session.get(
        "https://osapi.opensports.ca/app/posts/listMyGoing",
        headers=auth_spread
    ).json()

    existing = set(list(map(lambda v: v['id'], going['result'])))

    if target.id in existing:
        raise ShrinkyException('Already enrolled in session.')

    summary = data['ticketsSummary'][0]

    complete = session.post("https://osapi.opensports.ca/app/posts/insertOrder",
        headers={
            "buildnumber": "202070",
            "content-type": "application/json",
            "source": "oswebsite",
            **auth_spread
        },
        data=json.dumps(
            {
                "currency": "USD",
                "attendeeSummary": [
                    {
                        "ticketClassID": summary['id'],
                        "isFlexible": False,
                        "schemaResponse": {
                            "Do they have a lesson at this time?": "No",
                            "Who is skating? List only one skater here. Add guests to add additional skaters.": "%s %s" % (auth['firstName'], auth['lastName'])
                        },
                        "userID": int(auth['os-user-id']),
                        "userSummary": {
                            "firstName": auth['firstName'],
                            "lastName": auth['lastName'],
                            "userID": int(auth['os-user-id'])
                        }
                    }
                ],
                "totalPriceInCents": (summary['price'] * 100) / 4,
                "postID": target.id,
                "discountID": 801,
                "numOfDiscounts": 1,
                "membershipID": 3274
            }
        )
    )

    if complete.status_code != 200:
        raise ShrinkyException('Call to complete signup failed')

    complete = complete.json()

    if complete['response'] != 200:
        raise ShrinkyException('Signup failed')

CUT_TIME = timedelta(minutes = 10)


def read_template(path):
    template = []
    with open(path, 'r') as f:
        for i, row in enumerate(f.read().split('\n')):
            if i > 6 or not row: continue

            start, sessions = row.split(' ')
            start = datetime.strptime(start, '%I:%M%p')
            sessions = int(sessions)
            template.append((i, start, sessions))
    return template


def check_contiguous(sessions):
    is_contiguous = True
    for first, second in zip(sessions, sessions[1:]):
        first_end = (first.time + timedelta(minutes = 30))
        second_start = second.time
        difference = second_start - first_end

        if difference > CUT_TIME:
            is_contiguous = False
            break

    return is_contiguous


if __name__ == '__main__':
    args = sys.argv[1:]

    cookie = args[0]
    template  = None

    if len(args) == 2:
        template = read_template(args[0])
        cookie = args[1]
    elif len(args) != 1:
        print('You must provide a cookie.')
        exit(1)

    handle = log_in(cookie)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = today.astimezone(utc)

    days = list(map(lambda i: today + timedelta(days = i), list(range(0, 7))))

    sessions = get_sessions(handle)

    if template:
        enrolled_sessions = get_enrolled(handle)
        enrolled_set = set(list(map(lambda v: v.id, enrolled_sessions)))
        lookup = { x[0]: (x[1], x[2]) for x in template }

        chosen_set = set()

        for day in days:
            if day.weekday() not in lookup: continue

            start, num_sessions = lookup[day.weekday()]
            start_time = day + timedelta(hours=start.hour, minutes=start.minute)

            day_end = day + timedelta(days = 1)
            day_sessions = list(filter(lambda v: v.time > day and v.time < day_end, sessions))
            day_sessions = sorted(day_sessions, key=lambda v: v.time)

            for i, session in enumerate(day_sessions):
                if session.time != start_time: continue

                choices = day_sessions[i:i+num_sessions]
                is_contiguous = check_contiguous(choices)

                if len(choices) < num_sessions or not is_contiguous:
                    print(f"Failed to find compatible session for {day.weekday()}")
                    continue

                for choice in choices: chosen_set.add(choice.id)


        for session in sessions:
            if session.id in enrolled_set:
                if session.id not in chosen_set:
                    cancel(handle, session)
                continue

            if session.id in chosen_set:
                sign_up(handle, session)

        exit(0)

    while True:
        enrolled_sessions = get_enrolled(handle)
        enrolled_set = set(list(map(lambda v: v.id, enrolled_sessions)))

        day_choices = []
        for day in days:
            day_end = day + timedelta(days = 1)

            day_sessions = list(filter(lambda v: v.time > day and v.time < day_end, sessions))
            day_sessions = list(map(lambda v: (v, v.id in enrolled_set), day_sessions))
            day_sessions = sorted(day_sessions, key=lambda v: v[0].time)

            data = (day, day_sessions)
            day_title = "{} ({}/{})".format(
                day.strftime("%m/%d/%y %A"),
                len(list(filter(lambda v: v[1], day_sessions))),
                len(day_sessions)
            )

            day_choices.append(
                (
                    day_title,
                    data
                )
            )

        day, day_sessions = inquirer.list_input(
            "Choose a day",
            choices=day_choices
        )

        # Find all training sessions in the day, defined as contiguous periods
        # of 1.5h or 2h
        training_choices = []

        for start, session_pair in enumerate(day_sessions):
            session, enrolled = session_pair

            for end in range(start + 2, start + 5):
                training_sessions = day_sessions[start:end]

                if len(training_sessions) != (end - start): continue

                cuts = []

                # Training sessions need to be contiguous
                is_contiguous = True
                for first, second in zip(training_sessions, training_sessions[1:]):
                    first_end = (first[0].time + timedelta(minutes = 30))
                    second_start = second[0].time
                    difference = second_start - first_end

                    if difference == CUT_TIME:
                        cuts.append(
                            "{}-{}".format(
                                first_end.astimezone(EASTERN).strftime("%I:%M%p"),
                                second_start.astimezone(EASTERN).strftime("%I:%M%p"),
                            )
                        )

                    if difference > CUT_TIME:
                        is_contiguous = False
                        break

                if not is_contiguous: continue

                # Format title
                training_title = "{}-{} ({}) {} {}".format(
                    training_sessions[0][0].time.astimezone(EASTERN).strftime("%I:%M%p"),
                    (training_sessions[-1][0].time.astimezone(EASTERN) + timedelta(minutes = 30)).strftime("%I:%M%p"),
                    len(training_sessions),
                    "".join(list(map(lambda v: '|' if v[1] else '.', training_sessions))),
                    ', '.join(cuts) if cuts else ''
                )
                training_choices.append(
                    (training_title, training_sessions)
                )

        training_choices = sorted(training_choices, key=lambda v: v[1][0][0].time - timedelta(days=len(v[1])))

        training_choices = [
            ('Cancel all', [])
        ] + training_choices

        training_sessions = inquirer.list_input(
            "Choose a training session",
            choices=training_choices
        )

        chosen_set = set(list(map(lambda v: v[0].id, training_sessions)))

        for session, _ in day_sessions:
            if (
                session.id in enrolled_set and
                session.id not in chosen_set
            ):
                cancel(handle, session)

        for session, enrolled in training_sessions:
            if enrolled: continue
            sign_up(handle, session)
