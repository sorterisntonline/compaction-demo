#!/usr/bin/env python3
import numpy as np
import scipy, random, itertools, sys
from typing import List, Tuple, Optional, Set, Dict

# For analysis purposes we track the number of iterations until convergence.
global total_iters
total_iters = 0

def rank_centrality(A, tol=1e-8, max_iters=100000):
    """
    Implements the rank centrality algorithm for pairwise comparisons.  The
    argument "A" is an n x n matrix such that A_ij / (A_ij + A_ji) represents
    the probability that item j is preferred to item i.  For example in a
    tournament, A_ij could be the number of times that player j beat player i.
    The matrix may be sparse (i.e. some (i,j) pairs may have no comparisons)
    but the graph induced by non-zero arcs must be fully connected.

    Returns a vector "scores" of length n such that scores[i] is proportional
    to the global preference for item i.  Its entries sum approximately to 1,
    i.e. it is a probability distribution over the n items.

    tol: iteration stops when sum(abs(scores - prev_scores)) < tol
    max_iters: the algorithm also stops after this many iterations
    """
    # Compute a normalized matrix W such that the probabilities for each (i, j)
    # pair sum to 1.
    n = A.shape[0]
    W = np.zeros((n, n))
    for (i, j) in itertools.product(range(n), range(n)):
        if A[i, j]: W[i, j] = A[i, j] / (A[i, j] + A[j, i])

    # Compute a transition matrix P whose non-diagonal entries are proportional
    # to W but where every row sums to exactly 1.  To do this, we first compute
    # the maximum sum of any row of W excluding the diagonal entry.
    w_max = max(sum(W[i, j] for j in range(n) if j != i) for i in range(n))

    # Now define the transition matrix P by dividing all non-diagonal entries
    # by w_max and setting the diagonal entry to one minus the sum of the
    # non-diagonal entries.  Note that w_max has been chosen to make the
    # diagonal entries as small as possible while ensuring that no value is
    # negative.  This maximizes the convergence rate in the loop below.
    P = W / w_max
    for i in range(n):
        P[i, i] = 1 - sum(P[i, k] for k in range(n) if k != i)

    # If n is large enough, it is more efficient in the loop below to use
    # a sparse representation for the matrix P.
    if n >= 250: P = scipy.sparse.csr_array(P)

    # Finally, compute the stationary distribution of the Markov chain defined
    # by the transition matrix P.  We start with an arbitrary distribution
    # "scores" and iterate by applying the transition matrix repeatedly.
    prev_scores = np.ones(n) / n
    for iter in range(max_iters):
        scores = prev_scores @ P
        if np.sum(np.abs(scores - prev_scores)) < tol: break
        prev_scores = scores

    global total_iters
    total_iters += iter + 1
    return scores


def tarjans_scc(adjacency_matrix: np.ndarray) -> List[List[int]]:
    """
    Find strongly connected components using Tarjan's algorithm.

    Args:
        adjacency_matrix: n x n matrix where A[i,j] > 0 indicates edge from i to j

    Returns:
        List of strongly connected components, each component is a list of node indices.
        Components are returned in reverse topological order.
    """
    n = adjacency_matrix.shape[0]

    # Build adjacency list from matrix
    adj_list: Dict[int, List[int]] = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(n):
            if adjacency_matrix[i, j] > 0 and i != j:
                adj_list[i].append(j)

    # Tarjan's algorithm state
    index_counter = [0]
    stack: List[int] = []
    lowlink: Dict[int, int] = {}
    index: Dict[int, int] = {}
    on_stack: Set[int] = set()
    components: List[List[int]] = []

    def strongconnect(v: int):
        # Set the depth index for v to the smallest unused index
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        # Consider successors of v
        for w in adj_list[v]:
            if w not in index:
                # Successor w has not yet been visited; recurse on it
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                # Successor w is in stack and hence in the current SCC
                lowlink[v] = min(lowlink[v], index[w])

        # If v is a root node, pop the stack and create an SCC
        if lowlink[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.append(w)
                if w == v:
                    break
            components.append(component)

    # Find SCCs for all nodes
    for v in range(n):
        if v not in index:
            strongconnect(v)

    return components


def add_comparison(i, j, A):
    """
    Adds a comparison between nodes i and j to the comparison matrix A by
    updating the weights A_ij and A_ji approriately.

    Nodes are preferred in proportion to their numerical value plus one.  So
    for example, node 4 is preferred to node 6 with probability 5/(5+7)
    whereas node 6 is preferred to node 4 with probability 7/(7+5).
    """
    # Weight nodes according to the node value plus one.  Zero node weights
    # should be avoided since arcs to such nodes will never be followed in a
    # random walk and hence do not contribute towards the graph connectivity.
    w = (j + 1) / (i + j + 2)
    A[i, j] += w
    A[j, i] += 1 - w

def make_comparison_matrix(n, extra_comparisons=0):
    """
    Generates a comparison matrix containing n - 1 random comparisons that
    form a spanning tree (thus ensuring graph connectivity), plus an additional
    "extra_comparisons" random comparisons.  A given pair of nodes may be
    compared more than once, in which case the comparison data is summed.

    Returns an n x n matrix "A" where A_ij / (A_ij + A_ji) represents the
    fraction of times that node i was preferred to node j
    """
    # First build a random spanning tree.
    result = np.zeros((n, n))
    perm = random.sample(range(n), n)
    for k in range(1, n):
        i = random.choice(perm[:k])
        j = perm[k]
        add_comparison(i, j, result)

    # Then add any extra comparisons requested.
    for _ in range(extra_comparisons):
        i = random.randrange(n)
        j = (i + 1 + random.randrange(n - 1)) % n
        add_comparison(i, j, result)

    return result

def run_test(n, extra_comparisons):
    scores = rank_centrality(make_comparison_matrix(n, extra_comparisons))

    # Sort by score, high to low, and print results.
    for i in sorted(range(n), key=lambda i : scores[i], reverse=True):
        # The scaled score of item i is expected to be i + 1.
        scaled_score = scores[i] * n * (n + 1) / 2
        print(f'{i}: {scores[i]:.4f} ({scaled_score:.4f})')


def compute_rankings_from_state(
    state,
    hashtag: str,
    attribute: str
) -> List[Tuple[str, float, int, int]]:
    """
    Compute rankings from a reducer State object for a specific hashtag and attribute.

    Rankings are computed per-hashtag per-attribute. Items are filtered by hashtag,
    votes are filtered by attribute. The graph is analyzed for strongly connected
    components, and each component is ranked separately.

    Args:
        state: A State object from the reducer with items and votes
        hashtag: The hashtag to filter items by
        attribute: The attribute to filter votes by

    Returns:
        List of (item_title, score, rank, component_id) tuples sorted by component
        and rank within component (best first). Returns empty list if no items or votes.

        component_id groups items that have been compared (directly or transitively).
        Items with different component_ids have never been compared and thus cannot
        be ranked relative to each other.
    """
    from src.reducer import State

    if not state.items:
        return []

    # Filter items by hashtag
    filtered_items = {
        title: record
        for title, record in state.items.items()
        if hashtag in record.hashtags
    }

    if not filtered_items:
        return []

    # Filter votes by attribute and ensure both items are in filtered set
    filtered_votes = [
        vote for vote in state.votes
        if vote.attribute == attribute
        and vote.item1 in filtered_items
        and vote.item2 in filtered_items
    ]

    if not filtered_votes:
        # No votes for this attribute/hashtag combination
        # All items are unranked singletons
        return [
            (title, 1.0 / len(filtered_items), 1, i)
            for i, title in enumerate(sorted(filtered_items.keys()))
        ]

    # Build mapping from item titles to indices
    item_titles = sorted(filtered_items.keys())
    title_to_idx = {title: i for i, title in enumerate(item_titles)}
    n = len(item_titles)

    # Build comparison matrix from filtered votes
    A = np.zeros((n, n))
    for vote in filtered_votes:
        i = title_to_idx[vote.item1]
        j = title_to_idx[vote.item2]
        # Vote says item1 is better than item2 with ratio_left:ratio_right
        # So A[j,i] (how much i is preferred to j) gets ratio_left
        # And A[i,j] (how much j is preferred to i) gets ratio_right
        A[j, i] += vote.ratio_left
        A[i, j] += vote.ratio_right

    # Find strongly connected components
    components = tarjans_scc(A)

    # Rank each component separately
    results = []
    for component_id, component_indices in enumerate(components):
        if len(component_indices) == 1:
            # Singleton component - single item with no comparisons
            idx = component_indices[0]
            title = item_titles[idx]
            results.append((title, 1.0, 1, component_id))
        else:
            # Multi-item component - compute rankings
            # Build subgraph for this component
            component_size = len(component_indices)
            idx_map = {old_idx: new_idx for new_idx, old_idx in enumerate(component_indices)}
            A_sub = np.zeros((component_size, component_size))

            for i, old_i in enumerate(component_indices):
                for j, old_j in enumerate(component_indices):
                    A_sub[i, j] = A[old_i, old_j]

            # Compute rankings for this component
            try:
                scores = rank_centrality(A_sub)
            except Exception:
                # If ranking fails, assign equal scores
                scores = np.ones(component_size) / component_size

            # Sort by score within component
            sorted_component_indices = sorted(
                range(component_size),
                key=lambda i: scores[i],
                reverse=True
            )

            for rank, sub_idx in enumerate(sorted_component_indices, start=1):
                original_idx = component_indices[sub_idx]
                title = item_titles[original_idx]
                score = scores[sub_idx]
                results.append((title, score, rank, component_id))

    return results


# Example usage
if __name__ == '__main__':
    if not len(sys.argv) in range(2, 5):
        print(f'Usage: {sys.argv[0]} num_items [extra_comparisons [iters]]')
        sys.exit(-1)

    n = int(sys.argv[1])
    extra_comparisons = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for _ in range(iters):
        run_test(n, extra_comparisons)
    print(f'Total iterations: {total_iters}')
