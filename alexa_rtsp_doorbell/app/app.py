#!/usr/bin/env python3
import logging
from flask import Flask, request, jsonify
import alexa_smart_home_skill as alexa_smart_home_skill
import os
import json

from homeassistant_ws import HomeAssistantReconnectingClient

OPTIONS_FILENAME = '/data/options.json'
ROUTE_PREFIX = '/api/alexa_rtsp_doorbell'

options = {}
if os.path.exists(OPTIONS_FILENAME):
    with open(OPTIONS_FILENAME) as options_json_file:
        options = json.load(options_json_file)

logging_level = options.get('log_level', 'INFO')
debug = logging_level == 'DEBUG'
debuger_enabled = options.get('debugger', False)


logging.basicConfig(
    format='%(asctime)s [%(levelname)-8s] %(message)s',
    level=logging_level,
    datefmt='%Y-%m-%d %H:%M:%S.%s')

logger = logging.getLogger(__name__)
logger.setLevel(logging_level)

logger.debug(f"options: {options}")

API_PASSWORD = options.get('api_password', '')
API_KEY_HEADER = 'x-alexa-api-key'


app = Flask(__name__)

HOME_ASSISTANT_WS_API_URL = "ws://supervisor/core/api/websocket"
token = os.environ.get('SUPERVISOR_TOKEN')

# If we want to use an external connection to HA WS we use this
#HOME_ASSISTANT_WS_API_URL = "ws://192.168.0.1:8123/api/websocket"
#token = options.get('token')

homeassistant_ws_client = HomeAssistantReconnectingClient(HOME_ASSISTANT_WS_API_URL, token)
homeassistant_ws_client.connect()

alexa_skill = alexa_smart_home_skill.AlexaSkill(options, homeassistant_ws_client)

@app.route(ROUTE_PREFIX + "/", methods=['POST'])
def invoke_skill():
    logger.info("Received Alexa request")
    auth_check = do_auth_check(request)
    if auth_check:
        return auth_check
    # callback function for api requests
    request2 = request.get_json()
    logger.debug(request2)
    init_namespace = request2['directive']['header']['namespace']
    if init_namespace == 'Alexa.Discovery':
        return alexa_skill.handle_discovery(request2)
    elif init_namespace == 'Alexa.Authorization':
        return alexa_skill.handle_authorization(request2)
    elif init_namespace == 'Alexa.RTCSessionController':
        return alexa_skill.handle_rtc_session_controller(request2)
    elif init_namespace == 'Alexa':
        return alexa_skill.handle_alexa(request2)
    else:
        logger.info(f"Unhandled message from Alexa: {init_namespace}")



# Can be used by a REST API to fire the announcment if needed.
# Doorbell ID is the alexa_endpoint
@app.route(ROUTE_PREFIX + "/doorbell/<doorbell_id>", methods=['GET'])
def do_doorbell(doorbell_id):
    logger.info("Received Doorbell request")
    auth_check = do_auth_check(request)
    if auth_check:
        return auth_check
    return alexa_skill.do_doorbell(doorbell_id)


# Can be used by a REST API to fire the announcment if needed.
# Doorbell ID is the alexa_endpoint
@app.route(ROUTE_PREFIX + "/motion/<doorbell_id>/detected", methods=['GET'])
def do_motion_detected(doorbell_id):
    logger.info("Received Motion Detected request")
    auth_check = do_auth_check(request)
    if auth_check:
        return auth_check
    return alexa_skill.do_motion_detected(doorbell_id)


# Can be used by a REST API to fire the announcment if needed.
# Doorbell ID is the alexa_endpoint
@app.route(ROUTE_PREFIX + "/motion/<doorbell_id>/not_detected", methods=['GET'])
def do_motion_not_detected(doorbell_id):
    logger.info("Received Motion not Detected request")
    auth_check = do_auth_check(request)
    if auth_check:
        return auth_check    
    return alexa_skill.do_motion_not_detected(doorbell_id)


def do_auth_check(request):
    headers = request.headers
    auth = headers.get(API_KEY_HEADER)

    if auth != API_PASSWORD:
        logger.error(f"Invalid API Password {auth}")
        return jsonify({"message": "ERROR: Unauthorized"}), 401    
    



if __name__ == '__main__':
    logger.info(f"{os.environ}")
    logger.info("Connecting to Home Assistant")
    logger.info("Starting flask app")
    app.run(host='0.0.0.0', debug=debuger_enabled)
