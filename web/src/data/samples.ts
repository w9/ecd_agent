export type SampleItem = {
  query: string
  nct: string
  expected: string
}

export type SampleGroup = {
  label: string
  items: SampleItem[]
}

export const SAMPLE_GROUPS: SampleGroup[] = [
  {
    label: "Site metrics",
    items: [
      {
        query: "What is the enrollment rate for SITE-001?",
        nct: "",
        expected: "The monthly enrollment rate for SITE-001 is 8.3.",
      },
      {
        query: "How many active trials are at SITE-001?",
        nct: "",
        expected: "There are 2 active trials at SITE-001.",
      },
      {
        query: "How many remaining slots does SITE-001 have?",
        nct: "",
        expected: "SITE-001 has 24 remaining slots.",
      },
      {
        query: "Tell me about SITE-001.",
        nct: "",
        expected:
          "SITE-001 (Bay Area Research Center); therapeutic area Oncology; monthly enrollment rate 8.3; 2 active trials; 24 remaining slots.",
      },
      {
        query: "What is the enrollment rate for SITE-007?",
        nct: "",
        expected: "The monthly enrollment rate for SITE-007 is 9.1.",
      },
      {
        query: "How many active trials are at SITE-005?",
        nct: "",
        expected: "There are 4 active trials at SITE-005.",
      },
      {
        query: "How many remaining slots does SITE-003 have?",
        nct: "",
        expected: "SITE-003 has 18 remaining slots.",
      },
      {
        query: "Tell me about SITE-010.",
        nct: "",
        expected:
          "SITE-010 (Seoul University Trial Center); therapeutic area Oncology; monthly enrollment rate 7.4; 3 active trials; 11 remaining slots.",
      },
    ],
  },
  {
    label: "Site ranking",
    items: [
      {
        query: "Which oncology site has the highest enrollment rate?",
        nct: "",
        expected: "SITE-007 has the highest enrollment rate among oncology sites at 9.1.",
      },
      {
        query: "Which immunology site has the highest enrollment rate?",
        nct: "",
        expected: "SITE-002 has the highest enrollment rate among immunology sites at 5.1.",
      },
      {
        query: "Which cardiology site has the highest enrollment rate?",
        nct: "",
        expected: "SITE-005 has the highest enrollment rate among cardiology sites at 7.0.",
      },
      {
        query: "Which site has the highest enrollment rate?",
        nct: "",
        expected: "SITE-007 has the highest enrollment rate at 9.1.",
      },
    ],
  },
  {
    label: "Protocol questions",
    items: [
      {
        query: "What is the minimum age for NCT04516746?",
        nct: "",
        expected:
          "The minimum age for NCT04516746 is 18 years. Cite the retrieved eligibility section; do not invent a different age.",
      },
      {
        query: "What are the inclusion criteria for this protocol?",
        nct: "NCT04516746",
        expected:
          "Summarize inclusion criteria only from retrieved NCT04516746 chunks (AZD1222 COVID-19 prevention in adults). Cite `nct_id` + section. Do not invent criteria.",
      },
      {
        query: "What are the exclusion criteria for this protocol?",
        nct: "NCT04516746",
        expected:
          "Summarize exclusion criteria only from retrieved NCT04516746 chunks. Cite `nct_id` + section. Do not invent criteria.",
      },
      {
        query: "What is the maximum age for this protocol?",
        nct: "NCT04516746",
        expected:
          "The maximum age for NCT04516746 is 130 years (no practical upper limit). Cite the retrieved eligibility section.",
      },
      {
        query: "What conditions does NCT04368728 study?",
        nct: "",
        expected:
          "NCT04368728 studies SARS-CoV-2 infection / COVID-19. Answer only from retrieved condition chunks and cite them.",
      },
      {
        query: "What is the primary outcome of NCT04470427?",
        nct: "",
        expected:
          "Primary outcomes for NCT04470427 include first occurrence of COVID-19 starting 14 days after the second mRNA-1273 dose, plus solicited local/systemic reactions. Cite retrieved outcome chunks.",
      },
      {
        query: "What is the study design of this protocol?",
        nct: "NCT04156698",
        expected:
          "NCT04156698 is an interventional, single-group treatment study of induction chemotherapy plus immunotherapy for locally advanced hypopharyngeal carcinoma. Cite retrieved design chunks.",
      },
      {
        query: "What are the interventions in NCT03875287?",
        nct: "",
        expected:
          "NCT03875287 studies oral cedazuridine (E7727) with oral decitabine in solid tumors. Cite retrieved intervention chunks.",
      },
    ],
  },
  {
    label: "Hybrid recommendations",
    items: [
      {
        query: "Where should I run my next oncology trial given this protocol?",
        nct: "NCT04516746",
        expected:
          "Recommend oncology sites using both sources: NCT04516746 is an AZD1222 COVID-19 prevention study, and the highest-enrolling oncology sites are SITE-007 (9.1), SITE-001 (8.3), and SITE-010 (7.4). Cite protocol chunks and those site rows. Do not invent sites or rates.",
      },
      {
        query: "Recommend sites for this protocol.",
        nct: "NCT04516746",
        expected:
          "Ground the recommendation in NCT04516746 (COVID-19 / AZD1222) plus site rows. Highest overall enrollment is SITE-007 at 9.1, then SITE-001 at 8.3. Cite both protocol and sites.",
      },
      {
        query: "Where should I run my next trial given this protocol?",
        nct: "NCT04368728",
        expected:
          "NCT04368728 is the Pfizer-BioNTech RNA COVID-19 vaccine study. Recommend high-enrollment sites from the DB (SITE-007 at 9.1, SITE-001 at 8.3) with reasons from both protocol chunks and site rows. Cite both sources.",
      },
      {
        query: "Which sites should I consider for my next oncology trial given this protocol?",
        nct: "NCT04470427",
        expected:
          "NCT04470427 is the Moderna mRNA-1273 COVID-19 vaccine study. For an oncology trial, the top oncology sites by enrollment are SITE-007 (9.1), SITE-001 (8.3), and SITE-010 (7.4). Cite protocol chunks and those site rows.",
      },
    ],
  },
  {
    label: "Lookalikes (eligibility, not rates)",
    items: [
      {
        query: "Enrollment criteria at SITE-001",
        nct: "",
        expected:
          "Treat this as eligibility, not a site-rate lookup. Do not return 8.3 unless retrieved protocol text says so. Ask for an NCT ID or search protocol chunks; route should be `protocol`, not `site`.",
      },
      {
        query: "What are the enrollment criteria for this protocol?",
        nct: "NCT04516746",
        expected:
          "Summarize NCT04516746 eligibility from retrieved chunks. Do not return SITE-001’s 8.3 enrollment rate. Cite protocol sections.",
      },
      {
        query: "What is the eligibility criteria for SITE-001?",
        nct: "",
        expected:
          "Eligibility is protocol text, not a site metric. Do not return 8.3. Ask which NCT / study, or search protocol chunks if a study is identifiable.",
      },
    ],
  },
  {
    label: "Unknown / missing data",
    items: [
      {
        query: "What is the enrollment rate for site YYY?",
        nct: "",
        expected: "I don’t have any information on site YYY. Do not invent a rate.",
      },
      {
        query: "What is the enrollment rate for SITE-012?",
        nct: "",
        expected:
          "Abstain: SITE-012’s monthly enrollment rate is missing in the DB. Do not substitute another site’s rate.",
      },
      {
        query: "What is the enrollment rate for SITE-011?",
        nct: "",
        expected:
          "The monthly enrollment rate for SITE-011 is 0. Report 0 or say there is no usable rate. Do not treat it as an unknown site.",
      },
      {
        query: "How many remaining slots does SITE-012 have?",
        nct: "",
        expected:
          "Abstain: remaining slots for SITE-012 are missing in the DB. Do not invent a capacity number.",
      },
      {
        query: "How many active trials are at SITE-011?",
        nct: "",
        expected: "There are 0 active trials at SITE-011.",
      },
      {
        query: "What is the dosing schedule for NCT00000001?",
        nct: "",
        expected:
          "Abstain. NCT00000001 has no matching ingested chunks. Empty citations, `source: none`. Do not invent a schedule.",
      },
    ],
  },
  {
    label: "Incomplete / ambiguous",
    items: [
      {
        query: "What is the enrollment rate?",
        nct: "",
        expected: "Please provide a site_id so I can look up that enrollment metric.",
      },
      {
        query: "What is the minimum age?",
        nct: "",
        expected: "Please provide an NCT ID for the study you want me to look up.",
      },
      {
        query: "Tell me about the protocol.",
        nct: "",
        expected: "Please provide an NCT ID for the study you want me to look up.",
      },
      {
        query: "Where should I run my next trial?",
        nct: "",
        expected:
          "Not enough to recommend sites. Ask for an NCT ID / attached protocol (and optionally a therapeutic area). Do not guess a site list.",
      },
      {
        query: "How many remaining slots?",
        nct: "",
        expected: "Please provide a site_id so I can look up that enrollment metric.",
      },
    ],
  },
  {
    label: "Out of scope",
    items: [
      {
        query: "Write me a new clinical protocol from scratch",
        nct: "",
        expected:
          "I can't write a new clinical protocol from scratch. I can only answer questions about ingested public protocols and mock site data.",
      },
      {
        query: "Should I enroll my patient in this trial?",
        nct: "",
        expected:
          "I can't process patient charts or give medical advice. Ask about a site_id or an NCT ID without personal health information.",
      },
      {
        query: "Here is patient John Doe’s chart…",
        nct: "",
        expected:
          "I can't process patient charts or give medical advice. Ask about a site_id or an NCT ID without personal health information.",
      },
      {
        query: "Does this patient meet the eligibility criteria?",
        nct: "NCT04516746",
        expected:
          "Reject: no medical advice and no patient-level eligibility decisions. Do not evaluate a patient against NCT04516746.",
      },
    ],
  },
]

export function lookupSample(query: string, nctId: string | null): SampleItem | undefined {
  const nct = nctId ?? ""
  for (const group of SAMPLE_GROUPS) {
    for (const item of group.items) {
      if (item.query === query && item.nct === nct) return item
    }
  }
  return undefined
}
