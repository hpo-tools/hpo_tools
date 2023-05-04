import tempfile
import urllib.request
from typing import Dict, Optional, Set

import networkx as nx
import numpy as np
import obonet
from mp_utils import mp_wrapper
from networkx.classes.multidigraph import MultiDiGraph
from numpy.typing import NDArray


class Ontology:
    root_id = "HP:0000118"

    def __init__(self, hpo_path: Optional[str] = None, ignore_obsolete: bool = True):
        if hpo_path is None:
            graph = self._create_from_obolibrary(ignore_obsolete)
        else:
            graph = obonet.read_obo(hpo_path, ignore_obsolete)
        self.graph: MultiDiGraph = self._extract_phenotypic_abnormality_subgraph(graph)
        self.undirected_graph = self.graph.to_undirected(as_view=True)
        self.indexer = {node: i for i, node in enumerate(graph.nodes)}
        self.inverse_indexer = {i: node for i, node in enumerate(graph.nodes)}
        self.__depths: Optional[Dict] = None

    @classmethod
    def _extract_phenotypic_abnormality_subgraph(cls, graph: MultiDiGraph) -> MultiDiGraph:
        global_root_id = "HP:0000001"
        top_nodes = [child for (child, _) in graph.in_edges(global_root_id)]
        for node in top_nodes:
            if node == cls.root_id:
                continue
            ancestors = nx.ancestors(graph, node) | {node}
            graph.remove_nodes_from(ancestors)
        graph.remove_node(global_root_id)
        return graph

    def __len__(self):
        return len(self.graph)

    def __iter__(self):
        return iter(self.graph)

    def __getitem__(self, item):
        return self.graph[item]

    def nodes(self, data=True):
        return self.graph.nodes(data=data)

    @staticmethod
    def _create_from_obolibrary(ignore_obsolete: bool) -> MultiDiGraph:
        url = "http://purl.obolibrary.org/obo/hp.obo"
        with tempfile.NamedTemporaryFile() as f:
            _ = urllib.request.urlretrieve(url, f.name)
            return obonet.read_obo(f.name, ignore_obsolete)

    def children(self, hpo_id: str, include_self: bool = True) -> Set[str]:
        """Ontology edges are directed towards the root so children are formally predecessors."""
        children = set(self.graph.predecessors(hpo_id))
        return children | {hpo_id} if include_self else children

    def parents(self, hpo_id: str, include_self: bool = True) -> Set[str]:
        """Ontology edges are directed towards the root so parents are formally successors."""
        parents = set(self.graph.successors(hpo_id))
        return parents | {hpo_id} if include_self else parents

    def descendants(self, hpo_id: str, include_self: bool = True) -> Set[str]:
        """Ontology edges are directed towards the root so descendants are formally ancestors."""
        descendants = nx.ancestors(self.graph, hpo_id)
        return descendants | {hpo_id} if include_self else descendants

    def ancestors(self, hpo_id: str, include_self: bool = True) -> Set[str]:
        """Ontology edges are directed towards the root so ancestors are formally descendants."""
        ancestors = nx.descendants(self.graph, hpo_id)
        return ancestors | {hpo_id} if include_self else ancestors

    def depth(self, hpo_id) -> int:
        """Depth := distance from the given node to the ontology root."""
        return nx.shortest_path_length(self.graph, hpo_id, self.root_id)

    @property
    def depths(self) -> Dict[str, int]:
        """Depth := distance from the given node to the ontology root."""
        if self.__depths is None:
            depths = nx.single_target_shortest_path_length(self.graph, self.root_id)
            self.__depths = dict(depths)
        return self.__depths

    def distance(self, source: str, target: str, undirected: bool = False) -> int:
        """
        Calculates distance between two nodes. If `undirected = True` then graph is converted into an undirected one.
        :param source: HPO ID of source node
        :param target: HPO ID of target node
        :param undirected: if True, edge direction will be ignored
        :return: distance from source to target
        """
        # graph: Union[MultiGraph, MultiDiGraph]
        graph = self.graph if not undirected else self.graph.to_undirected(as_view=True)
        return nx.shortest_path_length(graph, source, target)

    def _get_dist_matrix_row(self, source: str) -> NDArray[np.uint16]:
        lens = dict(nx.single_source_shortest_path_length(self.undirected_graph, source))
        ans = np.zeros(len(self.graph), dtype=np.uint16)
        for key, i in self.indexer.items():
            ans[i] = lens[key]
        return ans

    def get_dist_matrix(self, n_processes: int) -> NDArray[np.uint16]:
        inputs = (node for node in self.graph.nodes)
        rows = mp_wrapper(n_processes)(self._get_dist_matrix_row)(inputs)
        return np.vstack(rows)


onto = Ontology("/Users/ivustianiu/hpo_tools/hp.obo")
pass
