# Team Alignment — Open Questions for the Group Chat

> 中文版本: [`team-alignment-questions.zh.md`](team-alignment-questions.zh.md) (Paste the Chinese one into the group chat; this English copy is for the formal record.)

> **Status: RESOLVED (2026-05-11)**. All five questions answered by the team. The resolutions are recorded in [`team-interfaces.md`](team-interfaces.md) §"Resolved Decisions" and reflected in [`data-contract.md`](data-contract.md) §6 (label set) and §7 (window params). This file is kept as the historical record of how the decisions were framed.
>
> Summary of resolutions:
>
> | # | Question | Resolution |
> |---|---|---|
> | 1 | Who owns sensor-side feature extraction? | HE Xinhao + YANG Xuanzhi (co-owned, in-process with web BE) |
> | 2 | Is YE Bingli's "back-end driver" the device driver or web BE? | Device-side acquisition driver only |
> | 3 | Where does the model run for midterm? | Edge (Orange Pi), same Python process as web BE |
> | 4 | Label vocabulary? | `normal / unbalance / loose / misaligned / unknown` (closed) |
> | 5 | Window length? | `window_size_s = 0.5`, `window_hop_s = 0.25` |


Copy-paste the message below into the group chat. It lists the small number of decisions the team must lock down before each branch (vision / sensor / model / web) goes too far in a direction that's incompatible with the others.

The goal is **not** to design the system in chat — most of it is already designed in the proposal. The goal is to close the few residual ambiguities that, if left open another two weeks, will cause rework.

---

## Drop-In Message

> Hi team,
>
> Before we all sprint toward the May 26 midterm, can we lock down the following 5 decisions so vision / sensor / model / web don't drift apart? I've started writing the web dashboard against an assumed contract (see `doc/data-contract.md` and `doc/team-interfaces.md` on the repo). If anyone's assumption differs, please flag it now — much cheaper to fix here than at integration time.
>
> **1. Sensor-side feature extraction — who owns it?**
> The schema declares ~30 `sensor_*` columns (see `doc/feature_schema.md`) but no one is explicitly assigned to compute them from STM32 → Orange Pi sensor streams. Without this, every "real" sample will be vision-only and we lose the dual-modal story for the midterm. Proposed deadline: first sensor CSV produced by 2026-05-19.
>
> **2. YE Bingli's "back-end driver" — device driver or web back-end?**
> I (HE Xinhao) am writing the web back-end (FastAPI under `src/project_course/api/`). My assumption is YE Bingli's "back-end driver" means the **device-side driver software** between STM32 and Orange Pi, not a web back-end. Bingli, please confirm — if it's actually the web side, we have overlap to split.
>
> **3. Model serving for the midterm demo — edge or web?**
> My current assumption: YANG Xuanzhi's model runs on the Orange Pi (edge), and the web dashboard is **display + storage only** (no live inference). If the model should instead be served by the web BE on demand, we need:
> - a new API route (`POST /api/v1/predict`)
> - the data contract must require `predicted_label` / `prediction_confidence` columns
> - one extra week of dev time
> Please confirm so I don't build the wrong thing.
>
> **4. Label vocabulary — agree on a closed set?**
> Proposed: `normal / unbalance / loose / misaligned / unknown` (lowercase ASCII, exact spelling). Filtering, training labels, and the report all depend on us using the same words. If anyone has a stronger taxonomy from the literature, propose it now.
>
> **5. Window length — fixed at 0.5 s?**
> Vision and sensor rows can only be fused if both branches use the same sliding window definition. The proposal mentions Welch sliding windows but doesn't pin a duration. Suggest fixing at 0.5 s with 0.25 s hop for both branches. Vision team / sensor team — does this work given your sample rates (vision 420 fps, sensor ~1.6 kHz)?
>
> If we can answer all five by EOD Wednesday, every branch can keep moving in parallel without integration surprises. Reply in thread so we have a written record.
>
> — HE Xinhao

---

## Why These Five and Not More

There's a lot more we *could* discuss (incremental update API, demo script, data labeling tooling, etc.), but those don't block parallel work this week. Each of the five above can silently invalidate work already in progress, which is why they're in the message and other things aren't.

If you want to discuss the others later, add them to a "next sync" agenda — don't dump them into the chat at the same time, or all five of these will go unanswered.

## After the Chat

Once decisions are locked, update:
- §6 of [`data-contract.md`](data-contract.md) if the label set changes
- [`team-interfaces.md`](team-interfaces.md) §"Open Questions" — strike through resolved items, leave the answer inline
- The reserved columns in [`data-contract.md`](data-contract.md) §8 if predictions become required
