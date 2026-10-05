# Translation evaluation input

No translation benchmark or model output is currently included. The project’s job-posting corpus contains individual German and English advertisements, not aligned translations, and the skill evaluation labels contain no translation references. Do not treat separate ads as parallel text.

When rights and review permit, place local evaluation records in `pairs.jsonl`. One JSON object per line:

```json
{"segment_id":"stable-id","direction":"de-en","source":"...","reference":"...","hypothesis":"..."}
```

`direction` must be `de-en` or `en-de`. `reference` should be an independently produced human translation; `hypothesis` must identify the output of a named translation system in the dataset documentation. Keep personally identifying information out. The audit reports counts and a file checksum, never source, reference, or hypothesis text.

FLORES+ is a possible public general-domain benchmark and is licensed CC BY-SA 4.0. It does not measure job-ad translation quality, and its share-alike terms need review before redistribution. For job-domain claims, use text with a clear right to translate and publish, create a held-out set with independent human references, and document adjudication. The OPUS-MT model family is a possible local baseline; verify the exact direction-specific model and license before use. No models or benchmark files are downloaded by this phase.
