import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
/** Sanitised Markdown; external links open safely (FE-RP-02, SEC-08). */
export function MarkdownView({ children }: { children: string }) {
  return (
    <div className="max-w-[var(--reading-width)] space-y-3 leading-7 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mt-6 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:font-semibold [&_li]:ml-5 [&_ol]:list-decimal [&_ul]:list-disc [&_table]:w-full [&_td]:border [&_td]:border-line [&_td]:px-2 [&_th]:border [&_th]:border-line [&_th]:px-2 [&_a]:text-accent [&_a]:underline">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}
        components={{ a: ({ href, children: c }) => <a href={href} target="_blank" rel="noopener noreferrer">{c}</a> }}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
