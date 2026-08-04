# Specification Quality Checklist: Supervised HIL Validation and Handoff

**Purpose**: Validate that the HIL requirements are complete, unambiguous, safe, measurable, and ready for planning  
**Created**: 2026-08-05  
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] CHK001 Are physical outcomes described as operator value and acceptance evidence rather than implementation claims? [Clarity]
- [x] CHK002 Are all mandatory template sections complete and free of placeholder text? [Completeness]
- [x] CHK003 Is the distinction between tonight's offline work and later physical execution explicit throughout? [Consistency, Spec §Verification Boundary]
- [x] CHK004 Is the procedure understandable to the operator, vision teammate, and Skill integrator? [Audience]

## Requirement Completeness

- [x] CHK005 Are read-only identity, deployment, configuration, ROS graph, ownership, scan, target, and estop preflight requirements all specified? [Completeness, Spec §FR-001-FR-003]
- [x] CHK006 Are proposal contents and the single-use nearby-operator `走` gate defined for every non-zero action? [Completeness, Spec §FR-004-FR-006]
- [x] CHK007 Are minimum-command, all direction-sign, observed-motion, and stop-evidence requirements specified? [Completeness, Spec §FR-007-FR-009]
- [x] CHK008 Are directional lidar and persistent-estop/reset acceptance requirements complete? [Completeness, Spec §FR-010-FR-011]
- [x] CHK009 Are visual target, calibration, correction, failure, obstacle, cancellation, timeout, and arrival scenarios defined? [Completeness, Spec §FR-013-FR-015]
- [x] CHK010 Are evidence, case status, deployment, rollback, and team-handoff requirements complete? [Completeness, Spec §FR-016-FR-021]

## Requirement Clarity

- [x] CHK011 Is authorization explicitly non-transferable, non-persistent, and invalidated by any proposal/context change? [Clarity, Spec §FR-005 and Edge Cases]
- [x] CHK012 Are the constitutional speed/duration bounds and smaller first-test defaults quantified with units? [Clarity, Spec §FR-007]
- [x] CHK013 Is lidar acceptance defined per enabled direction with measurable distance, freshness, and valid-sample evidence? [Clarity, Spec §FR-010]
- [x] CHK014 Is arrival evidence explicitly independent of open-loop odometry and tied to configured tolerances? [Clarity, Spec §FR-015]
- [x] CHK015 Are evidence statuses and verification levels defined without ambiguous partial-pass promotion? [Clarity, Spec §FR-017 and §FR-021]

## Requirement Consistency

- [x] CHK016 Do the motion proposal, operator gate, emergency stop, and retry rules agree across stories, requirements, and edge cases? [Consistency]
- [x] CHK017 Do deployment and rollback requirements preserve the manifest-only boundary from Spec 003? [Consistency, Spec §FR-018-FR-019]
- [x] CHK018 Are source, offline, and HIL evidence kept distinct in requirements and measurable outcomes? [Consistency, Spec §Verification Boundary]
- [x] CHK019 Do all acceptance paths preserve forbidden-interface and secret-handling constraints? [Consistency, Spec §FR-022]

## Acceptance Criteria Quality

- [x] CHK020 Can every success criterion be evaluated from counts, case records, measurements, or artifact links? [Measurability, Spec §SC-001-SC-010]
- [x] CHK021 Does each user story have an independent test and concrete Given/When/Then outcomes? [Acceptance Criteria]
- [x] CHK022 Does global completion require all mandatory cases in one matching robot/revision/configuration context? [Acceptance Criteria, Spec §FR-021]

## Scenario and Edge-Case Coverage

- [x] CHK023 Are primary, exception, recovery, cancellation, rollback, and handoff flows all represented? [Coverage]
- [x] CHK024 Are reboot, redeploy, configuration/sensor changes, stale time, low battery, physical obstruction, and partial-session cases addressed? [Coverage, Edge Cases]
- [x] CHK025 Are ambiguity, silence, remote approval, retries, and expired authorization explicitly treated as no authorization? [Coverage, Edge Cases]
- [x] CHK026 Are evidence invalidation and non-transfer across robot/revision/configuration contexts specified? [Coverage, Edge Cases]

## Dependencies and Boundaries

- [x] CHK027 Are Specs 001-003, the vision contract, calibration, physical test area, and recording device documented as dependencies? [Dependency, Spec §Assumptions]
- [x] CHK028 Are mechanical-arm, navigation, grasp, Skill orchestration, unattended motion, and tonight's board access explicitly excluded? [Scope, Spec §Out of Scope]
- [x] CHK029 Are all physical claims reserved for supervised HIL rather than mock, source, shell, odometry, or prior-session evidence? [Boundary, Spec §Verification Boundary]
- [x] CHK030 Are there no `[NEEDS CLARIFICATION]`, TODO, synthetic measurement, or guessed production-value placeholders? [Completeness]

## Notes

- Review iteration 1: 30/30 requirements-quality checks passed.
- HIL task checkboxes created later remain intentionally open; this checklist approves requirement quality only.
