import datetime
from uuid import uuid4
import requests
import datetime
import json
import os
import logging
from homeassistant_ws import HomeAssistantClient
from rtsp_to_webrtc_doorbell import Doorbell

class AlexaSkill():

    def __init__(self, options, homeassistant_ws_client):
        
        self.logger = logging.getLogger(__name__)
        self.homeassistant_ws_client: HomeAssistantClient = homeassistant_ws_client
        self.alexa_event_gateway_url = options.get('alexa_event_gateway_url')
        self._oauth_url = options.get('oauth_token_url')
        self._client_id = options.get('alexa_client_id')
        self.rtsp_to_webrtc_url = options.get('rtsp_to_webrtc_url')
        self._client_secret = options.get('alexa_client_secret')
        self._json_credentials_file_name = '/data/token.json'

        self.ha_entity_id_to_doorbell_id = {}
        self._doorbells = {}
        doorbells = options.get('doorbells', [])
        self.print_camera_streams(self.rtsp_to_webrtc_url)
        if len(doorbells) == 0:
          self.print_camera_streams(self.rtsp_to_webrtc_url)

        for doorbell in doorbells:
          self.logger.info(f"Setting up {doorbell['alexa_friendly_name']}")
          self.logger.debug(f"{doorbell}")
          alexa_endpoint = doorbell['alexa_endpoint']
          doorbell_sensor = doorbell.get('doorbell_sensor', None)
          motion_sensor = doorbell.get('motion_sensor', None)

          d = Doorbell(doorbell, self.rtsp_to_webrtc_url)
          self._doorbells[alexa_endpoint] = d
          self.ha_entity_id_to_doorbell_id[doorbell_sensor] = alexa_endpoint
          self.homeassistant_ws_client.subscribe_to_trigger(
             doorbell_sensor,
             self.do_doorbell_from_ha,
             from_state="off",
             to_state="on"
          )
          self.ha_entity_id_to_doorbell_id[motion_sensor] = alexa_endpoint
          self.homeassistant_ws_client.subscribe_to_trigger(
             motion_sensor,
             self.do_motion_from_ha
          )

        self._json_credentials = {}
        if os.path.exists(self._json_credentials_file_name):
          with open(self._json_credentials_file_name) as json_file:
            self.logger.info(f"Loading token from {os.path.realpath(json_file.name)}")
            json_credentials = json.load(json_file)
            self._process_and_set_json_credentials(json_credentials)
        else:
          self.logger.error("ACCOUNT ISN'T LINKED TO SKILL. Link account in the Alexa App. If already linked disable and re-enable the skill")


    def do_doorbell_from_ha(self, entity_id, message):
      self.logger.debug(f"Message from HA: {message}")

      from_state = message["event"]["variables"]["trigger"]["from_state"]["state"]
      to_state = message["event"]["variables"]["trigger"]["to_state"]["state"]
      self.logger.debug(f"From State: {from_state}, to state: {to_state}")
      if from_state == "off" and to_state == "on":
        doorbell_id = self.ha_entity_id_to_doorbell_id.get(entity_id)
        self.do_doorbell(doorbell_id)

    def do_motion_from_ha(self, entity_id, message):
      # TODO Amazon docs say there need to be at least 30 seconds between events.
      self.logger.debug(f"Message from HA: {message}")
      from_state = message["event"]["variables"]["trigger"]["from_state"]["state"]
      to_state = message["event"]["variables"]["trigger"]["to_state"]["state"]
      if from_state == "off" and to_state == "on":
        doorbell_id = self.ha_entity_id_to_doorbell_id.get(entity_id)
        self.do_motion_detected(doorbell_id)
      elif from_state == "on" and to_state == "off":
        doorbell_id = self.ha_entity_id_to_doorbell_id.get(entity_id)
        self.do_motion_not_detected(doorbell_id)


    def handle_rtc_session_controller(self, request):
        init_name = request['directive']['header']['name']
        endpoint_name = request['directive']['endpoint']['endpointId']
        camera = self._doorbells.get(endpoint_name)
        if init_name == "InitiateSessionWithOffer":
          return camera.initiate_session_with_offer(request)
        elif init_name == "SessionConnected":
          return camera.session_connected(request)
        elif init_name == "SessionDisconnected":
          return camera.session_disconnected(request)
        else:
          self.logger.info(f"Unprocessed name: {init_name}")


    def handle_authorization(self, request):
      init_name = init_name = request['directive']['header']['name']
      if init_name == 'AcceptGrant':
        code = init_name = request['directive']['payload']['grant']['code']
        self.do_access_token_request(code)
        # RESPOND
        resp = {
                "event": {
                    "header": {
                        "messageId": str(uuid4()),
                        "namespace": "Alexa.Authorization",
                        "name": "AcceptGrant.Response",
                        "payloadVersion": "3"
                    },
                    "payload": {}
                }
        }
        return resp
      else:
        self.logger.info("ERROR in auth")
        # TODO need to handle this anod not return a tuple.
        return {}, 500

    def do_access_token_request(self, code):
      self.logger.info("Requesting access token")
      self._do_token_request(code=code)

    # kwargs is required for the AppDaemon scheduler
    def do_refresh_token_request(self, kwargs={}):
      self.logger.info("Refreshing access token")
      self._do_token_request(refresh_token=self._json_credentials['refresh_token'])

    def _do_token_request(self, code=None, refresh_token=None):
      headers = {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      }

      payload = {}
      if code is not None:
        payload = {
          'grant_type': 'authorization_code',
          'code': code,
          'client_id' : self._client_id,
          'client_secret': self._client_secret,

        }
      elif refresh_token is not None:
        payload = {
          'grant_type': 'refresh_token',
          'refresh_token': refresh_token,
          'client_id' : self._client_id,
          'client_secret': self._client_secret,
        }

      self.logger.info(f"Requesting Token: {payload}")
      response = requests.post(self._oauth_url, headers=headers, data=payload)
      self.logger.info(f"{response.status_code} - {response.json()}")
      if not response.ok:
        self.logger.error("Error getting access token - try disabling and re-enabling the skill")
      else:
        json_credentials = response.json()
        self._process_and_set_json_credentials(json_credentials)

    def _process_and_set_json_credentials(self, json_credentials):
      expires_datetime = None
      if 'expires_at' not in json_credentials:
        expires_datetime = datetime.datetime.now() + datetime.timedelta(seconds=json_credentials['expires_in'])
        json_credentials['expires_at'] = expires_datetime.isoformat()
        # If we don't include expires_at it means we got it from Amazon so need to save the details
        # If we do include expires at it means we have read it from the filesystem.
        with open(self._json_credentials_file_name, 'w') as outfile:
          json.dump(json_credentials, outfile)
      else:
        self.logger.info(json_credentials['expires_at'])
        expires_datetime = datetime.datetime.fromisoformat(json_credentials['expires_at'])

      if datetime.datetime.now() > expires_datetime:
        # Immediate refresh - this will come back through this method
        self.logger.info("Token is old doing an immediate refresh")
        # Need to set the credentials before refresh as we need the refresh token
        self._json_credentials = json_credentials
        self.do_refresh_token_request({})
        return
      else:
        # Schedule Refresh
        self.logger.info("Scheduling refresh")
        #self.run_in(self.do_refresh_token_request, json_credentials['expires_in'] - 60)


      self.logger.info("Updated TOKEN")
      self._json_credentials = json_credentials
      self.logger.info(self._json_credentials)

    def handle_discovery(self, request):

      response_header = {
          "namespace": "Alexa.Discovery",
          "name": "Discover.Response",
          "messageId": str(uuid4()),
          "payloadVersion": "3"
      }

      endpoints = []
      for doorbell in self._doorbells.values():
        endpoints.append(
          doorbell.get_discovery_endpoint_details()
        )

      response_payload = {
        "endpoints": endpoints
      }

      discovery_response = {
          "event": {
              "header": response_header,
              "payload": response_payload
          }
      }
      self.logger.debug(f"Discovery Response: {discovery_response}")
      return discovery_response

    def handle_alexa(self, request):
      init_name = request['directive']['header']['name']
      endpoint_id = request['directive']['endpoint']['endpointId']
      if init_name == 'ReportState':
        self.logger.debug(f"Should be reporting state for {endpoint_id}")
      pass

    def do_doorbell(self, doorbell_id, retry=0):
      if doorbell_id in self._doorbells:
        bearer_token = self._json_credentials['access_token']
        timestamp =  datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.logger.info(f"Doorbell: {doorbell_id} - {timestamp}")
        headers = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
        }
        payload = {
                    "context": {},
                    "event": {
                        "header": {
                        "messageId": str(uuid4()),
                        "namespace":  "Alexa.DoorbellEventSource",
                        "name": "DoorbellPress",
                        "payloadVersion": "3"
                        },
                        "endpoint": {
                            "scope": {
                                "type": "BearerToken",
                                "token": bearer_token
                            },
                            "endpointId" :  doorbell_id
                        },
                        "payload": {
                            "cause": {
                                "type": "PHYSICAL_INTERACTION"
                            },
                            "timestamp": timestamp
                        }
                    }
        }
        if self.logger.isEnabledFor(logging.DEBUG):
          self.logger.debug(f"Sending: {json.dumps(payload)}")
        response = requests.post(self.alexa_event_gateway_url, headers=headers, json=payload)
        self.logger.debug(f"{response.status_code} - {response.content}")
        if not response.ok:
          error_code = response.json().get('payload', {}).get('code', '')
          if error_code  == 'INVALID_ACCESS_TOKEN_EXCEPTION':
            # Try our best to recover by trying to refresh the token
            self.do_refresh_token_request()
            # For now we just retry once.
            if retry == 0:
              self.do_doorbell(doorbell_id, retry=(retry+1))
            else:
              return {'result' : 'error', 'details' : response.json()}
          else:
              return {'result' : 'error', 'details' : response.json()}
        else:
          return { 'result': 'ok'}
      else:
        return {'result' : 'error', 'details' : f'Invalid doorbell ID {doorbell_id}'}


    def do_motion_detected(self, doorbell_id):
      return self.do_motion(doorbell_id, "DETECTED")

    def do_motion_not_detected(self, doorbell_id):
      return self.do_motion(doorbell_id, "NOT_DETECTED")


    def do_motion(self, doorbell_id, state, retry=0):
      if doorbell_id in self._doorbells:
        bearer_token = self._json_credentials['access_token']
        timestamp =  datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.logger.info(f"Motion: {doorbell_id} - {timestamp}")
        headers = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
        }
        payload = {  
          "event": {
            "header": {
              "namespace": "Alexa",
              "name": "ChangeReport",
              "messageId":  str(uuid4()),
              "payloadVersion": "3"
            },
            "endpoint": {
              "scope": {
                "type": "BearerToken",
                "token": bearer_token
              },
              "endpointId": doorbell_id
            },
            "payload": {
              "change": {
                "cause": {
                  "type": "PHYSICAL_INTERACTION"
                },
                "properties": [
                  {
                    "namespace": "Alexa.MotionSensor",
                    "name": "detectionState",
                    "value": state,
                    "timeOfSample": timestamp,
                    "uncertaintyInMilliseconds": 0
                  }
                ]
              }
            }
          },
          "context": {
            "properties": [
              {
                "namespace": "Alexa.EndpointHealth",
                "name": "connectivity",
                "value": {
                  "value": "OK"
                },
                "timeOfSample": timestamp,
                "uncertaintyInMilliseconds": 0
              }
            ]
          }
        }
        if self.logger.isEnabledFor(logging.DEBUG):
          self.logger.debug(json.dumps(payload))
        response = requests.post(self.alexa_event_gateway_url, headers=headers, json=payload)
        self.logger.debug(f"{response.status_code} - {response.content}")
        if not response.ok:
          error_code = response.json().get('payload', {}).get('code', '')
          if error_code  == 'INVALID_ACCESS_TOKEN_EXCEPTION':
            # Try our best to recover by trying to refresh the token
            self.do_refresh_token_request()
            # For now we just retry once.
            if retry == 0:
              self.do_doorbell(doorbell_id, retry=(retry+1))
            else:
              return {'result' : 'error', 'details' : response.json()}
          else:
              return {'result' : 'error', 'details' : response.json()}
        else:
          return { 'result': 'ok'}
      else:
        return {'result' : 'error', 'details' : f'Invalid doorbell ID {doorbell_id}'}

    def print_camera_streams(self, url):
        headers = {
            'Content-Type': 'application/json',
        }        
        response = requests.get(url + "/streams", headers=headers)
        json_response = response.json()

        for key, value in json_response.get('payload', {}).items():
          self.logger.info(f'RTSPToWeb STREAM: {value.get("name", "<NOT SET>")} - {key}')
