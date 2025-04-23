"""Fluidity controller-related configuration settings."""
import os
os.environ["TELEMETRY_ENDPOINT"] = "10.96.12.128:4317"
from mlstelemetry import MLSTelemetry
#: float: Maximum distance of a drone to be considered candidate
DRONE_CANDIDATE_DISTANCE = 25
#: float: Maximum distance of an edgenode to be considered candidate
EDGE_CANDIDATE_DISTANCE = 25

#: float: Maximum proximity range between edge nodes and a mobile node
MOBILE_EDGE_PROXIMITY_RANGE = 50

#: float: minimum coverage threshold
INTERSECTION_THRESHOLD = 1.0

#: float: maximum proximity for exclusion policies in meters
PROXIMITY_THRESHOLD = 20.0

#: float: maximum required coverage percentage
MAX_COVERAGE = 0.8

# network ranges in meters
RANGE_WIFI = 50
RANGE_BLUETOOTH = 10
RANGE_ZIGBEE = 100
RANGE_LORA = 10000

#: Policies registration port for mobility service
POLICY_PORT_MOBILITY = 50071
#: Policies registration port for camera service
POLICY_PORT_CAMERA = 50072

TELEMETRY_FLAG = 'OFF'
#cluster_id = "uth-prod-cluster"
cluster_id = None
# The policy configuration filepath
policy_config_file = None
# The policy implementation directory (contains all policy files).
policy_dir = None
mlsClient = MLSTelemetry("uth_demo_fluidity_mechanism", "uth_demo_fluidityapp_controller")

def init():
    global drone_controller_status
    drone_controller_status = 'INIT'
