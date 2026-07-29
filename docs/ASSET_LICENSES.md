# Asset licence manifest

## Purpose

Prevent unlicensed avatars, animations, textures, voices and generated derivatives from shipping.

## Decision

No asset is loaded by a release build unless status is `approved` and the record includes creator, canonical source, exact licence/embedded VRM terms, permitted avatar use, modification, redistribution, commercial use, attribution, verification date, SHA-256, local path/object key and verifier. Screenshots/PDF evidence should be stored privately if the licence page can change.

| Asset | Creator/source | Licence / uses | Modify | Redistribute | Attribution | Verified | SHA-256 | Status/notes |
|---|---|---|---|---|---|---|---|---|
| `5447297406763866907.vrm` | unknown in repository | unknown | unknown | unknown | unknown | not verified | `64164cf1c78df9eb1dd8ab812b2ab679fda1d94386cfe77a5df1f8e9c9b7a795` | **quarantined; do not load/ship** |
| PerfectSync female reference VRM | hinzka repository README, local extracted copy | README invites use as source data; exact embedded VRM terms still require inspection | unverified | unverified | unverified | local README read 2026-07-30 | `36d6d242999d580bd0d3bcd8656bb2d4d5d4839f187d8198226bda905e1d9114` | **quarantined reference only** |
| PerfectSync male reference VRM | hinzka repository README, local extracted copy | README invites use as source data; exact embedded VRM terms still require inspection | unverified | unverified | unverified | local README read 2026-07-30 | `7526838f4a45086a1d0abb23e9f38ad3f0103889f1efa70d2605ef25e7e6ef99` | **quarantined reference only** |
| AnimationClipToVrma code | Baku Dreameater, local `LICENSE` | MIT for code except separately noted model-dependent resources | yes | yes with notice | retain MIT notice | 2026-07-30 | calculate during intake | code reference; bundled model separate |
| `AvatarSample_A` bundled in Unity sample | VRoid Hub source linked by sample README | own embedded VRM licence, not MIT | inspect | inspect | inspect | not verified online | `82754e287e0b26b5d7a1fd223ed0fd5debcabed81f36549fb2c16b201f3e5ca9` | **quarantined** |
| future HINAA female/male | original/commissioned | written agreement required | required | release-specific | agreed | pending | pending | final identity, post-prototype |

Generated VRMA may embed reference-avatar skeletal information. Record both source motion and reference avatar terms; use converter mode/reference model whose redistribution permits the resulting file. Mixamo or any other motion is approved only after saving current official terms and source identifiers on acquisition date.

### Intake checklist

1. Preserve original filename/source URL/receipt and embedded VRM metadata.
2. Hash file; malware/format/complexity scan in quarantine.
3. Verify creator authority and all use columns; ambiguous means reject.
4. Record modifications/derivatives and required notices.
5. Optimize only a working copy; retain lineage/checksums.
6. Reverify before public/demo redistribution and yearly for hosted links.

## Alternatives considered

Assuming “downloadable” means redistributable is legally unsafe. Attribution alone does not cure missing permission.

## Reasoning

Asset-specific proof is required because repository/code licences do not automatically cover bundled VRMs or generated animations.

## Risks

Embedded terms and source pages can conflict/change. Use the most restrictive interpretation and replace unclear assets.

## Acceptance criteria

Release asset audit has zero unknown fields; build manifest contains only approved hashes; final characters are original/commissioned and not derivative of copyrighted anime identities.
