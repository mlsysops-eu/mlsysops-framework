"""Operation area calculation functionality."""
import copy
import logging
# import sys
# import time

# from shapely.geometry import shape #, union
# from shapely.ops import unary_union
# from shapely.geometry import Point, MultiPoint, LineString, Polygon, MultiPolygon

from fluidityapp_settings import RANGE_WIFI, RANGE_ZIGBEE, RANGE_BLUETOOTH, RANGE_LORA
from geo_util import feature_to_shapely #,lonlat_to_planar, lonlat_from_planar
from geo_util import coords_to_shapely #, is_in_cycle, get_distance_gc


# Default settings for buffering areas
DEFAULT_BUFFER_DISTANCE = 7.0
DEFAULT_BUFFER_RESOLUTION = 16
# 1 (round), 2 (flat), 3 (square)
DEFAULT_CAPS_STYLE = 3
# 1 (round), 2 (mitre), and 3 (bevel)
DEFAULT_JOINS_STYLE = 1


#: dict: Template for line string paths
line_string_template = {
    "type": "Feature",
    "properties": {
        "name": "path",
        "shape": "Line"
    },
    "geometry": {
        "type": "LineString",
        "coordinates": []
    }
}


#: dict: Template for single points
point_template = {
    "type": "Feature",
    "properties": {
        "name": "point",
        "shape": "Marker"
    },
    "geometry": {
        "type": "Point",
        "coordinates": []
    }
}


logger = logging.getLogger(__name__)


def get_net_range(technology):
    """Get the estimated range of the networking technology.

    Args:
        technology (str): The direct networking interface technology
        (WiFi, Bluetooth, LoRa, ZigBee).

    Returns:
        float: The range in meters.
    """
    if technology == 'WiFi':
        net_range = RANGE_WIFI
    elif technology == 'Bluetooth':
        net_range = RANGE_BLUETOOTH
    elif technology == 'ZigBee':
        net_range = RANGE_ZIGBEE
    elif technology == 'LoRa':
        net_range = RANGE_LORA
    else:
        net_range = RANGE_WIFI
    return float(net_range)

def get_op_area_driver(spec):
    """Calculate operational area of driver component.

    Args:
        spec (dict): The extended specification of the driver component.

    Returns:
        geom (obj): Shapely geometry object of the union of all areas.
        None: If invalid component specification.
    """
    op_area = None
    # Sanity checks
    if spec['placement'] != 'drone' or spec['class'] != 'driver':
        logger.error('Op area calculation, no driver component (%s)',
                     spec['name'])
        return None
    if 'controlPoints' not in spec:
        logger.error('Op area calculation, no controlPoints in driver (%s)',
                     spec['name'])
        return None
    logger.info('Calculating driver op area (%s)', spec['name'])
    # Iterate over all control points
    for control_point in spec['controlPoints']:
        if control_point['navigationType'] == 'regionBased':
            geom_planar = feature_to_shapely(control_point['navigationArea'])
        elif control_point['navigationType'] == 'pathBased':
            geom_planar = feature_to_shapely(control_point['navigationArea'])
            geom_planar = geom_planar.buffer(DEFAULT_BUFFER_DISTANCE,
                                             DEFAULT_BUFFER_RESOLUTION,
                                             None,
                                             DEFAULT_CAPS_STYLE,
                                             DEFAULT_JOINS_STYLE)
        logger.debug('Control point area: %f', geom_planar.area)
        if op_area is None:
            op_area = geom_planar
        else:
            # op_area = unary_union([op_area, geom_planar])
            op_area = op_area.union(geom_planar) # Usually this is faster
    logger.info('Driver operation area: %f (%s)', op_area.area, spec['name'])
    return op_area


def get_op_area_passenger(spec):
    """Calculate operational area of a passenger component.

    Args:
        spec (dict): The extended specification of the passenger component.

    Returns:
        geom (obj): Shapely geometry object of the union of all areas.
        None: If invalid component specification.
    """
    op_area = None
    # sanity checks
    if spec['placement'] != 'drone' or spec['class'] != 'passenger':
        logger.error('Op area calculation, no passenger component (%s)',
                     spec['name'])
        return None
    if 'pointsOfInterest' not in spec:
        logger.info('Op area calculation, no POIs in passenger (%s)',
                    spec['name'])
        return None
    logger.info('Calculating passenger op area (%s)', spec['name'])

    if spec['serviceAccess'] == 'path':
        path_feature = copy.deepcopy(line_string_template)
        # Iterate over all points of interest to create line string feature
        for point in spec['pointsOfInterest']['points']:
            # path_feature['geometry']['coordinates'].append(point)
            path_feature['geometry']['coordinates'].append([point[0], point[1]])
        geom_planar = feature_to_shapely(path_feature)
        op_area = geom_planar.buffer(DEFAULT_BUFFER_DISTANCE,
                                     DEFAULT_BUFFER_RESOLUTION,
                                     None,
                                     DEFAULT_CAPS_STYLE,
                                     DEFAULT_JOINS_STYLE)
    elif spec['serviceAccess'] == 'points':
        for point in spec['pointsOfInterest']['points']:
            point_feature = copy.deepcopy(point_template)
            geom_planar = feature_to_shapely(point_feature)
            geom_planar = geom_planar.buffer(DEFAULT_BUFFER_DISTANCE) # Circle
            if op_area is None:
                op_area = geom_planar
            else:
                # op_area = unary_union([op_area, geom_planar])
                op_area = op_area.union(geom_planar) # Usually this is faster
    else:
        logger.error('Op area calculation, unknown service access pattern (%s)',
                     spec['name'])
        return None
    logger.info('Passenger operation area: %f (%s)',
                op_area.area, spec['name'])
    return op_area


def get_op_area_edge(spec):
    """Calculate operational area of a (static) edge component.

    Args:
        spec (dict): The extended specification of the static edge component.

    Returns:
        geom (obj): Shapely geometry object of the area
        None: if invalid component specification
    """
    op_area = None
    # Sanity checks
    if spec['placement'] != 'edge': #or spec['class'] != 'static':
        logger.error('Op area calculation, no static edge component (%s).',
                     spec['name'])
        return None
    if 'staticLocations' not in spec:
        logger.error('Op area calculation, no staticLocations for edge (%s)',
                     spec['name'])
        return None
    logger.info('Calculating static edge op area (%s)', spec['name'])
    for location in spec['staticLocations']:
        feature = location['area']
        geom_planar = feature_to_shapely(feature)
        if geom_planar.geom_type == 'Point':
            geom_planar = geom_planar.buffer(DEFAULT_BUFFER_DISTANCE) # Circle
        if op_area is None:
            op_area = geom_planar
        else:
            # op_area = unary_union([op_area, geom_planar])
            op_area = op_area.union(geom_planar) # Usually this is faster
    logger.info('Static edge operation area: %f (%s)',
                op_area.area, spec['name'])
    return op_area


def get_com_area_drone(op_area, technology='WiFi'):
    """Calculate direct communication area of a drone's operation area.

    Args:
        geom (obj): Shapely geometry object of the operation area.
        technology (str): The direct networking interface technology
        (WiFi, Bluetooth, LoRa, ZigBee).

    Returns:
        geom (obj): Shapely geometry object of communication area, or None.
    """
    # In case there is no operation area
    if op_area is None:
        return None
    net_range = get_net_range(technology)
    geom_planar = op_area.buffer(net_range,
                                 DEFAULT_BUFFER_RESOLUTION,
                                 None,
                                 DEFAULT_CAPS_STYLE,
                                 DEFAULT_JOINS_STYLE)
    logger.info('Drone com area (%s): %f', technology, geom_planar.area)
    return geom_planar


def get_com_area_edgenode(edgenode):
    """Calculate direct communication area of an edge node.

    Args:
        edgenode (dict): The full specification of the edge node.

    Returns:
        geom (obj): Shapely geometry object of edge node's communication area,
        or None in case of no direct communication interface.
    """
    edgenode_loc = edgenode['spec']['location']
    point = coords_to_shapely(edgenode_loc[0], edgenode_loc[1])
    edgenode_labels = edgenode['metadata']['labels']
    net_range = float(edgenode_labels['fluidity.gr/direct-range'])
    if net_range == 0:
        return None
    geom_planar = point.buffer(net_range,
                               DEFAULT_BUFFER_RESOLUTION,
                               None,
                               DEFAULT_CAPS_STYLE,
                               DEFAULT_JOINS_STYLE)
    logger.info('Edgenode communication area: %f', geom_planar.area)
    return geom_planar
