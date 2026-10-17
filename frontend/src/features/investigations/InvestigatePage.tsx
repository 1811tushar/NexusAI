import { PageHeader } from '@/common/components/PageHeader'
import { QuestionForm } from './QuestionForm'
export function InvestigatePage() {
  return (<><PageHeader title="Investigate" description="Ask a business question. The agents plan, gather evidence, verify claims and report with citations." /><div className="max-w-3xl"><QuestionForm /></div></>)
}
