#!/usr/bin/with-contenv bashio

# We only use 1 worker otherwise we end up causing issues for the HA Websockets.
# 1 should be enough for now.
gunicorn -w 1 -b 0.0.0.0:5000 app:app