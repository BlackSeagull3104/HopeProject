# Retrieval v3 experiment

All 60 entries and 80 questions are fictional and hand-authored in `corpus.py`.
The corpus and relevance judgments were authored before running retrieval. They
are a small diagnostic set, not a statistically representative product evaluation.
Activity questions exclude explicit nonparticipation/plans; exact term questions
include mentions even when negated. Graded relevance is not used.

`baseline.json` is the unmodified v2 implementation at `061a909`:
literal = whole-query literal candidate search using existing diary ranking;
v2_alias = existing assistant `query_terms` plus existing retrieval/ranking.
Literal is not advertised as the whole Local Search UI (which sorts by date).
Macro recall divides retrieved relevant IDs by all judged relevant IDs per query.
MRR considers all returned candidates, not just five. Precision always divides by k.
Language and date groups overlap the four intent classes.

Run `.venv/Scripts/python.exe benchmarks/retrieval_v3/evaluate.py --output PATH`.
Every report includes a hash of the serialized dataset. Do not overwrite the
baseline when changing production retrieval. A Windows SQLite connection cleanup
bug in the first harness run was fixed before a baseline could be saved; judgments
were not changed. No secrets, personal archives, or live AI calls are required.

Future strategies must use these same queries/judgments. Any mocked rewrite result
is a pipeline experiment, NOT a measured provider quality result. Embedding model
files/dependencies belong under ignored `build/ai-v3`, never production requirements.
