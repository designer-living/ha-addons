import json
import logging
import urllib3
import os

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

def lambda_handler(request, context):
    response = None
    _LOGGER.debug("Directive:")
    _LOGGER.debug(json.dumps(request, indent=4, sort_keys=True))

    api_url = os.environ.get('HOSTNAME')
    password = os.environ.get('PASSWORD')
    http = urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED',
        timeout=urllib3.Timeout(connect=2.0, read=10.0)
    )

    response = http.request(
        'POST', 
        api_url,
        headers={
            'Content-Type': 'application/json',
            'x-alexa-api-key': password
        },
        body=json.dumps(request, indent=4, sort_keys=True).encode('utf-8'),
    )
    if response.status >= 400:
        return {
            'event': {
                'payload': {
                    'type': 'INVALID_AUTHORIZATION_CREDENTIAL' 
                            if response.status in (401, 403) else 'INTERNAL_ERROR',
                    'message': response.data.decode("utf-8"),
                }
            }
        }
    _LOGGER.info(response.data)
    return json.loads(response.data.decode('utf-8'))