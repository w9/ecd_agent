import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"

export function MarkdownAnswer({ children }: { children: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-inherit prose-p:my-2 prose-p:first:mt-0 prose-p:last:mb-0 prose-p:leading-relaxed prose-headings:mt-3 prose-headings:mb-1.5 prose-li:my-0.5 prose-pre:bg-background prose-pre:text-foreground">
      <Markdown remarkPlugins={[remarkGfm]}>{children}</Markdown>
    </div>
  )
}
