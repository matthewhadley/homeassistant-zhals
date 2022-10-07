import appdaemon.plugins.hass.hassapi as hass
import json
import sqlite3
from websocket import create_connection

HASS_DB = "/config/home-assistant_v2.db"

class zhals(hass.Hass):

  def initialize(self):
    self.token = self.args["token"]
    self.addr = "ws://" + self.args["host"] + ":8123/api/websocket"

    # run at user defined interval in seconds
    self.run_every(self.monitor, 'now', self.args["interval"])

  def monitor (self, kwargs):
    self.scan()

  def scan (self):
    zha_data = {"success":0}

    try:
      ws = create_connection(self.addr)
      result =  ws.recv()
      ws.send(json.dumps( {"type": "auth", "access_token": self.token} ))
      result =  ws.recv()
      ws.send(json.dumps( {"id": 1, "type": "zha/devices"} ))
      result =  ws.recv()
      zha_data = json.loads(result)
    except:
      self.log("Unable to get ZHA data")

    if (zha_data["success"]):
      for device in zha_data["result"] :
        last_seen = str(device["last_seen"])
        sensor = "zha_" + str(device["user_given_name"]).replace(" ", "_").lower() + "_last_seen"
        entity = "sensor." + sensor

        # set up the state and attributes of the entity
        attributes = {}
        attributes["device_class"] = "timestamp"
        attributes["friendly_name"] = str(device["user_given_name"] + " Last Seen")

        if (sensor in self.entities.sensor):
          state = self.entities.sensor[sensor].state
          attributes["count"] = self.entities.sensor[sensor].attributes.count
        else:
          state = "Unknown"
          attributes["count"] = 0

          # check for a count value in recorder history
          connection = sqlite3.connect(HASS_DB)
          cursor = connection.cursor()
          result = cursor.execute("SELECT shared_attrs FROM states LEFT JOIN state_attributes ON states.attributes_id = state_attributes.attributes_id WHERE entity_id = 'sensor." + sensor + "'ORDER BY state_id DESC LIMIT 1")
          recorder_data = result.fetchone()
          connection.close()

          if (recorder_data != None):
            recorder_attributes = json.loads(recorder_data[0])
            if ("count" in recorder_attributes):
              attributes["count"] = recorder_attributes["count"]

        # log values
        self.log(sensor, level = "DEBUG")

        # record entity if newer state or first state with no count
        if (last_seen != state or attributes["count"] == 0):
          attributes["count"] += 1
          self.set_state("sensor." + sensor, state=last_seen, attributes=attributes)
          self.log(sensor + " " + state + " [" + str(attributes["count"]) + "]")
    else:
      self.log("No valid JSON")