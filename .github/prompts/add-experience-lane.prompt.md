---
name: add-experience-lane
description: Add RecommendationStore persistence + experience transform + historical context for an agent
agent: agent
argument-hint: Agent id (e.g. spark_rca or cluster_tuning) and corpus name
---

# Add an experience / history lane

Mirror `cluster_tuning` / `spark_rca` patterns:

1. Persist via RecommendationStore (`agent_id`, lifecycle statuses) from the **API** host — not from a graph node upserting vectors directly
2. `ExperienceTransform` → `ExperienceDocument` with **open/structural features** (not closed scenario enums; not `job_id` as similarity key)
3. Register transform in domain bootstrap
4. Corpus entry in `config/corpora.yaml`
5. `compose_historical_context`: experience search (dedupe) + same-job store shelf; empty → `"None"`
6. Keep runbooks / guidance RAG in a **separate** prompt field
7. Tests: transform labels/signature; compose lanes; reject/delete indexing behavior as applicable
8. Docs: agent doc + retrieval/recommendation-store notes

Fail soft on empty retrieval. Do not block analyze/recommend when history is missing.
