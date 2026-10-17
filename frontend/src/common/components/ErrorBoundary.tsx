import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from './ui/Button'

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(e: Error, i: ErrorInfo) { console.error(e, i.componentStack) }
  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <div role="alert" className="mx-auto mt-16 max-w-lg space-y-3 p-6">
        <h1 className="text-xl font-semibold">This page hit an unexpected error</h1>
        <p className="text-muted">Reload to continue. If it keeps happening, copy the details and send them to your administrator.</p>
        <div className="flex gap-2">
          <Button onClick={() => location.reload()}>Reload</Button>
          <Button variant="secondary" onClick={() => void navigator.clipboard.writeText(`${error.name}: ${error.message}\n${error.stack ?? ''}`)}>Copy details</Button>
        </div>
      </div>
    )
  }
}
