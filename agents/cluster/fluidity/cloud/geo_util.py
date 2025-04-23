#/usr/bin/python3
"""Geographic utility methods."""
from __future__ import print_function
# import json
import math
# import sys

# from functools import partial

# import geojson
# import pyproj
import utm
import shapely.ops

from shapely.geometry import shape
# from shapely.geometry import buffer, mapping
# from shapely.geometry import GeometryCollection
from shapely.geometry import Point
# from shapely.geometry import MultiPoint, LineString, Polygon, MultiPolygon


def latlonalt_to_xyz(lat, lon, alt=0.0):
    """Transform WGS84 coordinates to planar."""
    # pylint: disable=invalid-name
    p = 0.017453292519943295     # Pi/180
    lat_rad = lat * p # latitude in radians
    lon_rad = lon * p # longitude in radians
    a = 6371000 # earth radius  R = 6371 km
    e = 0 # earth eccentricity
    Rn = a / (math.sqrt (1 - pow (e, 2) * pow (math.sin (lat_rad), 2)))
    x = (Rn + alt) * math.cos (lat_rad) * math.cos (lon_rad)
    y = (Rn + alt) * math.cos(lat_rad) * math.sin(lon_rad)
    z = ((1 - pow (e, 2)) * Rn + alt) * math.sin(lat_rad)
    return x, y, z


def get_distance_gc(lat1, lon1, lat2, lon2):
    """Find the greate-circle distance between two points using the haversine
    formula.

    Note:
        The Haversine formula determines the great-circle distance
        between two points on a sphere, i.e., the shortest distance over the
        earth's surface, but it doesn't account for the Earth being a spheroid.

    Returns:
        The great-circle distance, in metres.
    """
    # pylint: disable=invalid-name
    p = 0.017453292519943295     #Pi/180
    a = (0.5 - math.cos((lat2 - lat1) * p)/2 +
        math.cos(lat1 * p) * math.cos(lat2 * p) *
        (1 - math.cos((lon2 - lon1) * p))/2)
    return 12742000 * math.asin(math.sqrt(a)) #2 * R; R = 6371 km


def utm_from_lonlat(lon, lat, alt=None):
    """Transformer for longitude latitude coordinates to UTM x/y"""
    # pylint: disable=invalid-name
    x, y, z, l = utm.from_latlon(lat, lon)
    return x, y


def utm_to_lonlat(x, y, zone_num=34, zone_letter='S'):
    """Transformer for UTM x/y to longitude latitude coordinates"""
    # pylint: disable=invalid-name
    lat, lon = utm.to_latlon(x, y, zone_num, zone_letter)
    return lon, lat


def lonlat_to_planar(geom):
    """Transform coordinates of a shape from geodetic lon/lat to UTM planar x/y.

    Args:
        geom (obj): A shapely geometry object.

    Returns:
        Obj: A geometry of the same type with transformed coordinates.
    """
    # NOTE: workaround for out of bounds error in python 2.7
    # if geom.geom_type == 'Point':
    #     planar_coords = utm_from_lonlat(geom.x, geom.y)
    #     return Point(planar_coords)
    # elif geom.geom_type == 'Polygon':
    #     planar_coords_list = []
    #     # coord_tuples = mapping(geom)['coordinates'][0]
    #     for coord in list(geom.exterior.coords):
    #         planar_coords = utm_from_lonlat(coord[0], coord[1])
    #         planar_coords_list.append(planar_coords)
    #     return  Polygon(planar_coords_list)
    return shapely.ops.transform(utm_from_lonlat, geom)


def lonlat_from_planar(geom):
    """Transform coordinates of a shape from UTM planar x/y to geodetic lon/lat.

    Args:
        geom (obj): A shapely geometry object.

    Returns:
        Obj: A geometry of the same type with transformed coordinates.
    """
    return shapely.ops.transform(utm_to_lonlat, geom)


def feature_to_shapely(feature, proj=True):
    """Transform a geojson feature to a shapely geometry.

    Args:
        feature (str): A valid geojson feature object.
        proj (bool): Project the coordinates from WGS84 to EPSG:3857.

    Returns:
        Obj: The respective shapely geometry object.
        None: if an error occurs.
    """
    geom = None
    if feature['geometry']['type'] in ['Point', 'MultiPoint', 'LineString',
                                       'Polygon', 'MultiPolygon']:
    # elif feature['geometry']['type'] in ['Point', 'LineString', 'Polygon']:
        geom = shape(feature['geometry'])
        if proj:
            geom = lonlat_to_planar(geom)
        if (feature['geometry']['type'] == 'Point' and
            feature['properties']['shape'] == 'Circle'):
            geom = geom.buffer(feature['properties']['radius'])
    return geom


def coords_to_shapely(lon, lat, proj=True):
    """Transform coordinates to a shapely Point.

    NOTE: Its does not use altitude/elevation.

    Args:
        lon (float): Longitude, in degrees.
        lat (float): Latitude, in degrees.
        proj (bool): Project the coordinates from WGS84 to EPSG:3857.

    Returns:
        Obj: The respective shapely Point object.
    """
    point = Point(lon, lat)
    if proj:
        point = lonlat_to_planar(point)
    return point


def point_in_area(point, area):
    """Check if the area contains the point.

    Args:
        point (obj): A Shapely Point geometry.
        area (obj): A Shapely geometry.

    Returns:
        bool: True if contained, False otherwise.
    """
    # return point.within(shape)
    return area.contains(point)


def is_in_polygon(point, polygon):
    """Check if point is inside polygon."""
    if polygon.contains(point):
        return True
    return False


def is_in_cycle(point, circle_center, circle_radius):
    """Check if point is inside circle."""
    # circle = circle_center.buffer(circle_radius)
    # return circle.contains(point)
    if point.distance(circle_center) <= circle_radius:
        return True
    return False
