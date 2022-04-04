from time import sleep
from ws4py.client.threadedclient import WebSocketClient
import logging
import json
import threading

def do_nothing():
    pass

latest_states = {}
include_by_default = True

class HomeAssistantClient(WebSocketClient):

    logger = logging.getLogger(__name__)
    authenticated = False
    connected = False
    message_id = 1
    id_to_type = {}
    id_to_entity_id = {}
    _entity_id_to_trigger = {}
    reconnection_thread = None
    _disconnected_callback = do_nothing

    def set_token(self, token):
        self.homeassistant_token = token

    def set_disconnect_callback(self, callback):
        self._disconnected_callback = callback

    def set_authenticated_callback(self, callback):
        self._authenticated_callback = callback

    def opened(self):
        self.logger.info("Home Assistant WebSocket Connection Opened")
        self.connected = True

    def closed(self, code, reason=None):
        self.logger.warning("Home Assistant WebSocket Connection Closed. Code: {} Reason {}".format(code, reason))
        self.connected = False
        self.authenticated = False

        self.id_to_type.clear()
        self.id_to_entity_id.clear()
        self._entity_id_to_trigger.clear()

        self._disconnected_callback()

    def subscribe_to_trigger(self, entity_id, callback, from_state=None, to_state=None):
        self.logger.info(f"Subscribing for trigger for {entity_id} from_state: {from_state}, to_state: {to_state}")
        trigger = {
                "platform": "state",
                "entity_id": entity_id,
        }
        if from_state:
            trigger['from'] = from_state
        if to_state:
            trigger['to'] = to_state

        payload = {
            "type": "subscribe_trigger",
            "trigger": trigger,
        }

        id = self._send_with_id(payload, "subscribe_trigger")
        self.id_to_entity_id[id] = entity_id

        self._entity_id_to_trigger[entity_id] = Subscription(entity_id, callback, from_state, to_state)

    def turn_off_light(self, entity_id):
        return self.call_service(
            domain="light",
            service="turn_off",
            entity_id=entity_id
        )

    def turn_off(self, entity_id):
        '''
        Attempts to turn off a device by guessing the domain from the entity id name
        '''
        self.logger.info(f"Turning off {entity_id}")
        split_entity_id = entity_id.split(".")
        if len(split_entity_id) != 2:
            self.logger.error(f"Couldn't get domain from entity_id - is the entity_id correct? {entity_id}")
        else:
            self.call_service(split_entity_id[0], "turn_off", entity_id=entity_id)

    def call_service(self, domain, service, entity_id=None, service_data=None):

        payload = {
            "type": "call_service",
            "domain": domain,
            "service": service,
        }
        if service_data:
            payload["service_data"] = service_data
        if entity_id:
            payload["target"] = {
                "entity_id": entity_id
            }
        return self._send_with_id(payload, "call_service")


    def received_message(self, m):
        self.logger.debug("Received message: {}".format(m))
        message_text = m.data.decode(m.encoding)
        message = json.loads(message_text)
        message_type = message.get('type', None)
        if message_type == "auth_required":
            self.do_auth_required(message)
        elif message_type == "auth_ok":
            self.do_auth_complete()
        elif message_type == "auth_invalid":
            self.do_auth_invalid(message)
        elif message_type == "result":
            self.do_result(message)
        elif message_type == "event":
            self.do_event(message)
        elif message_type == "pong":
            self.do_pong(message)
        else:
            self.logger.warning("Unexpected message: ", message)

    def do_auth_required(self, m):
        self.logger.info("Home Assistant Web Socket Authorisation required")
        payload = {
                'type':'auth',
                'access_token': self.homeassistant_token
        }
        self.logger.debug(f"Sending {payload}")
        self._send(payload)

    def do_auth_invalid(self, message):
        self.logger.error("Home Assistant Web Socket Authorisation invalid: {}".format(message))
        self.authenticated = False
        self._authenticated_callback(self.authenticated)


    def do_auth_complete(self):
        self.logger.info("Home Assistant Web Socket Authorisation complete")
        self.authenticated = True
        self._authenticated_callback(self.authenticated)

    # def get_states(self):
    #     payload = {
    #         'type' : 'get_states'
    #     }
    #     self._send_with_id(payload, "getstates")

    # def subscribe_for_updates(self):
    #     payload = {
    #         "type": "subscribe_events",
    #         "event_type": "state_changed"
    #     }
    #     self._send_with_id(payload, "subscribe")


    def do_result(self, message):
        self.logger.debug(self.id_to_type)
        if 'result' in message:
            message_type = self.id_to_type.pop(message['id'])
            self.logger.debug(f"Got message type {message_type}")
            if message_type == 'subscribe_trigger':
                entity_id = self.id_to_entity_id.get(message['id'])
                self.logger.info(f"Subscribed for {entity_id}")


    def do_event(self, message):
        message_id = message.get('id', -1)
        if message_id in self.id_to_entity_id.keys():
            entity_id = self.id_to_entity_id.get(message['id'])
            self.logger.debug(f"Found entity id {entity_id} in {self.id_to_entity_id}")
            subscription: Subscription = self._entity_id_to_trigger.get(entity_id)
            callback = subscription.callback
            self.logger.debug(f"Found callback {callback} in {self._entity_id_to_trigger}")
            callback(entity_id, message)
        else:
            self.logger.debug(f"Didn't find message id {message_id} in {self.id_to_entity_id}")


    def _send_with_id(self, payload, type_of_call):
        payload['id'] = self.message_id
        self.logger.debug(f"Adding {self.message_id} as type {type_of_call}")
        self.id_to_type[self.message_id] = type_of_call
        self.message_id += 1
        self._send(payload)
        return payload['id']

    def _send(self, payload):
        json_payload = json.dumps(payload)
        self.logger.debug(f"Sending: {json_payload}")
        self.send(json_payload)   

class Subscription:
    def __init__(self, entity_id, callback, from_state, to_state) -> None:
        self.entity_id = entity_id
        self.callback = callback
        self.from_state = from_state
        self.to_state = to_state


class HomeAssistantReconnectingClient():

    def __init__(self, url, token):
        self.logger = logging.getLogger(__name__)
        self.url = url
        self.token = token
        self.ws = None
        self._reconnection_thread = None
        self._triggers = []

    def connect(self):
        self._reconnection_thread = threading.Thread(target=self._connect, daemon=True)
        self._reconnection_thread.start()

    def connected(self):
      if self.ws is None or self.ws.client_terminated: 
        return False
      return True  

    def _connect_if_required(self):  
      if not self.connected(): 
        try:
          self.ws = HomeAssistantClient(self.url)
          self.ws.set_token(self.token)
          self.ws.set_disconnect_callback(self.disconnected)
          self.ws.set_authenticated_callback(self.authenticated)
          self.ws.connect()
        except Exception as e:
          self.logger.info("Error connecting to Home Assistant Websocket", e)  
          self.ws = None  

    def subscribe_to_trigger(self, entity_id, callback, from_state=None, to_state=None):
        self._triggers.append(
            Subscription(
                entity_id,
                callback,
                from_state,
                to_state
            )
        )

        if self.ws.authenticated:
            self.ws.subscribe_to_trigger(entity_id, callback, from_state, to_state)

    def turn_off(self, entity_id):
        if self.ws.authenticated:
            self.ws.turn_off(entity_id)
        else:
            self.logger.warning(f"Can't turn off {entity_id} as we aren't connected to home assistant")

    def call_service(self, domain, service, entity_id=None, service_data=None):
        if self.ws.authenticated:
            self.ws.subscribe_to_trigger(domain, service, entity_id, service_data)
        else:
            self.logger.warning(f"Can't call {domain}.{service} as we aren't connected to home assistant")



    def authenticated(self, auth_success):
        if auth_success:
            for trigger in self._triggers:
                self.ws.subscribe_to_trigger(
                    trigger.entity_id,
                    trigger.callback,
                    trigger.from_state,
                    trigger.to_state
                )
        

    def disconnected(self):
        self.logger.warning("Disconnected will attempt to reconnect.")
        self._reconnection_thread = threading.Thread(target=self._reconnect, daemon=True)
        self._reconnection_thread.start()

    def _internal_connection(self):
        while not self.connected():
            self.logger.debug("Home Assistant WebSocket - Attempting to connect...")
            self._connect_if_required()
            self.logger.debug(f"Home Assistant WebSocket - connection work? {self.connected()}")
            sleep(5) # Give a second before reconnecting to ensure the socket has been closed.


    def _connect(self):
        self.logger.info("Home Assistant WebSocket - Starting connection thread")
        self._internal_connection()
        self.logger.info("Home Assistant WebSocket - conection complete - connection thread ending")

    def _reconnect(self):
        self.logger.info("Home Assistant WebSocket - Starting reconnection thread")
        sleep(5) # Give a second before reconnecting to ensure the socket has been closed.
        self._internal_connection()
        self.logger.info("Home Assistant WebSocket - Reconnection complete - reconnection thread ending")
