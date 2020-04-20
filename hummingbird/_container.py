# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

import torch


class PyTorchBackendModel(torch.nn.Module):
    """
    Container for a model compiled for the PyTorch Backend.
    """

    def __init__(self, input_names, output_names, operator_map, topology, extra_config):
        super(PyTorchBackendModel, self).__init__()
        self.input_names = input_names
        self.output_names = output_names
        self.operator_map = torch.nn.ModuleDict(operator_map)
        self.topology = topology
        self.extra_config = extra_config

    def forward(self, *pytorch_inputs):
        with torch.no_grad():
            pytorch_inputs = [*pytorch_inputs]
            variable_map = {}

            # Maps data inputs to the expected variables.
            for i, input_name in enumerate(self.input_names):
                variable_map[input_name] = pytorch_inputs[i]

            # Evaluate all the operators in the topology by properly wiring inputs \ outputs
            for operator in self.topology.topological_operator_iterator():
                pytorch_op = self.operator_map[operator.full_name]
                pytorch_outputs = pytorch_op(*(variable_map[input] for input in operator.input_full_names))

                if len(operator.output_full_names) == 1:
                    variable_map[operator.output_full_names[0]] = pytorch_outputs
                else:
                    for i, output in enumerate(operator.output_full_names):
                        variable_map[output] = pytorch_outputs[i]

            # Prepare and return the output.
            if len(self.output_names) == 1:
                return variable_map[self.output_names[0]]
            else:
                return list(variable_map[output_name] for output_name in self.output_names)
