import base64
import re
import requests
from uuid import uuid4
import logging

class Doorbell(): 

    def __init__(self, options, rtsp_to_webrtc_url):
        self.logger = logging.getLogger(__name__)
        self.alexa_friendly_name = options['alexa_friendly_name']
        self.alexa_endpoint = options['alexa_endpoint']
        self.doorbell_sensor = options.get('doorbell_sensor', None)
        self.motion_sensor = options.get('motion_sensor', None)
        self.rtsp_to_webrtc_stream_id = options['rtsp_to_webrtc_stream_id']
        self.rtsp_to_webrtc_channel_id = options['rtsp_to_webrtc_channel_id']
        self.reset_doorbell = options.get('reset_doorbell', False)
        self._rtsptowebrtc_url = rtsp_to_webrtc_url


    def initiate_session_with_offer(self, request):
        sdp_offer = request['directive']['payload']['offer']['value']
        self.logger.info(f"SDP OFFER:\n{sdp_offer}")
        
        # Currently RTSPtoWebRTC doesn't support audio so remove that from the OFFER
        sdp_offer = sdp_offer.replace('a=group:BUNDLE audio0 video0', 'a=group:BUNDLE video0')
        sdp_offer = re.sub('a=group:BUNDLE video0.*m=video', 'm=video', sdp_offer, flags=re.DOTALL)

        base_64_encoded_offer = base64.b64encode(sdp_offer.encode('ascii'))
        url = f"{self._rtsptowebrtc_url}/stream/{self.rtsp_to_webrtc_stream_id}/channel/{self.rtsp_to_webrtc_channel_id}/webrtc"
        headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        }
        data = {
            'data': base_64_encoded_offer
        }
        response = requests.post(url, headers=headers, data=data)
        if not response.ok:
          self.logger.error(f"Error getting answer: {response.content}")
          return {}, 500
        else:

          answer = base64.b64decode(response.content).decode('utf-8')
          # Doesn't seem to make a different so removing for now
          # Amazon docs suggest setting this if no audio.
          # answer = answer.replace('a=sendrecv', 'a=sendonly')
          self.logger.info(f"SDP ANSWER:\n{answer}")

          payload = {
          "event": {
              "header": {
              "namespace": "Alexa.RTCSessionController",
              "name": "AnswerGeneratedForSession",
              "messageId": str(uuid4()),
              "correlationToken": request['directive']['header']['correlationToken'],
              "payloadVersion": "3"
              },
              "endpoint": {
              "scope": {
                  "type": "BearerToken",
                  "token":  request['directive']['endpoint']['scope']['token']
              },
              "endpointId": request['directive']['endpoint']['endpointId']
              },
              "payload": {
              "answer": {
                  "format" : "SDP",
                  "value" : answer
              }
              }
          }
          }
          return payload

    def session_connected(self, request):
        payload = {
        "event": {
            "header": {
            "namespace": "Alexa.RTCSessionController",
            "name": "SessionConnected",
            "messageId": str(uuid4()),
            "correlationToken": request['directive']['header']['correlationToken'],
            "payloadVersion": "3"
            },
            "endpoint": {
            "scope": {
                "type": "BearerToken",
                "token": request['directive']['endpoint']['scope']['token']
            },
            "endpointId": request['directive']['endpoint']['endpointId']
            },
            "payload": {
            "sessionId" : request['directive']['payload']['sessionId']
            }
        }
        }
        return payload

    def session_disconnected(self, request):
        payload = {
            "event": {
                "header": {
                "namespace": "Alexa.RTCSessionController",
                "name": "SessionDisconnected",
                "messageId": str(uuid4()),
                "correlationToken": request['directive']['header']['correlationToken'],
                "payloadVersion": "3"
                },
                "endpoint": {
                "scope": {
                    "type": "BearerToken",
                    "token": request['directive']['endpoint']['scope']['token']
                },
                "endpointId": request['directive']['endpoint']['endpointId']
                },
                "payload": {
                "sessionId" : request['directive']['payload']['sessionId']
                }
            }
        }
        return payload



    def get_discovery_endpoint_details(self):
      displayCategories = []
      capabilities = []

      # Add video feed.
      # CAMERA has to be first for it to work
      # https://amazon.developer.forums.answerhub.com/questions/238533/doorbell-doesnt-show-video.html?childToView=244593#comment-244593
      displayCategories.append("CAMERA")
      capabilities.append(
            {
              "type": "AlexaInterface",
              "interface": "Alexa.RTCSessionController",
              "version": "3",
              "configuration": {
                "isFullDuplexAudioSupported": "false"
              }
            }        
      )

      # Add motion notification
      if self.motion_sensor is not None:
        displayCategories.append('MOTION_SENSOR')
        capabilities.append(
              {
                "type": "AlexaInterface",
                "interface": "Alexa.MotionSensor",
                "version": "3",
                "properties": {
                  "supported": [
                    {
                      "name": "detectionState"
                    }
                  ],
                  "proactivelyReported": "true",
                  "retrievable": "true"
                }
              }        
        )

      # Add doorbell notifications
      if self.doorbell_sensor is not None:
        displayCategories.append('DOORBELL')
        capabilities.append(
              {
                "type": "AlexaInterface",
                "interface": "Alexa.DoorbellEventSource",
                "version": "3",
                "proactivelyReported" : "true"
              }       
        )


      # TODO look at supporting this when my region supports it.
      # if self.event_detection_sensor:
      #   # Require CAMERA display category for this but should already be added before this section. 
      #   # displayCategories.insert(0, 'CAMERA')
      #   capabilities.append(
      #         {
      #           "type": "AlexaInterface",
      #           "interface": "Alexa.EventDetectionSensor",
      #           "version": "3",
      #           "properties": {
      #             "supported": [
      #               {
      #                 "name": "humanPresenceDetectionState"
      #               }
      #             ],
      #             "retrievable": False,
      #             "proactivelyReported": True
      #           },
      #           "configuration": {
      #             "detectionMethods": ["AUDIO", "VIDEO"],
      #             "detectionModes": {
      #               "humanPresence": {
      #                 "featureAvailability": "ENABLED",
      #                 "supportsNotDetected": False
      #               }
      #             }
      #           }
      #         }     
      #   )
      # TODO look at supporting this when it is in my region
      # capabilities.append(
      #       {
      #         "type": "AlexaInterface",
      #         "interface": "Alexa.MediaMetadata",
      #         "version": "3",
      #         "proactivelyReported": "true"
      #       }       
      # )


      capabilities.append(
            {
              "type": "AlexaInterface",
              "interface": "Alexa.EndpointHealth",
              "version": "3",
              "properties": {
                "supported": [
                  {
                    "name":"connectivity"
                  }
                ],
                "proactivelyReported": "true",
                "retrievable": "true"
              }
            }       
      )
      capabilities.append(
            {
              "type": "AlexaInterface",
              "interface": "Alexa",
              "version": "3"
            }        
      )

      return {
          "endpointId": self.alexa_endpoint,
          "manufacturerName": "Camera",
          "description": "Generic RTSP Video Doorbell",
          "friendlyName": self.alexa_friendly_name,
          "displayCategories": displayCategories,
          "cookie": {},
          "capabilities": capabilities
        }