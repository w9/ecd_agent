export type Route = "site" | "protocol" | "hybrid" | "reject"
export type Source = "sites" | "protocol" | "hybrid" | "none"

export type Citation = {
  source: "sites" | "protocol"
  site_id?: string | null
  nct_id?: string | null
  section?: string | null
}

export type LlmDebugExchange = {
  request: Record<string, unknown>
  response: Record<string, unknown>
}

export type QueryResponse = {
  answer: string
  route: Route
  source: Source
  citations: Citation[]
  llm_debug?: LlmDebugExchange[] | null
}

export type CachedProtocol = {
  nct_id: string
  brief_title: string | null
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

function formatDetail(body: unknown): string | null {
  if (!body || typeof body !== "object" || !("detail" in body)) return null
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join("; ")
  }
  return null
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return {}
  }
}

export async function listProtocols(): Promise<CachedProtocol[]> {
  const response = await fetch("/protocols")
  if (!response.ok) return []
  const body = await readJson(response)
  return Array.isArray(body) ? (body as CachedProtocol[]) : []
}

export async function submitQuery(
  query: string,
  nctId: string | null,
): Promise<QueryResponse> {
  const payload: { query: string; nct_id?: string } = { query }
  if (nctId) payload.nct_id = nctId

  let response: Response
  try {
    response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new ApiError(0, "Could not reach the API. Is the server running?")
  }

  const body = await readJson(response)
  if (!response.ok) {
    throw new ApiError(
      response.status,
      formatDetail(body) ?? `Request failed (${response.status})`,
    )
  }
  return body as QueryResponse
}

export function citationLabel(citation: Citation): string {
  if (citation.site_id) return citation.site_id
  const parts = [citation.nct_id, citation.section].filter(Boolean)
  return parts.join(" · ") || citation.source
}
