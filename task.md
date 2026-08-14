# CLINICAL SITE FEASIBILITY AI ASSISTANT
## Onsite Exercise Candidate Guide

**Principal Software Engineer (SE7) | Early Clinical Development**

You will architect and build a functional prototype that answers questions about public clinical trial protocols and routes quantitative site-enrollment questions to structured data.

---

### Exercise timing

There will be three “rounds” for a total of 2 hours 45 minutes. You may have up to 3 hours to allow for additional time if necessary.

---

### What you will build

At Roche/Genentech, our Early Clinical Development (ECD) team works to accelerate clinical trial development and bring life-changing medicines to patients faster. A critical bottleneck in early stage trials is rapidly determining **site feasibility** and **patient enrollment forecasting**, which requires the complex analysis of unstructured trial protocols alongside structured historical site data.

Over the next 2 hours (scoping + solo build), you will architect and build a functional, API-first prototype of an **AI Assistant for Clinical Site Feasibility**. It should accept free-text user queries to obtain information on a given site and respond with relevant data.

#### Desired Project Outputs

1. **API backend (priority)**: Expose at least one main JSON endpoint in a clean, executable service. The starter repository uses FastAPI, but an equivalent backend is acceptable.
2. **Protocol RAG**: Ingest and retrieve relevant content from public clinical trial protocol data to answer eligibility and scientific questions with clear grounding or citations.
3. **Structured-data tool use**: Recognize quantitative enrollment or site-capacity questions and invoke some structured database (SQLite/CSV) instead of handling values in free text.
4. **Operational guardrails**: Validate input, handle model/API failures or malformed tool calls, and reduce hallucination risk through source grounding, constrained outputs, or equivalent controls.

#### Example Queries and Responses

| Query | Response |
|-------|----------|
| What is the enrollment rate for site XXX? | The monthly enrollment rate for site XXX is 8.3. |
| What is the enrollment rate for site YYY? | I don’t have any information on site YYY. |
| How many active trials are at site XXX? | There are 2 active trials at site XXX. |
| Where should I run my next trials? Please see the attached protocol for additional information. | Based on the attached protocol, you should run your trial at sites YYY and ZZZ for the following reasons: … |

#### What the starter repository provides

| Component | Description |
|-----------|-------------|
| **FastAPI scaffold** | A running application with a health endpoint. You design and implement the main request/response schema and query endpoint. |
| **Protocol fetcher** | A script that downloads public ClinicalTrials.gov study JSON. Parsing, chunking, indexing, and retrieval are part of your build. |
| **Mock site data** | A script that creates a CSV and SQLite table with site enrollment attributes for tool/function-call queries. |
| **LLM connectivity example** | A provider-specific smoke test. It is illustrative, not a required architecture; use or replace it with an available provider or local model. |

#### Data and Credentials clarification

No Roche or Genentech internal data is required. If you are using the provided Roche/Genentech laptop, an API key for an Roche/Genentech internal LLM provider (Portkey/Galileo) will be provided. Otherwise, we suggest that you obtain your own LLM access elsewhere.

---

### Before the interview

A Roche/Genentech laptop will be provided to you on the day of your interview. However, you may bring your laptop if desired.

- Install Git and make sure your GitHub account can access the private starter repository. **Do not publish interview code in a public repository.**
- Use **VS Code** as the supported interview IDE. Contact the recruiter in advance if you need an alternative editor or accessibility accommodation.
- Install a recent Python 3 environment and the repository dependencies. **Python 3.11 or 3.12 is recommended.**
  - Confirm that the health endpoint runs, public protocol data can be fetched or cached, and the mock site database can be created.
  - Confirm access to an LLM endpoint or local model that you are permitted to use. Do not purchase access specifically for the interview.
- Pre-interview work should be limited to setup and access validation. **Do not implement the solution before the timed exercise begins.**

---

### Interview flow

| Module | Time | Activity | What to expect |
|--------|------|----------|----------------|
| Round 1 | 30 minutes | Kickoff and scoping | Clarify requirements, define the MVP and API contract, and outline the routing/data flow. |
| Round 2 | 90 minutes | Solo build | Implement the working service using the starter repository and the tools you selected. |
| Round 3 | 45 minutes | Demo, review, and defense | Run the API, explain design decisions and guardrails, review commits/code, and respond to a small live change or debugging request. |

#### During the review

Be prepared to run the service, explain the routing and grounding strategy, inspect your Git history, discuss failure modes and production hardening, and make a small code change or debug an issue live.

#### Expected outcome

A locally executable prototype is the primary deliverable. A user interface, cloud deployment, and production or GxP validation is **not required**. Prioritize a complete core flow, clear module boundaries, defensible tradeoffs, and graceful failure behavior.

Use only public trial information and the supplied mock site data. **Do not introduce confidential company information, real patient data, credentials, or secrets into the repository or any external AI tool.**

---

### Candidate Q&A

| Question | Answer |
|----------|--------|
| May I use an AI coding assistant? | Yes. You may use an AI coding assistant and public documentation. You remain responsible for the code, must review generated changes, and should be able to explain every important design decision. |
| Do I have to use the included LLM provider? | No. Use an endpoint or local model available to you. The provider-specific connection script is only a smoke-test example unless the interview team explicitly supplies credentials. |
| Am I required to use a vector database? | No. You are not required to use a vector database. Use whatever retrieval method that works for you. In-memory search, TF-IDF, embeddings, or a local vector store are all reasonable when clearly explained. |
| What qualifies as function calling or tool use? | The system must reliably distinguish structured site-data questions from protocol questions and execute a constrained structured-data operation. Native model tool calling is suitable; a documented equivalent router is acceptable when it preserves that behavior. |
| May I modify the starter scaffolding code? | Yes. Add changes, dependencies, tests, configuration, or documentation as needed. Preserve a simple setup/run path if possible and document changes as you go. |
| Is a user interface required? | No user interface is required. The exercise is API-first. Interactive API documentation or command-line requests are sufficient for the demo. |
| How much clinical expertise is expected? | Deep clinical domain expertise is not required. Ground answers in the public protocol text, state assumptions, and avoid making unsupported clinical conclusions. |
| Should I write automated tests? | Targeted tests are encouraged, especially for routing, validation, structured queries, and failure cases. Do not sacrifice the working end-to-end flow solely to maximize test count. |
| What if a public API or model endpoint fails? | Handle the failure clearly and continue with a reasonable fallback when possible. Cached public protocol data may be used. Explain the failure and the production mitigation you would apply. |
| Can I ask clarifying questions? | Yes. Use the kickoff to clarify scope, assumptions, and API contracts. During the solo build, the panel may resolve access or environment issues but will not design the solution for you. |
| What will be reviewed? | The working API, correctness of RAG and structured-data routing, guardrails, code organization, Git commits, use of AI-generated code, and your explanation of scalability, security, evaluation, and monitoring tradeoffs. |
| Will I be asked to code during the review? | Possibly. The panel may ask for a small modification, test, or debugging step to understand how you navigate and reason about the code. |
| Do I need to deploy to the cloud or implement GxP controls? | No, but be ready to discuss how the prototype would be hardened for security, observability, evaluation, compliance, and enterprise scale. We do not recommend you spend the build time implementing a production platform. |
| What should I submit or share? | Keep the work in the assigned private repository and commit as you go. Be ready to run it locally and show the code and commit history. Do not push the exercise to a public repository. |

#### Questions before the onsite

Contact the recruiter before the interview if accessibility accommodations or LLM availability may be an issue.
