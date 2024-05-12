import os
from flask import Flask, request, jsonify
from replit import db
from groq import Groq
from datetime import datetime

# Initialize the Flask app
app = Flask(__name__)

# Initialize the Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"), )

# Set the system prompt for the LLM
system_prompt = "You are a helpful assistant."

# Initialize the database if it doesn't exist
if "minute_requests" not in db:
  db["minute_requests"] = 0

if "daily_requests" not in db:
  db["daily_requests"] = 0

if "minute_tokens" not in db:
  db["minute_tokens"] = 0

if "usage" not in db:
  db["usage"] = {}

if "current_minute" not in db:
  db["current_minute"] = ""

if "current_day" not in db:
  db["current_day"] = ""

# Rate Limits
MINUTE_REQUESTS_LIMIT = 30
DAILY_REQUESTS_LIMIT = 14400
MINUTE_TOKEN_LIMIT = 600


def check_rate_limits():

  # Record the request timestamp
  current_time = datetime.now().timestamp()

  # Get the current minute
  current_minute = current_time.strftime("%Y-%m-%d %H:%M")

  # Get the current day
  current_day = current_time.strftime("%Y-%m-%d")

  # Reset the minute tokens if the minute has changed
  if current_minute != db["current_minute"]:
    db["minute_tokens"] = 0
    db["minute_requests"] = 1
    db["current_minute"] = current_minute
  else:
    db["minute_tokens"] += 1
    db["minute_requests"] += 1

  if current_day != db["current_day"]:
    db["daily_requests"] = 1
    db["current_day"] = current_day
  else:
    db["daily_requests"] += 1

  return (db["minute_requests"] < MINUTE_REQUESTS_LIMIT
          and db["daily_requests"] < DAILY_REQUESTS_LIMIT
          and db["minute_tokens"] < MINUTE_TOKEN_LIMIT)


@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
  if not check_rate_limits():
    return jsonify({"error": "Rate limit exceeded"}), 429

  if request.method == 'OPTIONS':
    # Handle CORS preflight request
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600'
    }
    return ('', 204, headers)

  try:
    response = client.chat.completions.create(model="llama3-70b-8192",
                                              messages=[{
                                                  "role":
                                                  "system",
                                                  "content":
                                                  system_prompt
                                              }, {
                                                  "role":
                                                  "user",
                                                  "content":
                                                  request.json["data"]
                                              }],
                                              max_tokens=500,
                                              temperature=1.2)

    # Get the current date
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Initialize the current date's usage if it doesn't exist
    if current_date not in db["usage"]:
      db["usage"][current_date] = 0

    # Add the total tokens from the response to the current day's usage
    db["usage"][current_date] += response.usage.total_tokens

    # Add the total tokens from the response to the current minute's usage
    db["minute_tokens"] += response.usage.total_tokens

    for choice in response.choices:
      result += choice.message.content
    response = app.response_class(response=json.dumps({'data': result}),
                                  status=200,
                                  mimetype='application/json')

    # return result
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
  except KeyError:
    return "Something went wrong :("
  except Exception as e:
    return jsonify({"error": "Failed to process request"}), 500


@app.route('/')
def index():
  return jsonify({"error": "Try /chat."}), 403


app.run(host='0.0.0.0', port=81)
