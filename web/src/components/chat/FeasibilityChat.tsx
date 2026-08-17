import { useEffect, useMemo, useState, type FormEvent, type KeyboardEvent } from "react"
import { CopyIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { Message, MessageContent, MessageFooter, MessageHeader } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { SAMPLE_GROUPS } from "@/data/samples"
import {
  ApiError,
  citationLabel,
  listProtocols,
  submitQuery,
  type CachedProtocol,
  type LlmDebugExchange,
  type QueryResponse,
  type Route,
} from "@/lib/api"

const MAX_QUERY_LENGTH = 8000

type Thread =
  | { status: "empty" }
  | { status: "pending"; query: string; nctId: string | null }
  | { status: "ready"; query: string; nctId: string | null; response: QueryResponse }
  | { status: "error"; query: string; nctId: string | null; message: string }

const ROUTE_BADGE: Record<Route, string> = {
  site: "border-transparent bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  protocol: "border-transparent bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  hybrid: "border-transparent bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200",
  reject: "border-transparent bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
}

function protocolLabel(item: CachedProtocol): string {
  return item.brief_title ? `${item.nct_id} — ${item.brief_title}` : item.nct_id
}

function DebugCard({ title, payload }: { title: string; payload: unknown }) {
  const text = JSON.stringify(payload ?? {}, null, 2)
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      setCopied(false)
    }
    window.setTimeout(() => setCopied(false), 1200)
  }

  return (
    <Card size="sm" className="bg-muted/40">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          {title}
        </CardTitle>
        <Button type="button" variant="outline" size="xs" onClick={copy}>
          <CopyIcon />
          {copied ? "Copied" : "Copy"}
        </Button>
      </CardHeader>
      <CardContent>
        <pre className="max-h-60 overflow-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed whitespace-pre">
          {text}
        </pre>
      </CardContent>
    </Card>
  )
}

function DebugList({ exchanges }: { exchanges: LlmDebugExchange[] }) {
  return (
    <div className="flex flex-col gap-3">
      {exchanges.map((exchange, index) => {
        const suffix = exchanges.length > 1 ? ` ${index + 1}` : ""
        return (
          <div key={index} className="flex flex-col gap-3">
            <DebugCard title={`LLM request${suffix}`} payload={exchange.request} />
            <DebugCard title={`LLM response${suffix}`} payload={exchange.response} />
          </div>
        )
      })}
    </div>
  )
}

export function FeasibilityChat() {
  const [query, setQuery] = useState("")
  const [nctId, setNctId] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)
  const [sample, setSample] = useState<string | null>(null)
  const [protocols, setProtocols] = useState<CachedProtocol[]>([])
  const [thread, setThread] = useState<Thread>({ status: "empty" })

  useEffect(() => {
    void listProtocols().then(setProtocols)
  }, [])

  const extraProtocols = useMemo(() => {
    if (!nctId || protocols.some((item) => item.nct_id === nctId)) return []
    return [{ nct_id: nctId, brief_title: null }]
  }, [nctId, protocols])

  const protocolOptions = [...protocols, ...extraProtocols]
  const selectedGroup = category ? SAMPLE_GROUPS[Number(category)] : undefined
  const sending = thread.status === "pending"

  function applySample(item: { query: string; nct: string }) {
    setQuery(item.query)
    setNctId(item.nct || null)
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextQuery = query.trim()
    if (!nextQuery || sending) return

    setThread({ status: "pending", query: nextQuery, nctId })
    try {
      const response = await submitQuery(nextQuery, nctId)
      setThread({ status: "ready", query: nextQuery, nctId, response })
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Could not reach the API. Is the server running?"
      setThread({ status: "error", query: nextQuery, nctId, message })
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <div className="mx-auto flex h-svh w-full max-w-3xl flex-col border-x bg-background">
      <header className="border-b px-5 py-4">
        <h1 className="text-base font-semibold tracking-tight">Clinical site feasibility</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Local one-shot UI for <code className="font-mono text-xs">POST /query</code>. History is
          not kept.
        </p>
      </header>

      <MessageScrollerProvider>
        <MessageScroller className="flex-1">
          <MessageScrollerViewport>
            <MessageScrollerContent className="px-5 py-6">
              {thread.status === "empty" ? (
                <MessageScrollerItem className="flex flex-1 items-center justify-center">
                  <div className="max-w-md text-center">
                    <h2 className="text-sm font-semibold">Try a query</h2>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Pick a categorized sample below, or type your own. Each send replaces the
                      previous exchange.
                    </p>
                  </div>
                </MessageScrollerItem>
              ) : (
                <>
                  <MessageScrollerItem messageId="user" scrollAnchor>
                    <Message align="end">
                      <MessageContent>
                        <MessageHeader>You</MessageHeader>
                        <Bubble>
                          <BubbleContent className="whitespace-pre-wrap">
                            {thread.query}
                          </BubbleContent>
                        </Bubble>
                        {thread.nctId ? (
                          <MessageFooter>Attached {thread.nctId}</MessageFooter>
                        ) : null}
                      </MessageContent>
                    </Message>
                  </MessageScrollerItem>

                  {thread.status === "pending" ? (
                    <MessageScrollerItem messageId="pending">
                      <Marker role="status">
                        <MarkerIcon>
                          <Spinner />
                        </MarkerIcon>
                        <MarkerContent className="shimmer">Working…</MarkerContent>
                      </Marker>
                    </MessageScrollerItem>
                  ) : null}

                  {thread.status === "error" ? (
                    <MessageScrollerItem messageId="error">
                      <Message>
                        <MessageContent>
                          <Bubble variant="destructive">
                            <BubbleContent>{thread.message}</BubbleContent>
                          </Bubble>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  ) : null}

                  {thread.status === "ready" ? (
                    <>
                      <MessageScrollerItem messageId="assistant">
                        <Message>
                          <MessageContent>
                            <MessageHeader>Assistant</MessageHeader>
                            <Bubble variant="muted">
                              <BubbleContent className="whitespace-pre-wrap">
                                {thread.response.answer}
                              </BubbleContent>
                            </Bubble>
                            <MessageFooter className="flex-wrap gap-1.5 px-0">
                              <Badge
                                variant="secondary"
                                className={ROUTE_BADGE[thread.response.route]}
                              >
                                route {thread.response.route}
                              </Badge>
                              <Badge variant="secondary">source {thread.response.source}</Badge>
                              {thread.response.citations.map((citation, index) => (
                                <Badge key={`${citationLabel(citation)}-${index}`} variant="outline">
                                  {citationLabel(citation)}
                                </Badge>
                              ))}
                            </MessageFooter>
                          </MessageContent>
                        </Message>
                      </MessageScrollerItem>
                      {thread.response.llm_debug?.length ? (
                        <MessageScrollerItem messageId="debug">
                          <DebugList exchanges={thread.response.llm_debug} />
                        </MessageScrollerItem>
                      ) : null}
                    </>
                  ) : null}
                </>
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>

      <div className="space-y-3 border-t bg-muted/30 px-5 py-4">
        <div className="grid gap-3 sm:grid-cols-[minmax(10rem,1fr)_minmax(14rem,2fr)]">
          <div className="grid gap-1.5">
            <Label htmlFor="sample-category">Sample category</Label>
            <Select
              value={category}
              onValueChange={(value) => {
                setCategory(value)
                setSample(null)
              }}
            >
              <SelectTrigger id="sample-category" className="w-full min-w-0">
                <SelectValue placeholder="Select a category…" />
              </SelectTrigger>
              <SelectContent align="start" alignItemWithTrigger={false} className="min-w-56">
                {SAMPLE_GROUPS.map((group, index) => (
                  <SelectItem key={group.label} value={String(index)}>
                    {group.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="sample-question">Sample question</Label>
            <Select
              value={sample}
              disabled={!selectedGroup}
              onValueChange={(value) => {
                setSample(value)
                const item = selectedGroup?.items[Number(value)]
                if (item) applySample(item)
              }}
            >
              <SelectTrigger id="sample-question" className="w-full min-w-0">
                <SelectValue placeholder="Select a sample…" />
              </SelectTrigger>
              <SelectContent align="start" alignItemWithTrigger={false} className="min-w-72">
                {selectedGroup?.items.map((item, index) => (
                  <SelectItem
                    key={`${item.query}-${item.nct}`}
                    value={String(index)}
                    className="whitespace-normal"
                  >
                    {item.nct ? `${item.query}  ·  ${item.nct}` : item.query}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <form className="grid gap-3" onSubmit={onSubmit}>
          <div className="grid gap-1.5">
            <Label htmlFor="nct">Attached protocol</Label>
            <Select value={nctId} onValueChange={setNctId}>
              <SelectTrigger id="nct" className="w-full min-w-0">
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent align="start" alignItemWithTrigger={false} className="min-w-72">
                <SelectItem value={null}>None</SelectItem>
                {protocolOptions.map((item) => (
                  <SelectItem key={item.nct_id} value={item.nct_id} className="whitespace-normal">
                    {protocolLabel(item)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-[1fr_auto] items-end gap-2">
            <Textarea
              id="query"
              name="query"
              required
              maxLength={MAX_QUERY_LENGTH}
              rows={2}
              value={query}
              disabled={sending}
              placeholder="Ask about a site metric or a protocol…"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onComposerKeyDown}
            />
            <Button type="submit" disabled={sending || !query.trim()}>
              Send
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
