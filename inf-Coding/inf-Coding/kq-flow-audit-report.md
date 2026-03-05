# FlowIR Audit Report

- Nodes: **7**
- Edges: **9**
- SCC cycles: **1**

## Layers
- `L0`: inbound
- `L1`: bridge
- `L2`: verify
- `L3`: formal
- `L4`: gate
- `L5`: output
- `L6`: cleanup

## High-Risk Edges
- `gate -> formal` mode=conditional condition=`re-check on caution`

## Cycles (SCC)
- output -> gate -> formal -> verify -> bridge