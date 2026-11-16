# 3.3.3 Infrastructure capacity plans

Infrastructure has no capacity plan of its own yet. No host is shared between
applications, so each application's plan carries its own host against its
ceiling, and this folder indexes them. The form is the
[capacity plan template](../../../docs/templates/capacity-plan.md), and who
writes and reviews each plan is the `capacity-plan` activity in
[1.4](../../../docs/1.4-programme-activities.md).

| Application | Its plan | Hosts it measures |
| --- | --- | --- |
| Tile Lite Elite | [3.1.3](../../tile-lite-elite/3.1.3-capacity-plan/README.md) | production's memory, swap, CPU, disk and journal |
| Dark Portal | [3.2.3](../../dark-portal/3.2.3-capacity-plan/README.md) | production's and non-production's memory, CPU and block storage, and Oracle's Always Free allowances across the account |

Capacity is planned at two levels. Each application's plan has its host's rows
and its own rows (rate limits, bottlenecks, what its users can drive it to). A
hosts' plan of its own starts when a host is first shared by two applications,
and takes each one's footprint from its plan.
