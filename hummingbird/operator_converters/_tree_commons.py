# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

import copy
import numpy as np

from ._tree_implementations import TreeImpl


"""
Collections of classes and functions shared among all tree converters.
"""


class Node:
    """
    Class defining a tree node.
    """

    def __init__(self, id=None):
        """
        :param id: A unique ID for the node
        :param left: The id of the left node
        :param right: The id of the right node
        :param feature: The feature used to make a decision (if not leaf node, ignored otherwise)
        :param threshold: The threshold used in the decision (if not leaf node, ignored otherwise)
        :param value: The value stored in the leaf (ignored if not leaf node).
        """
        self.id = id
        self.left = None
        self.right = None
        self.feature = None
        self.threshold = None
        self.value = None


class TreeParameters:
    """
    Class containing a convenient in-memory representation of a decision tree.
    """

    def __init__(self, lefts, rights, features, thresholds, values):
        """
        :param lefts: The id of the left nodes
        :param rights: The id of the right nodes
        :param feature: The features used to make decisions
        :param thresholds: The thresholds used in the decisions
        :param values: The value stored in the leaves
        """
        self.lefts = lefts
        self.rights = rights
        self.features = features
        self.thresholds = thresholds
        self.values = values


def _find_max_depth(tree_parameters):
    """
    Function traversing all trees in sequence and returning the maximum depth.
    """
    depth = 0

    for tree in tree_parameters:
        tree = copy.deepcopy(tree)

        lefts = tree.lefts
        rights = tree.rights

        ids = [i for i in range(len(lefts))]
        nodes = list(zip(ids, lefts, rights))

        nodes_map = {0: Node(0)}
        current_node = 0
        for i, node in enumerate(nodes):
            id, left, right = node

            if left != -1:
                l_node = Node(left)
                nodes_map[left] = l_node
            else:
                lefts[i] = id
                l_node = -1

            if right != -1:
                r_node = Node(right)
                nodes_map[right] = r_node
            else:
                rights[i] = id
                r_node = -1

            nodes_map[current_node].left = l_node
            nodes_map[current_node].right = r_node

            current_node += 1

        depth = max(depth, _find_depth(nodes_map[0], -1))

    return depth


def _find_depth(node, current_depth):
    """
    Recursive function traversing a tree and returning the maximum depth.
    """
    if node.left == -1 and node.right == -1:
        return current_depth + 1
    elif node.left != -1 and node.right == -1:
        return _find_depth(node.l, current_depth + 1)
    elif node.right != -1 and node.left == -1:
        return _find_depth(node.r, current_depth + 1)
    elif node.right != -1 and node.left != -1:
        return max(_find_depth(node.left, current_depth + 1), _find_depth(node.right, current_depth + 1))


def get_tree_implementation_by_config_or_depth(extra_config, max_depth, low=3, high=10):
    """
    Utility function used to pick the tree implementation based on input parameters and heurstics.
    The current heuristic is such that GEMM <= low < PerfTreeTrav <= high < TreeTrav
    :param max_depth: The maximum tree-depth found in the tree model.
    :param low: the maximum depth below which GEMM strategy is used
    :param high: the maximum depth for which PerfTreeTrav strategy is used
    """
    if "tree_implementation" not in extra_config:
        if max_depth is not None and max_depth <= low:
            return TreeImpl.gemm
        elif max_depth is not None and max_depth <= high:
            return TreeImpl.tree_trav
        else:
            return TreeImpl.perf_tree_trav

    if extra_config["tree_implementation"] == "gemm":
        return TreeImpl.gemm
    elif extra_config["tree_implementation"] == "tree_trav":
        return TreeImpl.tree_trav
    elif extra_config["tree_implementation"] == "perf_tree_trav":
        return TreeImpl.perf_tree_trav
    else:
        raise ValueError("Tree implementation {} not found".format(extra_config))


def get_tree_params_and_type(tree_infos, get_tree_parameters, extra_config):
    """
    Populate the parameters from the trees and pick the tree implementation strategy.
    """
    tree_parameters = [get_tree_parameters(tree_info) for tree_info in tree_infos]
    max_depth = max(1, _find_max_depth(tree_parameters))
    tree_type = get_tree_implementation_by_config_or_depth(extra_config, max_depth)

    return tree_parameters, max_depth, tree_type


def get_parameters_for_sklearn_common(tree_info):
    """
    Parse sklearn-based trees, including
    SklearnRandomForestClassifier/Regressor and SklearnGradientBoostingClassifier
    """
    tree = tree_info
    lefts = tree.tree_.children_left
    rights = tree.tree_.children_right
    features = tree.tree_.feature
    thresholds = tree.tree_.threshold
    values = tree.tree_.value

    return TreeParameters(lefts, rights, features, thresholds, values)


def get_parameters_for_tree_trav_common(lefts, rights, features, thresholds, values):
    """
    Common functions used by all tree algorithms to generate the parameters according to the tree_trav strategies.
    """
    if len(lefts) == 1:
        # Model creating tree with just a single leaf node. We transform it
        # to a model with one internal node.
        lefts = [1, -1, -1]
        rights = [2, -1, -1]
        features = [0, 0, 0]
        thresholds = [0, 0, 0]
        values = [np.array([0.0]), values[0], values[0]]

    ids = [i for i in range(len(lefts))]
    nodes = list(zip(ids, lefts, rights, features, thresholds, values))

    # Refactor the tree parameters in the proper format.
    nodes_map = {0: Node(0)}
    current_node = 0
    for i, node in enumerate(nodes):
        id, left, right, feature, threshold, value = node

        if left != -1:
            l_node = Node(left)
            nodes_map[left] = l_node
        else:
            lefts[i] = id
            l_node = -1
            feature = -1

        if right != -1:
            r_node = Node(right)
            nodes_map[right] = r_node
        else:
            rights[i] = id
            r_node = -1
            feature = -1

        nodes_map[current_node].left = l_node
        nodes_map[current_node].right = r_node
        nodes_map[current_node].feature = feature
        nodes_map[current_node].threshold = threshold
        nodes_map[current_node].value = value

        current_node += 1

    lefts = np.array(lefts)
    rights = np.array(rights)
    features = np.array(features)
    thresholds = np.array(thresholds)
    values = np.array(values)

    return [nodes_map, ids, lefts, rights, features, thresholds, values]


def get_parameters_for_tree_trav_sklearn(lefts, rights, features, thresholds, values):
    """
    This function is used to generate tree parameters for sklearn trees accordingy to the tree_trav strategy.
    Includes SklearnRandomForestClassifier/Regressor and SklearnGradientBoostingClassifier
    """
    features = [max(x, 0) for x in features]
    values = np.array(values)
    if len(values.shape) == 3:
        values = values.reshape(values.shape[0], -1)
    if values.shape[1] > 1:
        values /= np.sum(values, axis=1, keepdims=True)

    return get_parameters_for_tree_trav_common(lefts, rights, features, thresholds, values)


def get_parameters_for_gemm_common(lefts, rights, features, thresholds, values, n_features):
    """
    Common functions used by all tree algorithms to generate the parameters according to the GEMM strategy.
    """
    if len(lefts) == 1:
        # Model creating trees with just a single leaf node. We transform it
        # to a model with one internal node.
        lefts = [1, -1, -1]
        rights = [2, -1, -1]
        features = [0, 0, 0]
        thresholds = [0, 0, 0]
        values = [np.array([0.0]), values[0], values[0]]

    values = np.array(values)
    weights = []
    biases = []

    # First hidden layer has all inequalities.
    hidden_weights = []
    hidden_biases = []
    for left, feature, thresh in zip(lefts, features, thresholds):
        if left != -1:
            hidden_weights.append([1 if i == feature else 0 for i in range(n_features)])
            hidden_biases.append(thresh)
    weights.append(np.array(hidden_weights).astype("float32"))
    biases.append(np.array(hidden_biases).astype("float32"))

    n_splits = len(hidden_weights)

    # Second hidden layer has ANDs for each leaf of the decision tree.
    # Depth first enumeration of the tree in order to determine the AND by the path.
    hidden_weights = []
    hidden_biases = []

    path = [0]
    n_nodes = len(lefts)
    visited = [False for _ in range(n_nodes)]

    class_proba = []
    nodes = list(zip(lefts, rights, features, thresholds, values))

    while True and len(path) > 0:
        i = path[-1]
        visited[i] = True
        left, right, feature, threshold, value = nodes[i]
        if left == -1 and right == -1:
            vec = [0 for _ in range(n_splits)]
            # Keep track of positive weights for calculating bias.
            num_positive = 0
            for j, p in enumerate(path[:-1]):
                num_leaves_before_p = list(lefts[:p]).count(-1)
                if path[j + 1] in lefts:
                    vec[p - num_leaves_before_p] = 1
                    num_positive += 1
                elif path[j + 1] in rights:
                    vec[p - num_leaves_before_p] = -1
                else:
                    raise RuntimeError("Inconsistent state encountered while tree translation.")

            if values.shape[-1] > 1:
                class_proba.append((values[i] / np.sum(values[i])).flatten())
            else:
                # We have only a single value. e.g., GBDT
                class_proba.append(values[i].flatten())

            hidden_weights.append(vec)
            hidden_biases.append(num_positive)
            path.pop()
        elif not visited[left]:
            path.append(left)
        elif not visited[right]:
            path.append(right)
        else:
            path.pop()

    weights.append(np.array(hidden_weights).astype("float32"))
    biases.append(np.array(hidden_biases).astype("float32"))

    # OR neurons from the preceding layer in order to get final classes.
    weights.append(np.transpose(np.array(class_proba).astype("float32")))
    biases.append(None)

    return weights, biases
