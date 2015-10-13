phantom-dc-extras
=================

Background
----------
EFF's [phantom-of-the-capitol][1] project is super gnar. But we wondered: can we
make it even _more_ gnar? And if so, how gnar would that be? The answer, as it
turns out, is **totally rad-gnar.** And that's how phantom-dc-extras came about.

phantom-dc-extras automates the process of filling out Congress forms when you
might not have all the data available. Maybe you collected a petition signature
on behalf of your campaign participants, but you didn't ask the user for a phone
number, county, +4 zip extension, or name prefix (dear sir or madam). Maybe it's
a pain in the ass for people to fill in all that info. We understand. 
phantom-dc-extras takes care of it for you.

Give phantom-dc-extras a name, street address, zip code, and message and it
takes care of the rest:

1. Guesses the name prefix ("Mr." or "Ms.") based on US census data of common
   male and female names.
2. Geocodes the address / zip into a precise, predicatable format containing
   city, county, state, zip+4 extension, and latitude / longitude coordinates.
3. Looks up the senators and representatives for that address
4. Stuffs all that data (when needed) into the appropriate contact forms and
   sends out to Congress using [phantom-of-the-capitol][1]

phantom-dc-extras is built upon a Redis Queue (powered by the [Python RQ][5]
library. It will take form submissions as fast as you can send them in, and
process them as quickly as possible (which is usually much slower). It is
designed for easy deployment on Heroku, though you can run it anywhere.


Dependencies
------------
If you're using someone else's instance, skip ahead to the API section. If
you're going to deploy your own instance of phantom-dc-extras, you'll need the
following prerequisites:

- A working [phantom-of-the-capitol][1] installation (obvi's)
- Python 2.7 with pip and [Virtualenv][2]
- Redis
- PostgreSQL
- A [SmartyStreets][3] account and API key
- A [Sunlight Foundation API key][3]
- Love.


Installation
------------
1. Copy the `.env.EXAMPLE` file to a file called `.env` — it's super important
   to name it thusly because this file is in the `.gitignore` list. It will
   contain all of your most precious API keys and database passwords, so it's
   crucial to keep it out of the repository.
2. Customize the `.env` file with your actual precious API keys and db creds.
3. Create a Python virtualenv in the project root: `virtualenv venv`
4. Activate the virtualenv: `. venv/bin/activate`
5. Install Python requirements: `pip install -r requirements.txt`


Running the project
-------------------
1. Source the environment variables into memory: `source .env`
2. Run the app: `python app.py`
3. Run a worker (you'll want to use a different shell): `python worker.py`

Assuming this worked, you're now ready to submit to Congress. The app will
probably be running at localhost:9001, so if you visit
http://localhost:9001/submit you can submit a test form and watch your worker go
to town.


API
---
### `POST /congress/submit`

The `/congress/submit` endpoint sends form submissions into the queue for processing and
sending to Congress. It does only basic validation on the fields you pass in.
The ultimate success or failure of the job is logged in the database when the
worker process picks it up and tries to submit to Congress. 

**Required parameters:**

- `api_key`: Your API key for access
- `address1`: The street address (eg. "123 Main St.")
- `zip`: Five digit zip code (eg. "55419")
- `name` **_OR_** `first_name` and `last_name`: The user's name either as one string
  (we'll pull them apart on the first space) or two separate parameters for
  first/last.
- `message`: The message to send to Congress (eg. "stop wasting money kthx")

**Recommended parameters:**

- `email`: The user's email address.
- `subject`: The subject of the message
- `phone`: User's phone number
- `tag`: For your internal use. A campaign tag used to track stats for the send (eg.
  "stop-bombing-ppl").
- `uid`: For your internal use. The user ID of the user you're submitting the form on
  behalf of. Can be useful for a developer who is trying to track down where
  something broke.
- `topics`: a comma separated list of "topics", in order of preference (eg.
  "telecommunications,technology,internet"). Each congressperson has a different
  list of topics in their contact forms, so we'll try to match one of your
  topics on a form-by-form basis. In the example above, if Senator Billy doesn't
  have "telecommunications" or "technology" topics, but has an "Internet policy"
  topic, we'll match that one.

**Optional parameters:**

- `skip_senate`: (TinyInt 0|1) If specified, will skip sending to the senate.
- `skip_house`: (TinyInt 0|1) If specified, will skip sending to the house.

**Response format:**

If your submission was successful, you'll get a JSON object containing
`{"queued": { ... }}` back (where the elipsis is your data being echoed back at
you.

If a validation error occured, you'll get a JSON error object similar to this:

    {
        "code": 1,
        "error": "address1 and zip fields required."
    }


[1]: https://github.com/efforg/phantom-of-the-capitol
[2]: https://virtualenv.pypa.io/en/latest/
[3]: https://smartystreets.com/
[4]: http://sunlightfoundation.com/api/
[5]: http://python-rq.org/
