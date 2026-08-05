# Mandatory HIL Case Matrix

Every non-zero row requires the [supervision contract](supervision.md). Case IDs remain stable across attempts.

| Gate | Case ID | Case | Non-zero | Required evidence |
|---|---|---|---|---|
| Staging | DEP-001 | Backup, manifest-only candidate copy, modes/digests, read-only smoke | No | deployment and smoke record |
| Config | CFG-001 | Validate v2 motion-only configuration with approach explicitly disabled | No | validator result and capability record |
| Preflight | PRE-001 | Board/revision/manifest/config/runtime identity | No | session identity and digests |
| Preflight | PRE-002 | ROS graph/topic/type/owner snapshot | No | publishers, subscribers, types |
| Preflight | PRE-003 | Fresh scan/target and persistent-estop status | No | dual timestamps and validation |
| Preflight | PRE-004 | Read-only `/cmd_vel` observer reports type, graph, cadence, and zero/non-zero counts | No | observer JSON |
| Stop | STOP-001 | Explicit zero sequence under normal readiness | No | result and zero publish count |
| Stop | STOP-002 | Stop attempt under degraded readiness | No | degraded reason and zero attempt |
| Primitive | DIR-XP | Forward x sign | Yes | proposal, video, distance, zeros |
| Primitive | DIR-XN | Backward x sign | Yes | proposal, video, distance, zeros |
| Primitive | DIR-YP | Left y sign | Yes | proposal, video, distance, zeros |
| Primitive | DIR-YN | Right y sign | Yes | proposal, video, distance, zeros |
| Primitive | DIR-AZP | Counterclockwise sign | Yes | proposal, video, angle, zeros |
| Primitive | DIR-AZN | Clockwise sign | Yes | proposal, video, angle, zeros |
| Ownership | OWN-001 | Project lock contention rejects motion | No | two-process results, no non-zero |
| Ownership | OWN-002 | Unexpected publisher blocks ownership | No | graph snapshots and result |
| Lidar | SCAN-F-CLEAR/BLOCK | Forward clear and blocked behavior | Conditional | sector samples and stop/reject |
| Lidar | SCAN-B-CLEAR/BLOCK | Backward clear and blocked behavior | Conditional | sector samples and stop/reject |
| Lidar | SCAN-L-CLEAR/BLOCK | Left clear and blocked behavior | Conditional | sector samples and stop/reject |
| Lidar | SCAN-R-CLEAR/BLOCK | Right clear and blocked behavior | Conditional | sector samples and stop/reject |
| Estop | ESTOP-001 | Latch persists across process exit | Conditional | state before/after new process |
| Estop | ESTOP-002 | Reset rejects stale/blocked scans | No | reset result and scan sequence |
| Estop | ESTOP-003 | Reset accepts consecutive all-clear scans | No | frame count, result, no non-zero |
| Target | TGT-001 | Stationary target contract/calibration inspection | No | target JSON and provenance |
| Approach | APP-ROT-001 | One rotation correction | Yes | before/after target, proposal, video |
| Approach | APP-TRANS-001 | One translation correction | Yes | before/after target, proposal, video |
| Approach | APP-LOSS-001 | Target loss stops | Conditional | state transition and zeros |
| Approach | APP-STALE-001 | Stale/invalid target rejects/stops | Conditional | invalid input and result |
| Approach | APP-OBS-001 | Obstacle interruption stops | Conditional | scan, state transition, zeros |
| Approach | APP-CANCEL-001 | Operator cancellation stops | Conditional | cancellation and zeros |
| Approach | APP-TIME-001 | Timeout/iteration bound stops | Conditional | timing/iteration and zeros |
| Approach | APP-ARRIVE-001 | Bounded approach reaches measured tolerance | Yes | full trace and independent measurement |
| Acceptance | DEP-ACCEPT-001 | Promote staged candidate only after mandatory HIL evidence passes | No | traceability and acceptance record |
| Rollback | RBK-001 | Audit exact recovery; restore and re-preflight whenever a trigger fired | No | recovery audit or executed rollback record |
| Handoff | HAND-001 | Skill integrator package audit | No | completed handoff record |

“Conditional” means the case may create non-zero output before its trigger; if so, the proposal gate applies. Required failure-mode cases pass only when the expected safe rejection/stop occurs.
