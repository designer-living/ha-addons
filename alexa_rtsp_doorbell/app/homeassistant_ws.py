from asyncio.log import logger
from ws4py.client.threadedclient import WebSocketClient
import logging
import json

latest_states = {}
include_by_default = True

class HomeAssistantClient(WebSocketClient):

    connected = False
    message_id = 1
    id_to_type = {}
    id_to_entity_id = {}
    _entity_id_to_callback = {}
    _entity_id_to_trigger = {}

    def set_token(self, token):
        self.homeassistant_token = token

    def opened(self):
        logging.info("Home Assistant WebSocket Connection Opened")

    def closed(self, code, reason=None):
        logging.warning("Home Assistant WebSocket Connection Closed. Code: {} Reason {}".format(code, reason))
        # TODO ensure all internal state is cleared on a disconnect.
        self.id_to_entity_id.clear()
        self.connected = False

    def subscribe_to_trigger(self, entity_id, callback, from_state=None, to_state=None):
        trigger = {
                "platform": "state",
                "entity_id": entity_id,
        }
        if from_state:
            trigger['from_state'] = from_state
        if to_state:
            trigger['to_state'] = to_state

        payload = {
            "type": "subscribe_trigger",
            "trigger": trigger,            
        }
        # TODO store an object that describes this whole subscription not just the callback
        # then we can make it so that resub will also do to/from state correctly. We also
        # need to store it agaisnt the ID so we can link the messages up properly.
        self._entity_id_to_callback[entity_id] = callback
        if self.connected:
            id = self._send_with_id(payload, "subscribe_trigger")
            self.id_to_entity_id[id] = entity_id


    def received_message(self, m):
        logging.debug("Received message: {}".format(m))
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
            logging.warning("Unexpected message: ", message)

    def do_auth_required(self, m):
        logging.info("Home Assistant Web Socket Authorisation required")
        payload = {
                'type':'auth',
                'access_token': self.homeassistant_token
        }
        logging.debug(f"Sending {payload}")
        self._send(payload)

    def do_auth_invalid(self, message):
        logging.error("Home Assistant Web Socket Authorisation invalid: {}".format(message))

    def do_auth_complete(self):
        logging.info("Home Assistant Web Socket Authorisation complete")
        self.connected = True
        # Resub
        self.re_do_subs()

    def re_do_subs(self):
        for entity_id, callback in self._entity_id_to_callback.items():
            logger.info(f"Resubscribing for {entity_id}")
            self.subscribe_to_trigger(entity_id, callback)


    def get_states(self):
        payload = {
            'type' : 'get_states'
        }
        self._send_with_id(payload, "getstates")

    def subscribe_for_updates(self):
        payload = {
            "type": "subscribe_events",
            "event_type": "state_changed"
        }
        self._send_with_id(payload, "subscribe")


    def do_result(self, message):
        logger.debug(self.id_to_type)
        if 'result' in message:
            message_type = self.id_to_type.pop(message['id'])
            logger.debug(f"Got message type {message_type}")
            if message_type == 'subscribe_trigger':
                entity_id = self.id_to_entity_id.get(message['id'])
                logging.info(f"Subscribed for {entity_id}")


    def do_event(self, message):
        message_id = message.get('id', -1)
        if message_id in self.id_to_entity_id.keys():
            entity_id = self.id_to_entity_id.get(message['id'])
            logger.debug(f"Found entity id {entity_id} in {self.id_to_entity_id}")
            callback = self._entity_id_to_callback.get(entity_id)
            logger.debug(f"Found callback {callback} in {self._entity_id_to_callback}")
            callback(entity_id, message)
        else:
            logger.debug(f"Didn't find message id {message_id} in {self.id_to_entity_id}")


    def _send_with_id(self, payload, type_of_call):
        payload['id'] = self.message_id
        logger.debug(f"Adding {self.message_id} as type {type_of_call}")
        self.id_to_type[self.message_id] = type_of_call
        self.message_id += 1
        self._send(payload)
        return payload['id']

    def _send(self, payload):
        json_payload = json.dumps(payload)
        logger.debug(f"Sending: {json_payload}")
        self.send(json_payload)     