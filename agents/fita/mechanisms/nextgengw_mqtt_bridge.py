import paho.mqtt.client as mqtt
from paho.mqtt.subscribeoptions import SubscribeOptions
from mlsysops.logger_util import logger

class Mqtt_Bridge:
    def __init__(self, ip,port,device_id):
        self.broker_address = ip
        self.broker_port = port
        self.device_id = device_id

    def publish(self, topic, message, properties=None):
        self.client.publish(topic, payload=message, properties=properties)

    def subscribe(self, topic, callback):
        self.client.subscribe(topic, options=SubscribeOptions(noLocal=True))
        self.client.message_callback_add(topic,callback)

    # Callback function for when a message is received from the broker
    def on_message(self, client, userdata, msg):
        try:
            logger.info("Unfiltered message arrived : "+ message)
        except Exception as e:
            logging.exception(datetime.datetime.now())

    def start(self, connect_cb):
        # Create MQTT client instance
        self.client = mqtt.Client(protocol=5)

        # Set callback functions
        self.client.on_connect = connect_cb
        self.client.on_message = self.on_message

        # Set username and password
        self.client.username_pw_set(f"NextGen_Agent_{self.device_id}", "Fr4unh0f3r")

        # Connect to MQTT broker
        self.client.connect(self.broker_address, self.broker_port, 60)

        # Loop to maintain network traffic flow, handles reconnecting, etc.
        self.client.loop_start()