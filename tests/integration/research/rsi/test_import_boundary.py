"""RSI's independent boundary is checked with the actual shared graph contract."""
from tests.integration.research.router.test_import_boundary import (
    graph_copy, test_current_protected_import_graph,
    test_real_graph_rejects_each_planted_hot_path_import,
    test_real_graph_rejects_transitive_hot_path_import,
)
