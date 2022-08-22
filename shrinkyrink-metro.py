from datetime import datetime, date
import json
import requests
import re
import sys
from bs4 import BeautifulSoup as soup

class ShrinkyException(Exception): pass

def validate(_time, _date=None):
    if not re.match("^\d\d:\d\d$", _time):
        raise ShrinkyException('Time is in invalid format')

    if _date and not re.match("^\d\d.\d\d.\d\d$", _date):
        raise ShrinkyException('Date is in invalid format')


def sign_up(target_date, target_time, cookie):
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
        "os-token-id": auth['os-token-id'],
        "os-token-value": auth['os-token-value'],
        "os-user-id": auth['os-user-id'],
    }

    sessions = session.get("https://osapi.opensports.ca/app/posts/listFiltered", params={
        'limit': 48,
        'groupIDs[]': 1905,
    }, headers=auth_spread).json()

    sessions = sessions['result']
    time_parts = target_time.split(':')
    target_datetime = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        int(time_parts[0]) + 4,
        int(time_parts[1])
    )

    freestyles = []
    for _session in sessions:
        if not 'Freestyle Session' in _session['title']: continue
        start = datetime.strptime(_session['start'][:16], "%Y-%m-%dT%H:%M")

        if start != target_datetime: continue

        freestyles.append(_session)

    if not freestyles:
        raise ShrinkyException('Failed to find freestyles for time.')

    target = freestyles[0]

    going = session.get(
        "https://osapi.opensports.ca/app/posts/listMyGoing",
        headers=auth_spread
    ).json()
    existing = set(list(map(lambda v: v['id'], going['result'])))

    if target['id'] in existing:
        raise ShrinkyException('Already enrolled in session.')

    summary = target['ticketsSummary'][0]
    hold = session.post("https://osapi.opensports.ca/app/posts/insertHold",
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
                "totalPriceInCents": summary['price'] * 100,
                "postID": target['id']
            }
        )
    )

    if hold.status_code != 200:
        raise ShrinkyException('Call to hold failed')

    hold = hold.json()

    if hold['response'] != 200:
        raise ShrinkyException('Holding session failed')

    complete = session.post("https://osapi.opensports.ca/app/posts/completeHoldOrder",
        headers={
            "buildnumber": "202070",
            "content-type": "application/json",
            "source": "oswebsite",
            **auth_spread
        },
        data=json.dumps(
            {
                "orderID": hold['result']['orderID'],
                "holdExpiry": hold['result']['holdExpiry'],
                "holdKey": hold['result']['holdKey'],
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
                "postID": target['id'],
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


if __name__ == '__main__':
    args = sys.argv[1:]

    if len(args) < 3:
        print('You must provide your username, password, and desired time.')
        exit(1)

    target_date = date.today()
    cookie = args[0]
    target_time = args[1]

    if len(args) == 3:
        cookie = args[0]
        target_date = datetime.strptime(args[1], "%d.%m.%y")
        target_date = date(target_date.year, target_date.month, target_date.day)
        target_time = args[2]

    sign_up(target_date, target_time, cookie)
