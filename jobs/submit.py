import os
from models.log import Log
from models.send_record import SendRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(os.environ.get('DATABASE_URL').strip())
Session = sessionmaker(bind=engine)
session = Session()

default_email       = 'team@fightforthefuture.org'
default_phone       = '6125551212'
default_subject     = 'Message from a citizen'
default_county      = 'Nullsville'

states = {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming'
}

def main_data_task(data):
    """Pulls records from battleforthenet and queues push jobs to Platform DB"""

    from library.GenderLookup import GenderLookup
    import requests
    import json

    gender_looker_upper = GenderLookup()

    print data

    prefix = None
    name = None 
    lat = None
    lng = None
    first_name = data.get('first_name', None)
    last_name  = data.get('last_name', None)
    address1   = data.get('address1', None)    # overridden by smarty streets
    city       = data.get('city', None)        # overridden by smarty streets
    state      = data.get('state', None)       # overridden by smarty streets
    state_full = None                          # filled in later
    zip        = data.get('zip', None)         # overridden by smarty streets
    zip4       = data.get('zip4', None)        # overridden by smarty streets
    topics     = data.get('topics', 'no topic').split(',')
    email      = data.get('email', default_email)
    county     = default_county
    subject    = data.get('subject') if data.get('subject') else default_subject
    message    = data.get('message')
    phone      = data.get('phone') if data.get('phone') else default_phone
    tag        = data.get('tag')
    uid        = data.get('uid', None)

    # if name supplied in one field, massage it into two parts (first / last)
    if data.get('name'):
        split_name = data.get('name', '').split(' ', 1)
        first_name = split_name[0]
        if len(split_name) == 2:
            last_name = split_name[1]

    # Guess name prefix by first name (sir/madam)
    prefix = gender_looker_upper.getPrefix(first_name)

    # look up detailed address info from SmartyStreets
    out('Querying SmartyStreets for %s, %s' % (address1, zip))
    smartystreets_url = 'https://api.smartystreets.com/street-address'
    query = {
        'street': address1,
        'zipcode': zip,
        'auth-id': os.environ.get('SMARTYSTREETS_AUTH_ID').strip(),
        'auth-token': os.environ.get('SMARTYSTREETS_TOKEN').strip()
    }

    r = requests.get(smartystreets_url, params=query)
    smarty = json.loads(r.text)

    if smarty:
        address1 = smarty[0]['delivery_line_1']

        if 'components' in smarty[0]:

            if 'city_name' in smarty[0]['components']:
                city = smarty[0]['components']['city_name']

            if 'state_abbreviation' in smarty[0]['components']:
                state = smarty[0]['components']['state_abbreviation']

            if 'zipcode' in smarty[0]['components']:
                zip = smarty[0]['components']['zipcode']

            if 'plus4_code' in smarty[0]['components']:
                zip4 = smarty[0]['components']['plus4_code']
            else:
                zip4 = '1234' # lol

        if 'metadata' in smarty[0]:

            if 'latitude' in smarty[0]['metadata']:
                lat = smarty[0]['metadata']['latitude']

            if 'longitude' in smarty[0]['metadata']:
                lng = smarty[0]['metadata']['longitude']

            if 'county_name' in smarty[0]['metadata']:
                county = smarty[0]['metadata']['county_name']
    else:
        out('Smarty FAIL. %s' % r.text)
        return log('bad_address', r.text, data)

    # massage data
    if state and states.get(state):
        state_full = states[state]

    # look up congress people from Sunlight API lol
    out('Querying sunlight for lat: %s / long: %s' % (lat, lng))
    sun_url = 'https://congress.api.sunlightfoundation.com/legislators/locate'
    sun_key = os.environ.get('SUNLIGHT_API_KEY').strip()

    if lat and lng:
        query = {'latitude': lat, 'longitude': lng, 'apikey': sun_key}
    else:
        query = {'zip': zip, 'apikey': sun_key}
        log('sunlight_zip_query', r.text, data)

    r2 = requests.get(sun_url, params=query)
    sunlight = json.loads(r2.text)

    if not sunlight or not 'results' in sunlight:
        out('Sunlight FAIL. %s' % r2.text)
        return log('sunlight_fail', r2.text, data)

    bioguides = []
    recipients = {}

    for result in sunlight['results']:
        bioguides.append(result['bioguide_id'])
        recipients[result['bioguide_id']] = result

        if 'nickname' in result and result['nickname']:
            name = result['nickname']+' '+result['last_name']
        else:
            name = result['first_name']+' '+result['last_name']

        recipients[result['bioguide_id']]['name'] = name

    # Get the form fields for these congresspeople from congress-forms server
    out('Querying congress-forms server for %s' % json.dumps(bioguides))
    url = os.environ.get('CONGRESS_FORMS_URL').strip()+'/retrieve-form-elements'
    data = json.dumps({'bio_ids': bioguides})
    headers = {'content-type': 'application/json'}
    r3 = requests.post(url, data=data, headers=headers)

    forms = json.loads(r3.text)

    if not forms:
        out('congress-forms FAIL. %s' % r3.text)
        return log('congresss_forms_read_fail', r3.text, data)

    # fill out and submit the forms lol
    for bioguide in forms:
        form = forms[bioguide]
        fields = {}

        out("FILLING IN FORM %s" % bioguide)

        for action in form['required_actions']:
            val = action['value']

            if val == '$NAME_PREFIX':
                fields[val] = fill_basic_field(prefix, action)
            elif val == '$NAME_FIRST':
                fields[val] = fill_basic_field(first_name, action)
            elif val == '$NAME_LAST':
                fields[val] = fill_basic_field(last_name, action)
            elif val == '$NAME_FULL':
                fields[val] = fill_basic_field(first_name+' '+last_name,action)
            elif val == '$ADDRESS_STREET':
                fields[val] = fill_basic_field(address1, action)
            elif val == '$ADDRESS_CITY':
                fields[val] = fill_basic_field(city, action)
            elif val == '$ADDRESS_STATE_POSTAL_ABBREV':
                fields[val] = fill_basic_field(state, action)
            elif val == '$ADDRESS_STATE_FULL':
                fields[val] = fill_basic_field(state_full, action)
            elif val == '$ADDRESS_COUNTY':
                fields[val] = fill_basic_field(county, action)
            elif val == '$ADDRESS_ZIP5':
                fields[val] = fill_basic_field(zip, action)
            elif val == '$ADDRESS_ZIP4':
                fields[val] = fill_basic_field(zip4, action)
            elif val == '$ADDRESS_ZIP_PLUS_4':
                fields[val] = fill_basic_field(zip + '-' + zip4, action)
            elif val == '$PHONE':
                fields[val] = fill_basic_field(format_phone(phone), action)
            elif val == '$PHONE_PARENTHESIS':
                fields[val] = fill_basic_field(format_phone(phone,True),action)
            elif val == '$EMAIL':
                fields[val] = fill_basic_field(email, action)
            elif val == '$TOPIC':
                fields[val] = fill_basic_field(topics, action)
            elif val == '$SUBJECT':
                fields[val] = fill_basic_field(subject, action)
            elif val == '$MESSAGE':
                fields[val] = fill_basic_field(message, action)
            elif val == '$CAMPAIGN_UUID':
                fields[val] = fill_basic_field(tag, action)

        fields['$CAMPAIGN_UUID'] = tag

        out('SENDING congress-forms SUBMISSION TO %s' % bioguide)
        url = os.environ.get('CONGRESS_FORMS_URL').strip()+'/fill-out-form'
        data = json.dumps({'bio_id': bioguide, 'fields': fields})
        headers = {'content-type': 'application/json'}
        r4 = requests.post(url, data=data, headers=headers)

        form_result = json.loads(r4.text)

        if not form_result:
            out('congress-forms UNKNOWN FAIL. %s' % r4.text)
            log('congresss_forms_unknown_fail', r4.text, data, None, bioguide, \
                  recipients[bioguide]['chamber'], recipients[bioguide]['name'])

        elif form_result['status'] == 'error':
            cf_uid = None if not 'uid' in form_result else form_result['uid']
            out('congress-forms FAILED TO FILL OUT FORM. %s' % r4.text)
            out('-------------------------------------------------------------')
            out('-------------------------------------------------------------')
            out('-------------------------------------------------------------')
            log('congresss_forms_write_fail', r4.text, data, cf_uid, bioguide, \
                  recipients[bioguide]['chamber'], recipients[bioguide]['name'])

        elif form_result['status'] == 'success':
            out('congress-forms success!')
            data = {
                'source_uid':       uid,
                'campaign':         tag,
                'bioguide_id':      bioguide,
                'chamber':          recipients[bioguide]['chamber'],
                'recipient_name':   recipients[bioguide]['name']
            }
            record = SendRecord(**data)
            session.add(record)
            session.commit()

    return True

def format_phone(phone, ugly=False):
    phone = phone.replace(' ', '').replace('(', '').replace(')', '')
    phone = phone.replace('-', '').replace('+', '')[:10]

    if not ugly:
        return phone[:3] + "-" + phone[3:6] + "-" + phone[6:10]
    else:
        return "(" + phone[:3] + ") " + phone[3:6] + "-" + phone[6:10]


def fill_basic_field(val, action):
    """Fills out a standard form field on one of the congress-forms"""

    # If there's not a pre-defined list of drop-down options, then this is easy.
    if action['options_hash'] == None:

        out("    Filling in %s: %s" % (action['value'], val))

        val = val if action['maxlength'] == None else val[:action['maxlength']]
        return val

    # Okay, there's a dropdown, dammit. We'll have to pick the closest match.
    else:
        # JL HACK ~ 
        if action['options_hash'] == 'US_STATES_AND_TERRITORIES':
            out("    Filling in %s: %s (~ JL HACK ~)" % (action['value'], val))
            return val

        # Make sure our value is a list, if it isn't. For later consistency.
        if not isinstance(val, list):
            val = [val]

        imperfect_match = None
        first = None

        out("    Trying to find a match for list %s" % action['value'])

        for key in action['options_hash']:
            list_key = key.strip().lower()
            for check_val in val:
                user_key = check_val.strip().lower()

                if user_key == list_key:
                    out("        PERFECT MATCH: %s == %s" % (key, check_val))

                    if isinstance(action['options_hash'], list):
                        out("        list val: %s" % key)
                        return key
                    elif isinstance(action['options_hash'], dict):
                        out("        dict val: %s" %action['options_hash'][key])
                        return action['options_hash'][key]

                if user_key in list_key and not imperfect_match:
                    out("        IMPERFECT MATCH: %s in %s" % (key, check_val))

                    if isinstance(action['options_hash'], list):
                        imperfect_match = key;
                    elif isinstance(action['options_hash'], dict):
                        imperfect_match = action['options_hash'][key]

                if not first:
                    if isinstance(action['options_hash'], list):
                        first = key;
                    elif isinstance(action['options_hash'], dict):
                        first = action['options_hash'][key]

        if imperfect_match:
            out("            returning imperfect_match: %s" % imperfect_match)
            return imperfect_match

        out("        No good values found for %s. FIRST!" % action['value'])
        return first

def out(string):
    print string

def log(log_type, log, input_data, uid=None, bioguide_id=None, chamber=None, \
        recipient_name=None):
    import json
    data = {
        'log_type':         log_type,
        'log':              log,
        'input_data':       json.dumps(input_data),
        'uid':              uid,
        'bioguide_id':      bioguide_id,
        'chamber':          chamber,
        'recipient_name':   recipient_name
    }
    log = Log(**data)
    session.add(log)
    session.commit()
    return data


class JobFailedException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)