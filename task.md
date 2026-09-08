# Clinical Site Feasibility AI Assistant

A locally runnable service that answers questions about public clinical trial protocols and routes quantitative site-enrollment questions to structured data.

Site feasibility and enrollment forecasting usually mean reading unstructured protocols next to historical site tables. This project joins those sources so a free-text query can return grounded site and protocol answers.

---

### Goals

1. **API backend**: FastAPI JSON service with a health check and a main query endpoint.
2. **Protocol RAG**: Ingest public ClinicalTrials.gov study text and retrieve it to answer eligibility and scientific questions with citations.
3. **Structured-data tool use**: Detect enrollment or site-capacity questions and query SQLite/CSV instead of inventing numbers in free text.
4. **Guardrails**: Validate input, handle model or tool failures, and keep answers tied to retrieved sources.

A chat UI is included for local use. Cloud deploy, GxP controls, and medical advice are out of scope.

---

### Example queries

| Query | Response |
|-------|----------|
| What is the enrollment rate for site XXX? | The monthly enrollment rate for site XXX is 8.3. |
| What is the enrollment rate for site YYY? | I don’t have any information on site YYY. |
| How many active trials are at site XXX? | There are 2 active trials at site XXX. |
| Where should I run my next trials? Please see the attached protocol for additional information. | Based on the attached protocol, you should run your trial at sites YYY and ZZZ for the following reasons: … |

---

### Repository pieces

| Component | Description |
|-----------|-------------|
| **FastAPI app** | Health check, query endpoint, and request/response schema. |
| **Protocol fetcher + ingest** | Downloads public ClinicalTrials.gov JSON, then parses and indexes chunks. |
| **Mock site data** | CSV and SQLite table of synthetic site enrollment attributes. |
| **LLM smoke test** | Optional connectivity check. Swap in any OpenAI-compatible, Anthropic, or local endpoint. |
| **Chat UI** | Vite + React front end that talks to `POST /query`. |

Use only public trial information and the supplied mock site data. Do not commit credentials, real patient data, or secrets.

---

### Design choices

- **Routing** is tool-driven: site lookups, protocol search, both, or a reject. Eligibility language (“enrollment criteria”) stays on the protocol path.
- **Site numbers** come from the database, not the model. Missing or unknown sites abstain.
- **Protocol answers** cite retrieved chunks only.
- **Retrieval** can be FTS, embeddings, or a local vector store; the current path uses SQLite FTS over chunked protocol text.
- **Tool use** is native model function calling (or an equivalent router) that runs a constrained structured-data operation.
- **Failures** surface clearly. Cached protocols and the local site DB are the fallback when an upstream API is down.
- Deep clinical expertise is not assumed. Answers stay inside the public text and mock tables and avoid unsupported clinical conclusions.

Behavior details live in `SPECS.md`. Setup and run commands live in `README.md`.
