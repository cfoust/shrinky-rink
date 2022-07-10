from datetime import datetime, date
import json
import requests
import re
import sys

class ShrinkyException(Exception): pass

def validate(_time, _date=None):
    if not re.match("^\d\d:\d\d$", _time):
        raise ShrinkyException('Time is in invalid format')

    if _date and not re.match("^\d\d.\d\d.\d\d$", _date):
        raise ShrinkyException('Date is in invalid format')


def sign_up(target_date, target_time, username, password):
    session = requests.Session()

    directory = session.post("https://skatebowl.com/sysapi/public?sandboxKey=undefined", data="{\"siteID\":\"skatebowl\"}", headers={
      "referrer": "https://skatebowl.com/",
    });

    directory = directory.json()

    login = session.post("https://skatebowl.com/auth/authorization?sandboxKey=sbx~00~300", data=json.dumps({
        "username": username,
        "password": password,
        "siteID": "skatebowl",
        "navKey": directory['scopeNavKey'],
    }))

    if login.status_code != 200:
        raise ShrinkyException('Failed to log in')

    auth = login.json()

    auth_header = "Bearer %s" % auth['authToken']
    auth_headers = {
        "Authorization": auth_header
    }

    members = session.get("https://skatebowl.com/sandboxes/sbx~00~300/account/pac~00~BQoAAAAAAAA~XwM/members", headers=auth_headers).json()

    client = session.get("https://skatebowl.com/accounting/sandboxes/sbx~00~300/client/pac~00~BQoAAAAAAAA~XwM/billing?openTrxOnly=true&excludeVoidTrx=true", headers=auth_headers).json()

    account_key = client['client']['ownerAccountMemberKey']

    sessions = session.post("https://skatebowl.com/signup/sandboxes/sbx~00~300/choicesForParticipant/biz~00~CQcAAAAAAAA~YAQ/pam~00~BQoAAAAAAAA~YAM", data=json.dumps({
        "choiceFetchedRels": ["course","location"],
        "currentChoiceSelections": [],
        "includeCurrent": True,
        "participant": auth['environmentInfo']['userProxy'],
        "lightweightObjects": True
    }), headers=auth_headers).json()

    freestyles = list(filter(lambda a: 'Freestyle Session' in a['choice']['name'] and a['meetingStartTime'] == target_time, sessions))

    if not freestyles:
        raise ShrinkyException('Failed to find freestyles for time.')

    target = None
    target_meeting = None
    for _class in freestyles:
        for _id, _date in _class['meetingDates'].items():
            # Can't use strptime
            parts = list(map(int, _date.split('/')))
            if date(parts[2], parts[0], parts[1]) != target_date:
                continue

            target = _class
            target_meeting = _id
            break

        if target: break

    if not target:
        raise ShrinkyException('Failed to find suitable freestyle.')

    # Make sure we're not already enrolled
    enrollments = session.get("https://skatebowl.com/signup/sandboxes/sbx~00~300/userChoices/biz~00~CQcAAAAAAAA~YAQ", headers=auth_headers).json()['enrolledChoices'][account_key]
    for _class in enrollments:
        data = _class['enrollment']
        if (
            data['classKey'] == target['choice']['objKey'] and
            target_meeting in data['classMeetingKeys']
        ):
            raise ShrinkyException('Already enrolled in session.')

    # Initiate the transaction
    transaction_id = session.get('https://skatebowl.com/sysapi/transaction?sandboxKey=sbx~00~300', headers=auth_headers).json()

    client_key = auth['environmentInfo']['userProxy']['clientAccountKey']

    billing_info = session.get(
        "https://skatebowl.com/payments/sandboxes/sbx~00~300/nmiBillingEntries/Business/biz~00~CQcAAAAAAAA~YAQ/ClientAccount/%s" % client_key,
        headers=auth_headers
    )

    billing_info = billing_info.json()[0]
    billing_id = billing_info["id"]

    simple_billing_info = {
        "firstName": billing_info["firstName"],
        "lastName": billing_info["lastName"],
        "company":"",
        "streetAddress": billing_info["address1"],
        "extendedAddress":"",
        "locality": billing_info["city"],
        "region": billing_info["state"],
        "postalCode": billing_info["postalCode"],
        "country":""
    }

    for member in members:
        if member['type'] != 'Owner':
            member['selections'] = []
            continue

        member['selections'] = [
            {
                "classKey": target['choice']['objKey'],
                "costPerMeeting": 21,
                "dropin": True,
                "installmentPlan": False,
                "meetingKeys": [target_meeting],
                "prepaid": False,
                "selectionType": "Class",
                "waitlist": False,
            }
        ]

    pricing = session.post(
        "https://skatebowl.com/signup/sandboxes/sbx~00~300/pricing",
        headers=auth_headers,
        data=json.dumps({
            "addOnProducts": [],
            "businessKey": "biz~00~CQcAAAAAAAA~YAQ",
            "clientAccountKey": client_key,
            "notificationTemplateKey": "",
            "participants": members,
            "roleKeys": auth['user']['roleKeys'],
            "transactionId": transaction_id,
            "trxRequestPayments": None,
            "userAccount": client['client'],
            "userProxy": auth['environmentInfo']['userProxy'],
        })
    ).json()

    grand_total = pricing['grandTotal']
    print('cost', grand_total)
    transaction = session.post(
        "https://skatebowl.com/payments/sandboxes/:sandboxKey/nmiInitiateSale/Business/biz~00~CQcAAAAAAAA~YAQ?billingId=%s&payerKey=%s&payerType=ClientAccount&amount=%d&sandboxKey=sbx~00~300" % (billing_id, client_key, grand_total),
        headers=auth_headers,
        data=json.dumps(simple_billing_info)
    )

    transaction = transaction.json()

    form_url = transaction['gatewayResponse']['formUrl']
    nmi = session.get(form_url)
    token = form_url.split('/')[-1]

    if nmi.status_code != 302 and nmi.status_code != 200:
        print(nmi, nmi.status_code, nmi.text)
        raise ShrinkyException('Call to payment processor failed')

    preauth = {
        "paymentGateway": "nmi",
        "paymentMethod": "creditCardOrOther",
        "tokenId": token,
        "totalAmount": grand_total,
        "userBillingInfo": simple_billing_info,
        "waiveFee": False,
    }
    enroll = session.post(
        "https://skatebowl.com/signup/sandboxes/sbx~00~300/enroll",
        headers=auth_headers,
        data=json.dumps({
            "addOnProducts": [],
            "businessKey": "biz~00~CQcAAAAAAAA~YAQ",
            "clientAccountKey": client_key,
            "notificationStyle": None,
            "notificationTemplateKey": "",
            "participants": members,
            "preAuthResult": preauth,
            "roleKeys": auth['user']['roleKeys'],
            "transactionId": transaction_id,
            "trxRequestPayments": [
                {
                    "amount": grand_total,
                    "gatewayBillingInfo": simple_billing_info,
                    "gatewayEmailAddress": client['client']['emailDep'],
                    "gatewayPreauthResult": preauth,
                    "paymentId": "gateway",
                    "paymentMethodDetails": "",
                    "prepaidFundKey": "",
                }
            ],
            "userAccount": client['client'],
            "userProxy": auth['environmentInfo']['userProxy'],
        })
    )

if __name__ == '__main__':
    args = sys.argv[1:]

    if len(args) != 3:
        print('You must provide your username, password, and desired time.')
        exit(1)

    target_date = date.today()
    username = sys.argv[0]
    password = sys.argv[1]
    target_time = sys.argv[2]
    sign_up(target_date, target_time, username, password)
