import { setupWorker } from 'msw/browser'
import { approvalHandlers } from './handlers/approvals'
import { authHandlers } from './handlers/auth'
import { documentHandlers } from './handlers/documents'
import { evalHandlers } from './handlers/eval'
import { investigationHandlers } from './handlers/investigations'
import { miscHandlers } from './handlers/misc'
export const worker = setupWorker(...authHandlers, ...documentHandlers, ...miscHandlers, ...investigationHandlers, ...approvalHandlers, ...evalHandlers)
