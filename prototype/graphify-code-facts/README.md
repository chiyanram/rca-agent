# PROTOTYPE (throwaway): graphify as the Code-facts engine?

Evidence for [Can graphify be the engine behind Code facts for Java services?](https://github.com/chiyanram/rca-agent/issues/45). Not product code.

- `scorecard.py` reads graphify's `graph.json` and scores it fact by fact against the source (regex ground truth + a planted fault).
- `scorecard.txt` is the result for graphify **0.9.104** on:
  - Spring: `spring-projects/spring-petclinic@500158f` + `seeded-fault-petclinic.patch` (NPE in `updatePetDetails`, `log.error` in `processUpdateForm`)
  - Micronaut: `piomin/sample-micronaut-microservices@8547313` (3 services, declarative `@Client`)
  - Azure Functions: `Azure-Samples/azure-functions-samples-java@8d0e26d` (49 `@FunctionName` methods)
- `timings.json` holds measured build / incremental times and operational notes.

## Reproduce

```bash
uv venv gfy && VIRTUAL_ENV=$PWD/gfy uv pip install graphifyy==0.9.104
mkdir repos out && git clone --depth 1 https://github.com/spring-projects/spring-petclinic repos/spring-petclinic   # etc.
env -i PATH=/usr/bin:/bin HOME=$PWD/home GRAPHIFY_QUERY_LOG_DISABLE=1 \
  gfy/bin/graphify extract repos/spring-petclinic --code-only --out out/spring-petclinic
python3 -I scorecard.py out repos timings.json
```

Run on an untrusted repo: own empty dir, `env -i` (no API keys reach it), nothing executed from inside the repo.
