import json

import geopandas as gp
import networkx.readwrite

from rundmcmc.accept import always_accept
from rundmcmc.chain import MarkovChain
from rundmcmc.make_graph import (add_data_to_graph, construct_graph,
                                 get_assignment_dict_from_df)
from rundmcmc.partition import Partition
from rundmcmc.proposals import propose_random_flip
from rundmcmc.updaters import (Tally, boundary_nodes, county_splits, cut_edges,
                               cut_edges_by_part, exterior_boundaries,
                               perimeters, polsby_popper, votes_updaters,
                               interior_boundaries)
from rundmcmc.validity import (L1_reciprocal_polsby_popper, UpperBound,
                               Validator, no_vanishing_districts,
                               single_flip_contiguous,
                               within_percent_of_ideal_population)
import os

default_constraints = [single_flip_contiguous,
                       no_vanishing_districts]

FILE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DATA_PATH = os.path.join(FILE_PATH, "testData/")


def example_partition():
    df = gp.read_file(os.path.join(TEST_DATA_PATH, "mo_cleaned_vtds.shp"))

    with open(os.path.join(TEST_DATA_PATH, "MO_graph.json")) as f:
        graph_json = json.load(f)

    graph = networkx.readwrite.json_graph.adjacency_graph(graph_json)

    assignment = get_assignment_dict_from_df(df, "GEOID10", "CD")

    add_data_to_graph(df, graph, ['PR_DV08', 'PR_RV08', 'POP100', 'ALAND10', 'COUNTYFP10'],
                      id_col='GEOID10')

    updaters = {
        **votes_updaters(['PR_DV08', 'PR_RV08'], election_name='08'),
        'population': Tally('POP100', alias='population'),
        'counties': county_splits('counties', 'COUNTYFP10'),
        'cut_edges': cut_edges,
        'cut_edges_by_part': cut_edges_by_part
    }
    return Partition(graph, assignment, updaters)


def PA_partition(path=None):
    if not path:
        path = os.path.join(TEST_DATA_PATH, "PA_graph_with_data.json")

    # this is a networkx adjancency data json file with CD, area, population, and vote data
    graph = construct_graph(path, data_source_type="json")

    # Add frozen attributes to graph
    # data = gp.read_file("./testData/frozen.shp")
    # add_data_to_graph(data, graph, ['Frozen'], 'wes_id')

    assignment = dict(zip(graph.nodes(), [graph.node[x]['CD'] for x in graph.nodes()]))

    updaters = {
            **votes_updaters(['VoteA', 'VoteB']),
            'population': Tally('POP100', alias='population'),
            'perimeters': perimeters,
            'exterior_boundaries': exterior_boundaries,
            'interior_boundaries': interior_boundaries,
            'boundary_nodes': boundary_nodes,
            'cut_edges': cut_edges,
            'areas': Tally('ALAND10', alias='areas'),
            'polsby_popper': polsby_popper,
            'cut_edges_by_part': cut_edges_by_part
            }

    return Partition(graph, assignment, updaters)


class DefaultChain(MarkovChain):
    """
    A MarkovChain with propose_random_flips proposal and always_accept
    acceptance function. Also instantiates a Validator for you from a
    list of constraints.
    """

    def __init__(self, partition, constraints, total_steps):
        validator = Validator(constraints)
        super().__init__(propose_random_flip, validator,
                         always_accept, partition, total_steps)


class BasicChain(MarkovChain):
    """
    The standard MarkovChain for replicating the Pennsylvania analysis. The proposal
    is a single random flip at the boundary of a district. A step is valid if the
    districts are connected, no districts disappear, and the populations of the districts
    are all within 1% of one another. Accepts every valid proposal.

    Requires a lot of different updaters.
    """

    def __init__(self, initial_state, total_steps=1000):
        """
        :initial_state: the initial graph partition. Must have a cut_edges updater
        :total_steps: (defaults to 1000) the total number of steps that the random walk
        should perform.
        """
        if not initial_state['cut_edges']:
            raise ValueError('BasicChain needs the Partition to have a cut_edges updater.')

        if not initial_state['population']:
            raise ValueError('BasicChain needs the Partition to have a population updater.')

        population_constraint = within_percent_of_ideal_population(initial_state, 0.01)

        compactness_limit = L1_reciprocal_polsby_popper(initial_state)
        compactness_constraint = UpperBound(L1_reciprocal_polsby_popper, compactness_limit)

        validator = Validator(default_constraints + [population_constraint, compactness_constraint])

        super().__init__(propose_random_flip, validator, always_accept, initial_state,
                         total_steps=total_steps)


grid_validator = Validator([single_flip_contiguous, no_vanishing_districts])


class GridChain(MarkovChain):
    """
    A very simple Markov chain. The proposal is a single random flip at the boundary of a district.
    A step is valid if the districts are connected and no districts disappear.
    Requires a 'cut_edges' updater.
    """

    def __init__(self, initial_grid, total_steps=1000):
        if not initial_grid['cut_edges']:
            raise ValueError('BasicChain needs the Partition to have a cut_edges updater.')

        super().__init__(propose_random_flip, grid_validator,
                         always_accept, initial_grid, total_steps=total_steps)
