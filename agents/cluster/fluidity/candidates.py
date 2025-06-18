"""Candidates for FluidityApp components selection and scoring."""
#   Copyright (c) 2025. MLSysOps Consortium
#   #
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#   #
#       http://www.apache.org/licenses/LICENSE-2.0
#   #
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#  #
#  #

import logging

from nodes import set_fluiditynode_label, set_node_label
from settings import DRONE_CANDIDATE_DISTANCE, EDGE_CANDIDATE_DISTANCE
from settings import INTERSECTION_THRESHOLD, MOBILE_EDGE_PROXIMITY_RANGE, cluster_id
from util import sort_linked_list
from geo_util import feature_to_shapely, coords_to_shapely, point_in_area
# from operation_area import get_op_area_driver, get_op_area_passenger, get_op_area_edge
from operation_area import get_com_area_edgenode#, get_com_area_drone


logger = logging.getLogger(__name__)


#: float: Allowed battery discharge (safety factor) for planes (0.4-0.8)
BATTERY_DISCHARGE_PLANE = 0.8
#: float: Allowed battery discharge (safety factor) for multicopters (0.4-0.7)
BATTERY_DISCHARGE_MULTICOPTER = 0.6
#: Power required to lift 1 kg (in Watts/kg) Conservative: 170, 120 for more efficient systems
LIFT_POWER_ESTIMATE = 170


def drone_flight_time(drone):
    """Calculate the (remaining) flying time of a drone.

    Args:
        drone (obj): A k8s drone object.

    Returns:
        float: The estimated remaining flying time in minutes.
    """
    if drone['spec']['mobilityType'] == 'fixedWing':
        battery_discharge = BATTERY_DISCHARGE_PLANE
    else:
        battery_discharge = BATTERY_DISCHARGE_MULTICOPTER
    # NOTE: Make it required field in the YAML schema
    if 'maxFlightTime' in drone['spec']['systemServices']['mobility']:
        max_t = drone['spec']['systemServices']['mobility']['maxFlightTime']
        flight_time = max_t * battery_discharge
    else:
        # Used formula: https://www.omnicalculator.com/other/drone-flight-time
        capacity = drone['spec']['battery']['capacity'] # in mAh
        voltage = drone['spec']['battery']['voltage'] # in mV
        total_weight = drone['spec']['physicalFeatures']['mtom'] # in kgs
        # The average ampere draw, in amperes
        av_amp_draw = total_weight * LIFT_POWER_ESTIMATE / (voltage / 1000)
        # The recommended flight time in minutes
        flight_time = (capacity / 1000) * battery_discharge * 60 / av_amp_draw

    remaining_time = flight_time * drone['spec']['battery']['remainingLevel'] / 100
    return remaining_time


def get_drones_scores(candidates, drones_list):
    """Calculate the score to be assigned to each drone candidate.

    Args:
        candidates (list): The names of the drone candidates.
        drones_list (list): The drone k8s objects.

    Returns:
        list: The assigned scores.
    """
    scores = []
    for drone_name in candidates:
        logger.debug('Calculating drone score for: %s', drone_name)
        for drone_obj in drones_list:
            if drone_obj['metadata']['name'] == drone_name:
                score = drone_flight_time(drone_obj)
                scores.append(score)
                logger.debug('Score: %f', score)
    return scores


def find_candidates_drone(app, drones_list, dronestations_list, nodes_list):
    """Find location-based candidates to host the drone components.

    Selects candidates based on their distance to the starting point,
    calculates their score based on status and readiness level and sorts them
    according to their score. Populates the FluidityCompInfoDict['candidates']
    and FluidityCompInfoDict['candidates_scores'] lists for each drone component
    and the FluidityAppInfoDict['drone_candidates'] and
    FluidityAppInfoDict['drone_candidates_scores'] lists.

    Inserts labels to the respective drone and node k8s objects in the form
    candidate.<app-name>.mlsysops.eu/<component-name>.

    Args:
        app (dict): The application info dictionary.
        drones_list (list): The drone k8s objects.
        dronestations_list (list): The dronestation k8s objects.
        nodes_list (list): The node k8s objects.
    """
    logger.info('Find drone candidates')
    app_name = app['name']
    if app['has_driver']:
        logger.info('App has driver')
        # Get extended component specification of driver
        comp_spec = app['components'][app['driver_name']]
        # Get first navigation control point
        first_nav_point = comp_spec['controlPoints'][0]
        first_loc = first_nav_point['point']
        # Use only lon/lat
        point = coords_to_shapely(first_loc[0], first_loc[1])
        # Find candidates, append to list and tag k8s node/drone instances
        if comp_spec['controlType'] == 'full':
            for station in dronestations_list:
                if station['spec']['droneNum'] == 0:
                    continue
                station_geom = feature_to_shapely(station['spec']['area'])
                distance = station_geom.distance(point)
                logger.info('DroneStation candidate %s distance %f',
                            station['metadata']['name'], distance)
                is_inside =  point_in_area(point, station_geom)
                if not is_inside:
                    continue
                app['drone_candidates'].extend(station['spec']['droneNames'])
        # If not candidates found in depot station (or control type is partial)
        # check for nearby depots
        if not app['drone_candidates']:
            for station in dronestations_list:
                if station['spec']['droneNum'] == 0:
                    continue
                station_geom = feature_to_shapely(station['spec']['area'])
                distance = station_geom.distance(point)
                logger.info('DroneStation candidate %s distance %f',
                            station['metadata']['name'], distance)
                if distance > DRONE_CANDIDATE_DISTANCE:
                    continue
                app['drone_candidates'].extend(station['spec']['droneNames'])

        # Get scores for candidates and sort lists
        drones_scores = get_drones_scores(app['drone_candidates'], drones_list)
        app['drone_candidates_scores'] = drones_scores
        # Sort in descending order (higher score is better)
        sorted_candidates = sort_linked_list(app['drone_candidates'],
                                             app['drone_candidates_scores'],
                                             reverse=True)
        app['drone_candidates_scores'].sort(reverse=True)
        app['drone_candidates'] = sorted_candidates

        for comp_name in app['drone_comp_names']:
            # Add candidates list and scores to each drone component spec
            spec = app['components'][comp_name]
            spec['candidates'] = app['drone_candidates']
            spec['candidates_scores'] = app['drone_candidates_scores']
            # Add label with candidate info in drone and node desc
            for drone_name in app['drone_candidates']:
                label = 'candidate.{}.mlsysops.eu/{}'.format(app_name, comp_name)
                # NOTE: Setting node labels only when k8s node exists
                node_exists = False
                for node in nodes_list:
                    if node.metadata.name == drone_name:
                        node_exists = True
                if node_exists:
                    set_node_label(drone_name, label, '')
                set_fluiditynode_label(drone_name, label, '')
    else:
        logger.warning('App does not have driver - not supported')
    
def find_candidates_mobile(app, mobilenodes_list, nodes_list):
    logger.info('Find mobile candidates')
    app_name = app['name']
    for comp_name in app['mobile_comp_names']:
        spec = app['components'][comp_name]
        if spec['cluster_id'] != cluster_id:
            logger.info('Found different id')
            continue
        if not mobilenodes_list:
            logger.warning('mobile nodes list is empty.')
            return
        for entry in mobilenodes_list:
            if entry['spec']['status'] == 'Available':
                spec['candidates'].append(entry['metadata']['name'])
        # Add label with candidate info in drone and node desc
        for mobile_name in spec['candidates']:
            label = 'candidate.{}.mlsysops.eu/{}'.format(app_name, comp_name)
            # NOTE: Setting node labels only when k8s node exists
            node_exists = False
            for node in nodes_list:
                if node.metadata.name == mobile_name:
                    node_exists = True
            if node_exists:
                set_node_label(mobile_name, label, '')
            set_fluiditynode_label(mobile_name, label, '')

def find_candidates_edge(app, comp_name, edgenodes_list, nodes_list):
    """Find location-based candidates to host a (static) edge component.

    Selects candidates for each specified location, calculates their score
    based on their distance to that location and sorts them
    according to their score. Populates the FluidityCompInfoDict['candidates']
    and FluidityCompInfoDict['candidates_scores'] lists and for each location
    in the FluidityCompInfoDict['staticLocations'] creates and populates
    location['candidates'] and location['candidates_scores'] lists.

    Inserts labels to the respective edgenode and node k8s objects in the form
    candidate.<app-name>.mlsysops.eu/<component-name>-loc<location-num>.

    Args:
        app (dict): The application info dictionary.
        comp_name (str): The name of the component.
        edgenodes_list (list): The edgenode k8s objects.
        nodes_list (list): The node k8s objects.
    """
    logger.info('Check host candidates for (static) edge component: %s', comp_name)
    app_name = app['name']
    comp_spec = app['components'][comp_name]
    logger.info('comp_spec: %s',comp_spec)
    edge_locs = comp_spec['staticLocations']
    logger.info('staticLocations: %s',edge_locs)
    loc_num = 0
    for edge_loc in edge_locs:
        edge_geom = feature_to_shapely(edge_loc['area'])
        # Check if component placement specification is a point
        is_point = False
        if edge_loc['area']['geometry']['type'] == 'Point':
            is_point = True
        logger.info('Edge location spec is point: %s', is_point)
        # Find candidates, append to list and tag k8s node/edgenode instances
        for edgenode in edgenodes_list:
            edgenode_loc = edgenode['spec']['location']
            point = coords_to_shapely(edgenode_loc[0], edgenode_loc[1])
            if is_point:
                distance = edge_geom.distance(point)
                logger.info('Edgenode candidate %s distance %f',
                            edgenode['metadata']['name'], distance)
                # If this node was a candidate, remove from candidates.
                if distance > EDGE_CANDIDATE_DISTANCE:
                    if edgenode['metadata']['name'] in comp_spec['candidates']:
                        logger.info('Deleting %s from candidates',edgenode['metadata']['name'])
                        comp_index = comp_spec['candidates'].index(edgenode['metadata']['name'])
                        loc_index = edge_loc['candidates'].index(edgenode['metadata']['name'])
                        del comp_spec['candidates_scores'][comp_index]
                        del edge_loc['candidates_scores'][loc_index]
                        comp_spec['candidates'].remove(edgenode['metadata']['name'])
                        edge_loc['candidates'].remove(edgenode['metadata']['name'])
                        logger.info('comp_spec candidates: %s',comp_spec['candidates'])
                        logger.info('edge_loc candidates: %s',edge_loc['candidates'])
                        # TODO: Also remove labels and add functionality
                        #label = 'candidate.{}.mlsysops.eu/{}-loc{}'.format(app_name, comp_name, loc_num)
                    continue
            else:
                is_inside =  point_in_area(point, edge_geom)
                logger.info('Edgenode candidate %s is inside: %s',
                            edgenode['metadata']['name'], is_inside)
                # If this node was a candidate, remove from candidates.
                if not is_inside:
                    if edgenode['metadata']['name'] in comp_spec['candidates']:
                        # At this point, the lists of candidates and their scores are
                        # already sorted once. Thus, find the name index and remove
                        # from both lists
                        logger.info('Deleting %s from candidates',edgenode['metadata']['name'])
                        comp_index = comp_spec['candidates'].index(edgenode['metadata']['name'])
                        loc_index = edge_loc['candidates'].index(edgenode['metadata']['name'])
                        del comp_spec['candidates_scores'][comp_index]
                        del edge_loc['candidates_scores'][loc_index]
                        comp_spec['candidates'].remove(edgenode['metadata']['name'])
                        edge_loc['candidates'].remove(edgenode['metadata']['name'])
                        logger.info('comp_spec candidates: %s',comp_spec['candidates'])
                        logger.info('edge_loc candidates: %s',edge_loc['candidates'])
                        # TODO: Also remove labels and add functionality
                        #label = 'candidate.{}.mlsysops.eu/{}-loc{}'.format(app_name, comp_name, loc_num)
                        # NOTE: Setting node labels only when k8s node exists
                        #node_exists = False
                        #for node in nodes_list:
                        #    if node.metadata.name == edgenode['metadata']['name']:
                        #        node_exists = True
                        #if node_exists:
                        #    remove_node_label(edgenode['metadata']['name'], label, '')
                        #remove_edgenode_label(edgenode['metadata']['name'], label, '')
                    continue
                distance = edge_geom.centroid.distance(point)
            # Append total component and per location candidates & scores (if any new candidate)
            if edgenode['metadata']['name'] not in comp_spec['candidates']:
                comp_spec['candidates'].append(edgenode['metadata']['name'])
                comp_spec['candidates_scores'].append(distance)
                edge_loc['candidates'].append(edgenode['metadata']['name'])
                edge_loc['candidates_scores'].append(distance)

                label = 'candidate.{}.mlsysops.eu/{}-loc{}'.format(app_name, comp_name, loc_num)
                # NOTE: Setting node labels only when k8s node exists
                node_exists = False
                for node in nodes_list:
                    if node.metadata.name == edgenode['metadata']['name']:
                        node_exists = True
                if node_exists:
                    set_node_label(edgenode['metadata']['name'], label, '')
                set_fluiditynode_label(edgenode['metadata']['name'], label, '')

        # Sort candidates by distance in ascending order (lower is better)
        sorted_candidates = sort_linked_list(edge_loc['candidates'],
                                             edge_loc['candidates_scores'])
        edge_loc['candidates_scores'].sort()
        edge_loc['candidates'] = sorted_candidates
        logger.info('CANDIDATES: %s',edge_loc['candidates'])
        loc_num +=1


def find_candidates_hybrid(app, comp_name, edgenodes_list, reachable_edgenodes, nodes_list, mobilenodes_list):
    """Find location-based edge candidates to host a hybrid component.

    Selects candidates for each drone and edge interacting component and
    calculates their score based on their direct communication coverage.

    Inserts labels to the respective drone and node k8s objects in the form
    candidate.<app-name>.mlsysops.eu/<component-name> and
    hybrid.drone.<app-name>.mlsysops.eu/<component-name> or
    hybrid.edge.<app-name>.mlsysops.eu/<component-name>

    Args:
        app (dict): The application info dictionary.
        comp_name (str): The name of the component.
        edgenodes_list (list): The edgenode k8s objects.
        reachable_edgenodes (list): The reachability info of edge nodes.
        nodes_list (list): The node k8s objects.
    """
    #logger.info('Check host candidates for hybrid component: %s', comp_name)
    app_name = app['name']
    comp_spec = app['components'][comp_name]
    # Hybrid interacting with drone (passenger) components
    if comp_spec['is_drone_interacting'] and comp_spec['cluster_id'] == cluster_id:
        # logger.info('Drone hybrid candidates')
        for edgenode in edgenodes_list:
            range_geom = get_com_area_edgenode(edgenode)
            # Discard node if it has not direct communication interface
            if range_geom is None:
                continue
            # Find intersection with drone operation area
            intersection = range_geom.intersection(app['drone_op_area'])
            # intersection = range_geom.intersection(app['drone_com_area'])
            if intersection.area < INTERSECTION_THRESHOLD:
                continue
            logger.info('Drone hybrid candidate: %s covers drone op area: %f (%f)',
                        edgenode['metadata']['name'],
                        intersection.area,
                        intersection.area/app['drone_op_area'].area)
                        # intersection.area/app['drone_com_area'].area)
            # Add candidates list to component's extended spec
            comp_spec['candidates'].append(edgenode['metadata']['name'])
            comp_spec['candidates_hybrid_drone'].append(edgenode['metadata']['name'])
            comp_spec['candidates_hybrid_drone_intersection'].append(intersection)
            comp_spec['candidates_hybrid_drone_coverage'].append(
                intersection.area/app['drone_op_area'].area)
            # comp_spec['candidates_hybrid_drone_coverage'].append(
            #   intersection.area/app['drone_com_area'].area)

            # TODO: Add labels with coverage (intersection) percentage
            label1 = 'candidate.{}.mlsysops.eu/{}'.format(app_name, comp_name)
            label2 = 'hybrid.drone.{}.mlsysops.eu/{}'.format(app_name, comp_name)
            # NOTE: Setting node labels only when k8s node exists
            node_exists = False
            for node in nodes_list:
                if node.metadata.name == edgenode['metadata']['name']:
                    node_exists = True
            if node_exists:
                set_node_label(edgenode['metadata']['name'], label1, '')
                set_node_label(edgenode['metadata']['name'], label2, '')
            set_fluiditynode_label(edgenode['metadata']['name'], label1, '')
            set_fluiditynode_label(edgenode['metadata']['name'], label2, '')
        # Sort candidates by coverage (higher is better)
        sorted_candidates = sort_linked_list(comp_spec['candidates_hybrid_drone'],
                                             comp_spec['candidates_hybrid_drone_coverage'],
                                             reverse=True)
        sorted_intersection = sort_linked_list(comp_spec['candidates_hybrid_drone_intersection'],
                                               comp_spec['candidates_hybrid_drone_coverage'],
                                               reverse=True)
        comp_spec['candidates_hybrid_drone_coverage'].sort()
        comp_spec['candidates_hybrid_drone'] = sorted_candidates
        comp_spec['candidates_hybrid_drone_intersection'] = sorted_intersection
    
    if comp_spec['is_mobile_interacting'] and comp_spec['cluster_id'] == cluster_id:
        # Find mobile nodes' current location
        for related_comp in comp_spec['hybridHeuristic']['relatedTo']:
            if related_comp not in app['mobile_comp_names']:
                continue
            related_spec = app['components'][related_comp]
            related_candidates_list = related_spec['candidates']
        # Find mobile object
        tmp_found = False
        for entry in mobilenodes_list:
            if entry['metadata']['name'] in related_candidates_list:
                # Find new location
                current_loc = entry['spec']['location']
                logger.info('MobileName: %s , MobileLocation: %s', entry['metadata']['name'], current_loc)
                mobile_point = coords_to_shapely(current_loc[0], current_loc[1])
                #logger.info(entry['metadata']['name'])
                #logger.info(current_loc[0])
                #logger.info(current_loc[1])
                tmp_found = True
                break
        if not tmp_found:
            return
        # Check if there is any edge node close to the mobile node based on proximity range
        for edgenode in edgenodes_list:
            #logger.info(edgenode['metadata']['name'])
            edgenode_loc = edgenode['spec']['location']
            #logger.info(edgenode_loc[0])
            #logger.info(edgenode_loc[1])
            edge_point = coords_to_shapely(edgenode_loc[0], edgenode_loc[1])
            #if is_in_cycle(edge_point, mobile_point, MOBILE_EDGE_PROXIMITY_RANGE)
            distance = mobile_point.distance(edge_point)
            logger.info(distance)
            if distance < MOBILE_EDGE_PROXIMITY_RANGE:
                logger.info('EdgeName %s, EdgeLocation: %s', edgenode['metadata']['name'], edgenode_loc)
                logger.info('Edgenode candidate %s distance %f (OK)', edgenode['metadata']['name'], distance)
                # Append to candidates if needed
                # also append to scores
                if edgenode['metadata']['name'] not in comp_spec['candidates']:
                    comp_spec['candidates'].append(edgenode['metadata']['name'])
                    #comp_spec['candidates_hybrid_mobile'].append(edgenode['metadata']['name'])
                    #comp_spec['candidates_hybrid_mobile_proximity'].append(distance)
                    comp_spec['candidates_scores'].append(distance)
                    # Add labels
                    #label1 = 'candidate.{}.mlsysops.eu/{}'.format(app_name, comp_name)
                    #label2 = 'hybrid.mobile.{}.mlsysops.eu/{}'.format(app_name, comp_name)
                    # NOTE: Setting node labels only when k8s node exists
                    #node_exists = False
                    #for node in nodes_list:
                    #    if node.metadata.name == edgenode['metadata']['name']:
                    #        node_exists = True
                    #if node_exists:
                    #    set_node_label(edgenode['metadata']['name'], label1, '')
                    #    set_node_label(edgenode['metadata']['name'], label2, '')
                    #set_fluiditynode_label(edgenode['metadata']['name'], label1, '')
                    #set_fluiditynode_label(edgenode['metadata']['name'], label2, '')
                else:
                    # Find index of candidate and update its score
                    idx = comp_spec['candidates'].index(edgenode['metadata']['name'])
                    comp_spec['candidates_scores'][idx] = distance
            elif edgenode['metadata']['name'] in comp_spec['candidates']:
                # If a node is not a candidate anymore remove from candidates
                #logger.info('Deleting %s from candidates',edgenode['metadata']['name'])
                comp_index = comp_spec['candidates'].index(edgenode['metadata']['name'])
                #score_index = comp_spec['candidates_hybrid_mobile'].index(edgenode['metadata']['name'])
                del comp_spec['candidates_scores'][comp_index]
                #del comp_spec['candidates_hybrid_mobile'][score_index]
                comp_spec['candidates'].remove(edgenode['metadata']['name'])
                #comp_spec['candidates_hybrid_mobile'].remove(edgenode['metadata']['name'])
                #logger.info('comp_spec candidates: %s',comp_spec['candidates'])
        #print('candidates length = %f', len(comp_spec['candidates']))
        if not comp_spec['candidates']:
            logger.info('Edgenode candidates not found for %s', comp_name)
            return
        # Sort candidates by distance (lower is better)
        #sorted_candidates = sort_linked_list(comp_spec['candidates'],
        #                                     comp_spec['candidates_scores'],
        #                                     reverse=False)
        #comp_spec['candidates'] = sorted_candidates
        #comp_spec['candidates_scores'].sort(key=float)
        #logger.info('CANDIDATES: %s',comp_spec['candidates'])
        #logger.info('SCORES: %s',comp_spec['candidates_scores'])
            
    if not comp_spec['edge_interacting'] or comp_spec['cluster_id'] != cluster_id:
        return
    # Hybrid to edge components
    logger.info('Edgenode hybrid candidates: %s', comp_name)
    # Iterate over all interacting static edge components
    for related_comp in comp_spec['hybridHeuristic']['relatedTo']:
        # Ignore not edge components
        if related_comp not in app['edge_comp_names']:
            continue
        related_spec = app['components'][related_comp]
        related_candidates_list = related_spec['candidates']
        # Iterate over all candidate edge nodes for the interacting
        # static edge component
        for edgenode_name in related_candidates_list:
            # New entry for the specific edgenode candidate for the static edge component
            edge_entry = {
                'candidates': [],
                'intersection': [],
                'coverage': [],
                'host': None
            }
            # Consider all nodes communicating directly with this candidate node
            for edgenode2 in edgenodes_list:
                edgenode2_name = edgenode2['metadata']['name']
                reach_entry = reachable_edgenodes[edgenode_name][edgenode2_name]
                if reach_entry['intersection'].area < INTERSECTION_THRESHOLD:
                    continue
                logger.info('Edgenode hybrid candidate: %s covers edgenode %s (%s) com area: %f (%f)',
                    edgenode2_name,
                    edgenode_name,
                    related_comp,
                    reach_entry['intersection'].area,
                    reach_entry['coverage'])
                comp_spec['candidates'].append(edgenode2_name)
                edge_entry['candidates'].append(edgenode2_name)
                edge_entry['intersection'].append(reach_entry['intersection'])
                edge_entry['coverage'].append(reach_entry['coverage'])

                label1 = 'candidate.{}.mlsysops.eu/{}'.format(app_name, comp_name)
                label2 = 'hybrid.edge.{}.mlsysops.eu/{}'.format(app_name, comp_name)
                value2 = '{}.{}'.format(related_comp, edgenode_name)
                # NOTE: Setting node labels only when k8s node exists
                node_exists = False
                for node in nodes_list:
                    if node.metadata.name == edgenode2_name:
                        node_exists = True
                if node_exists:
                    set_node_label(edgenode2_name, label1, '')
                    set_node_label(edgenode2_name, label2, value2)
                set_fluiditynode_label(edgenode2_name, label1, '')
                set_fluiditynode_label(edgenode2_name, label2, value2)
            # Sort candidates by coverage (higher is better)
            sorted_candidates = sort_linked_list(edge_entry['candidates'],
                                                 edge_entry['coverage'],
                                                 reverse=True)
            sorted_intersection = sort_linked_list(edge_entry['intersection'],
                                                   edge_entry['coverage'],
                                                   reverse=True)
            edge_entry['coverage'].sort()
            edge_entry['candidates'] = sorted_candidates
            edge_entry['intersection'] = sorted_intersection
            comp_spec['candidates_hybrid_edge'][related_comp][edgenode_name] = edge_entry
