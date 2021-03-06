import geopandas as gp
import pandas
import pytest
from shapely.geometry import Polygon

from gerrychain.graph import Adjacency, Graph


@pytest.fixture
def geodataframe():
    a = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    b = Polygon([(0, 1), (0, 2), (1, 2), (1, 1)])
    c = Polygon([(1, 0), (1, 1), (2, 1), (2, 0)])
    d = Polygon([(1, 1), (1, 2), (2, 2), (2, 1)])
    df = gp.GeoDataFrame({"ID": ["a", "b", "c", "d"], "geometry": [a, b, c, d]})
    df.crs = "+init=epsg:4326"
    return df


@pytest.fixture
def geodataframe_with_boundary():
    """
    abe
    ade
    ace
    """
    a = Polygon([(0, 0), (0, 1), (0, 2), (0, 3), (1, 3), (1, 2), (1, 1), (1, 0)])
    b = Polygon([(1, 2), (1, 3), (2, 3), (2, 2)])
    c = Polygon([(1, 0), (1, 1), (2, 1), (2, 0)])
    d = Polygon([(1, 1), (1, 2), (2, 2), (2, 1)])
    e = Polygon([(2, 0), (2, 1), (2, 2), (2, 3), (3, 3), (3, 2), (3, 1), (3, 0)])
    df = gp.GeoDataFrame({"ID": ["a", "b", "c", "d", "e"], "geometry": [a, b, c, d, e]})
    df.crs = "+init=epsg:4326"
    return df


def test_add_data_to_graph_can_handle_column_names_that_start_with_numbers():
    graph = Graph([("01", "02"), ("02", "03"), ("03", "01")])
    df = pandas.DataFrame({"16SenDVote": [20, 30, 50], "node": ["01", "02", "03"]})
    df = df.set_index("node")

    graph.add_data(df, ["16SenDVote"])

    assert graph.nodes["01"]["16SenDVote"] == 20
    assert graph.nodes["02"]["16SenDVote"] == 30
    assert graph.nodes["03"]["16SenDVote"] == 50


def test_join_can_handle_right_index():
    graph = Graph([("01", "02"), ("02", "03"), ("03", "01")])
    df = pandas.DataFrame({"16SenDVote": [20, 30, 50], "node": ["01", "02", "03"]})

    graph.join(df, ["16SenDVote"], right_index="node")

    assert graph.nodes["01"]["16SenDVote"] == 20
    assert graph.nodes["02"]["16SenDVote"] == 30
    assert graph.nodes["03"]["16SenDVote"] == 50


def test_make_graph_from_dataframe_creates_graph(geodataframe):
    graph = Graph.from_geodataframe(geodataframe)
    assert isinstance(graph, Graph)


def test_make_graph_from_dataframe_preserves_df_index(geodataframe):
    df = geodataframe.set_index("ID")
    graph = Graph.from_geodataframe(df)
    assert set(graph.nodes) == {"a", "b", "c", "d"}


def test_make_graph_from_dataframe_gives_correct_graph(geodataframe):
    df = geodataframe.set_index("ID")
    graph = Graph.from_geodataframe(df)

    assert edge_set_equal(
        set(graph.edges), {("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")}
    )


def test_make_graph_works_with_queen_adjacency(geodataframe):
    df = geodataframe.set_index("ID")
    graph = Graph.from_geodataframe(df, adjacency=Adjacency.Queen)

    assert edge_set_equal(
        set(graph.edges),
        {("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"), ("b", "c")},
    )


def test_can_pass_queen_or_rook_strings_to_control_adjacency(geodataframe):
    df = geodataframe.set_index("ID")
    graph = Graph.from_geodataframe(df, adjacency="queen")

    assert edge_set_equal(
        set(graph.edges),
        {("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d"), ("b", "c")},
    )


def test_can_insist_on_not_reprojecting(geodataframe):
    df = geodataframe.set_index("ID")
    graph = Graph.from_geodataframe(df, reproject=False)

    for node in ("a", "b", "c", "d"):
        assert graph.nodes[node]["area"] == 1

    for edge in graph.edges:
        assert graph.edges[edge]["shared_perim"] == 1


def test_reprojects_by_default(geodataframe):
    # I don't know what the areas and perimeters are in UTM for these made-up polygons,
    # but I'm pretty sure they're not 1.
    df = geodataframe.set_index("ID")
    graph = Graph.from_geodataframe(df)

    for node in ("a", "b", "c", "d"):
        assert graph.nodes[node]["area"] != 1

    for edge in graph.edges:
        assert graph.edges[edge]["shared_perim"] != 1


def test_identifies_boundary_nodes(geodataframe_with_boundary):
    df = geodataframe_with_boundary.set_index("ID")
    graph = Graph.from_geodataframe(df)

    for node in ("a", "b", "c", "e"):
        assert graph.nodes[node]["boundary_node"]
    assert not graph.nodes["d"]["boundary_node"]


def test_computes_boundary_perims(geodataframe_with_boundary):
    df = geodataframe_with_boundary.set_index("ID")
    graph = Graph.from_geodataframe(df, reproject=False)

    expected = {"a": 5, "e": 5, "b": 1, "c": 1}

    for node, value in expected.items():
        assert graph.nodes[node]["boundary_perim"] == value


def edge_set_equal(set1, set2):
    return {(y, x) for x, y in set1} | set1 == {(y, x) for x, y in set2} | set2
