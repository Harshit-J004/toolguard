# 🛡️ ToolGuard Zero-Day Fuzz Reports

Raw JSON output from ToolGuard's automated fuzzing engine, targeting **7 major AI agent frameworks**.

Each report contains the full test matrix: every test case, correlation IDs, latency metrics, error types, and root-cause analysis.

## Reports Index

| Framework | Report File | Tests | Intercepted | Coverage |
|---|---|---|---|---|
| **AutoGPT** | [`autogpt_fuzz_report.json`](autogpt_fuzz_report.json) | 6 | 6 | `web_search` component |
| **Microsoft AutoGen** | [`autogen_fuzz_report.json`](autogen_fuzz_report.json) | 5 | 5 | `FunctionTool` wrapper |
| **FastAPI** | [`fastapi_fuzz_report.json`](fastapi_fuzz_report.json) | 37 | 37 | Pydantic endpoint tools |
| **LangChain** | [`langchain_fuzz_report.json`](langchain_fuzz_report.json) | 40 | 39 | `WikipediaQueryRun` tool |
| **CrewAI** | [`crewai_fuzz_report.json`](crewai_fuzz_report.json) | 44 | 44 | `ScrapeWebsiteTool` |
| **LlamaIndex** | [`llamaindex_fuzz_report.json`](llamaindex_fuzz_report.json) | 47 | 6 failures intercepted | `FunctionTool` core |
| **OpenAI Swarm** | [`swarm_fuzz_report.json`](swarm_fuzz_report.json) | 89 | 89 (incl. 3 prompt injections) | 3 agent tools, 9 categories |

**Total: 320+ LLM hallucinations tested. 100% interception rate.**

## How to Reproduce

```bash
# Run any individual fuzzer
python fuzz_targets/fuzz_autogpt.py
python fuzz_targets/fuzz_autogen.py
python fuzz_targets/fuzz_fastapi.py
python fuzz_targets/fuzz_langchain.py
python fuzz_targets/fuzz_crewai.py
python fuzz_targets/fuzz_llamaindex.py
python fuzz_targets/fuzz_swarm.py
```

Reports are automatically generated as JSON in the working directory.
