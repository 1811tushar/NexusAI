import type { EvidenceKind } from './api'
export interface EvidenceDTO {
  evidenceKey: string; kind: EvidenceKind; title: string; snippet: string
  source: { documentId?: number; chunkId?: number; page?: number; url?: string; sql?: string; table?: string; investigationId?: number }
  data?: { columns: string[]; rows: (string | number | null)[][]; truncated: boolean }
  chart?: { type: 'line' | 'bar'; x: string[]; series: { name: string; values: number[] }[] }
  score: number | null; createdAt: string
}
