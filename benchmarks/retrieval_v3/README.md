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

## Reproduction after v3

`evaluate.py` now reports `v2_alias` via the preserved `lexical_terms` policy and
`v3_concepts` via the shared production query preparation. Tests compare every
v2 ranking to the frozen baseline, not merely aggregate scores.

Run the offline experiments with the repository Python environment:

```
python benchmarks/retrieval_v3/evaluate.py --output build/ai-v3/current.json
python benchmarks/retrieval_v3/rewrite.py --output build/ai-v3/replay.json
python benchmarks/retrieval_v3/performance.py --output build/ai-v3/performance.json
python benchmarks/retrieval_v3/embedding.py --model build/ai-v3/e5 --output build/ai-v3/embedding.json
```

The embedding command performs no downloads/network access. Before running it,
place these public upstream artifacts in the ignored model directory:

- Repository `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- `onnx/model_qint8_avx512_vnni.onnx` as `model.onnx`; SHA-256 `dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88`.
- `tokenizer.json`; SHA-256 `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`.
- Isolated development dependency `tokenizers==0.22.2` under `build/ai-v3/deps`
  (`python -m pip install --target build/ai-v3/deps --no-deps tokenizers==0.22.2`).
- Experiment used existing `onnxruntime==1.30.0`, CPUExecutionProvider, two threads,
  512-token truncation, attention-masked mean pooling, normalized 384-dimensional
  float32 vectors and query/passage prefixes. No GPU or remote embedding API.

This specific quantized variant ran on the measured Windows Intel CPU. It is not
a compatibility promise for all PCs. The upstream MIT model card is the licensing
reference; nothing here authorizes skipping notices if distributing it later.
Experiments aren't imported by runtime code and are not in packaging dependencies.

## Judgment limitation discovered in review

Frozen q69 (`NLP`, August) labels only d5; d31 on August 31 describes “natural
language processing” and is also relevant under semantic alias interpretation.
Do not silently rewrite the frozen corpus or baseline. The final report calls out
this incomplete judgment; `judgment-sensitivity.json` recomputes metrics with
d31 added without changing any ranking. This is an annotation correction, not a
retrieval improvement. Other broad activity judgments also merit independent review.
