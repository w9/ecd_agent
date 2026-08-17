export type SampleItem = {
  query: string
  nct: string
}

export type SampleGroup = {
  label: string
  items: SampleItem[]
}

export const SAMPLE_GROUPS: SampleGroup[] = [
  {
    label: "Site metrics",
    items: [
      { query: "What is the enrollment rate for SITE-001?", nct: "" },
      { query: "How many active trials are at SITE-001?", nct: "" },
      { query: "How many remaining slots does SITE-001 have?", nct: "" },
      { query: "Tell me about SITE-001.", nct: "" },
      { query: "What is the enrollment rate for SITE-007?", nct: "" },
      { query: "How many active trials are at SITE-005?", nct: "" },
      { query: "How many remaining slots does SITE-003 have?", nct: "" },
      { query: "Tell me about SITE-010.", nct: "" },
    ],
  },
  {
    label: "Site ranking",
    items: [
      { query: "Which oncology site has the highest enrollment rate?", nct: "" },
      { query: "Which immunology site has the highest enrollment rate?", nct: "" },
      { query: "Which cardiology site has the highest enrollment rate?", nct: "" },
      { query: "Which site has the highest enrollment rate?", nct: "" },
    ],
  },
  {
    label: "Protocol questions",
    items: [
      { query: "What is the minimum age for NCT04516746?", nct: "" },
      { query: "What are the inclusion criteria for this protocol?", nct: "NCT04516746" },
      { query: "What are the exclusion criteria for this protocol?", nct: "NCT04516746" },
      { query: "What is the maximum age for this protocol?", nct: "NCT04516746" },
      { query: "What conditions does NCT04368728 study?", nct: "" },
      { query: "What is the primary outcome of NCT04470427?", nct: "" },
      { query: "What is the study design of this protocol?", nct: "NCT04156698" },
      { query: "What are the interventions in NCT03875287?", nct: "" },
    ],
  },
  {
    label: "Hybrid recommendations",
    items: [
      {
        query: "Where should I run my next oncology trial given this protocol?",
        nct: "NCT04516746",
      },
      { query: "Recommend sites for this protocol.", nct: "NCT04516746" },
      {
        query: "Where should I run my next trial given this protocol?",
        nct: "NCT04368728",
      },
      {
        query: "Which sites should I consider for my next oncology trial given this protocol?",
        nct: "NCT04470427",
      },
    ],
  },
  {
    label: "Lookalikes (eligibility, not rates)",
    items: [
      { query: "Enrollment criteria at SITE-001", nct: "" },
      {
        query: "What are the enrollment criteria for this protocol?",
        nct: "NCT04516746",
      },
      { query: "What is the eligibility criteria for SITE-001?", nct: "" },
    ],
  },
  {
    label: "Unknown / missing data",
    items: [
      { query: "What is the enrollment rate for site YYY?", nct: "" },
      { query: "What is the enrollment rate for SITE-012?", nct: "" },
      { query: "What is the enrollment rate for SITE-011?", nct: "" },
      { query: "How many remaining slots does SITE-012 have?", nct: "" },
      { query: "How many active trials are at SITE-011?", nct: "" },
      { query: "What is the dosing schedule for NCT00000001?", nct: "" },
    ],
  },
  {
    label: "Incomplete / ambiguous",
    items: [
      { query: "What is the enrollment rate?", nct: "" },
      { query: "What is the minimum age?", nct: "" },
      { query: "Tell me about the protocol.", nct: "" },
      { query: "Where should I run my next trial?", nct: "" },
      { query: "How many remaining slots?", nct: "" },
    ],
  },
  {
    label: "Out of scope",
    items: [
      { query: "Write me a new clinical protocol from scratch", nct: "" },
      { query: "Should I enroll my patient in this trial?", nct: "" },
      { query: "Here is patient John Doe’s chart…", nct: "" },
      {
        query: "Does this patient meet the eligibility criteria?",
        nct: "NCT04516746",
      },
    ],
  },
]
