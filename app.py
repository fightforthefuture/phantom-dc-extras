# handle imports
import os, time

from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash, jsonify, Response
from rq import Connection, Queue
from redis import Redis
from access_control_decorator import crossdomain
from models import db

# define flask application
app = Flask(__name__)
app.config.from_object(__name__)
app.config.update(
    JSON_AS_ASCII=False,
    DEBUG=True if os.environ.get('DEBUG') else False,
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    SQLALCHEMY_POOL_RECYCLE = 60 * 60,
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL').strip()
)
db.init_app(app)

from models.log import Log
from models.send_record import SendRecord

with app.app_context():
    db.create_all()

# set up redis queue
redis_url = os.environ.get('REDISTOGO_URL')
redis_conn = Redis.from_url(redis_url)
q = Queue(connection=redis_conn)

# these are endpoints that don't require authorization
public_endpoints = [
    '/',
]

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    # correct_username = os.environ.get('HTTP_AUTH_USERNAME')
    # correct_password = os.environ.get('HTTP_AUTH_PASSWORD')

    # return username == correct_username and password == correct_password

def before_first(*args, **kwargs):
    """Before running anything, check that the user is supposed to be here"""

    # entry_key = os.environ.get('AUTH_OVERRIDE_KEY')

    # if request.path in public_endpoints:
    #     return None

    # if request.values.get("key") == entry_key:
    #     return None

    # auth = request.authorization
    # if not auth or not check_auth(auth.username, auth.password):
    #     return Response(
    #         'Could not verify your access level for that URL.\n'
    #         'You have to login with proper credentials', 401,
    #         {'WWW-Authenticate': 'Basic realm="Login Required"'})
    
    return None

def fix_ip(ip_address):
    """Fixes an ugly, broken IP address string that came from Heroku"""

    if "," in ip_address:
        ips = ip_address.split(", ")
        ip_address = ips[0]

    return ip_address

# check authorization at the beginning of each request
app.before_request(before_first)

@app.route('/')
def index():
    """A bogus placeholder API call that does nothing."""

    return jsonify({'lol': True})

@app.route('/debug/find_fields')
def find_fields():
    """Looks over all contact-congress yaml files for common fields lol"""

    import yaml

    path = '../contact-congress/members'

    dir = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path,f))]

    i = 0

    fields = {}

    for f in dir:
        if f[-4:] != "yaml":
            continue
        
        stream = open(os.path.join(path,f), "r")
        form = yaml.load(stream)

        if form['contact_form']:
            for instruction in form['contact_form']['steps']:
                for step in instruction:
                    if step != 'fill_in' and step != 'select' \
                            and step != 'check' and step != 'uncheck':
                        continue

                    for field in instruction[step]:

                        if 'value' not in field or not \
                                isinstance(field['value'], basestring):
                            continue

                        if field['value'] == '$ADDRESS_STATE_FULL':
                            print form['bioguide'] + ' has full address requirement'

                        #  print '%s %s ' % (form['bioguide'], field['value'])

                        if field['value'] not in fields:
                            fields[field['value']] = 0

                        if 'required' in field and field['required']:
                            fields[field['value']] += 1

    print fields

    for k, v in fields.items():
        if v == 0:
            del fields[k]

    return jsonify({
        'a note': ('The number next to these fields indicates the number of '
                   'forms that require them lol'),
        'fields': fields
    })

@app.route('/debug/get_form/<bioguide>')
def get_form(bioguide):
    """Gets the contents of the form for a bioguide"""

    import json
    import requests

    url = os.environ.get('PHANTOM_DC_URL').strip()+'/retrieve-form-elements'
    data = json.dumps({'bio_ids': [bioguide]})
    headers = {'content-type': 'application/json'}

    print data

    response = requests.post(url, data=data, headers=headers)
    print response.text
    # response = 'billy'

    return jsonify({'lol': response.text})

@app.route('/submit', methods=['GET', 'POST'])
@crossdomain(origin='*')
def submit():
    """Sends Congress form data into our form stuffer shim process."""

    ip = fix_ip(request.headers.get('x-forwarded-for', request.remote_addr))
    v = request.values.get

    if request.method == 'POST':

        if not v('address1') or not v('zip'):
            return jsonify({
                'code': 1,
                'error': 'address1 and zip fields required.'
            }), 400

        if not v('name') and not v('last_name'):
            return jsonify({
                'code': 2,
                'error': 'missing name or first_name / last_name fields.'
            }), 400

        if not v('message'):
            return jsonify({
                'code': 3,
                'error': ('missing message field. you\'re contacting congress. '
                          'make an effort.')
            }), 400

        data = {
            'first_name':   v('first_name', None),     # optional
            'last_name':    v('last_name', None),      # optional
            'name':         v('name', None),
            'address1':     v('address1', None),
            'city':         v('city', None),
            'state':        v('state', None),
            'zip':          v('zip', None),
            'zip_4':        v('zip_4', None),
            'email':        v('email', None),
            'country':      v('country', None),
            'phone':        v('phone', None),
            'subject':      v('subject', None),
            'message':      v('message', None),
            'tag':          v('tag', None),
            'topics':       v('topics', None),
            'uid':          v('uid', None),
            'skip_senate':  v('skip_senate', 0)
        }
        from jobs.submit import main_data_task

        job = q.enqueue_call(
            func=main_data_task,
            args=(data,),
            timeout=3600) 

        return jsonify({'queued': data})
    else:
        return render_template('submit.html');


if __name__ == '__main__':
    if app.config['DEBUG'] == True:
        print 'Debug mode active'
        app.run('0.0.0.0', 9002)
    else:
        app.run()