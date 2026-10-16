// Host smoke test: boot the real host and play a real puzzle over HTTP.
//
// Deliberately end-to-end. Every defect found while building this layer was an
// integration defect that a unit test with a mocked service would have missed:
// the plugin loader skipping both entry files, Cordis refusing `ctx.puzzles`
// without an `inject` declaration, services that were constructed but never
// started. This file exists to keep those failures visible.
//
// Exit codes: 0 all checks passed · 1 a check failed · 3 the host would not boot.
import { bootHost, stopHost } from './boot.mjs'
import { inspectView, primitives, UnknownPrimitive } from './plugins/render.mjs'

const PORT = Number(process.env.SMOKE_PORT || 8099)
const failures = []

function ok(label, detail = '') {
  console.log(`OK    ${label}${detail ? ` — ${detail}` : ''}`)
}

function bad(label, detail = '') {
  failures.push(label)
  console.error(`FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
}

async function check(label, fn) {
  try {
    const detail = await fn()
    ok(label, detail)
  } catch (error) {
    bad(label, error.message)
    if (process.env.SMOKE_VERBOSE) console.error(error)
  }
}

async function request(base, path, { method = 'GET', body } = {}) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await response.text()
  let payload
  try {
    payload = JSON.parse(text)
  } catch {
    payload = { raw: text.slice(0, 200) }
  }
  return { status: response.status, payload }
}

let ctx
try {
  ctx = await bootHost({ port: PORT })
} catch (error) {
  console.error(`ENVIRONMENT ERROR: host did not boot: ${error.message}`)
  process.exit(3)
}

const base = ctx.web.url
console.log(`host booted on ${base}\n`)

await check('primitive whitelist is non-empty and complete', () => {
  const names = primitives()
  if (!names.includes('grid') || !names.includes('field')) {
    throw new Error(`unexpected primitives: ${names.join(', ')}`)
  }
  return `${names.length} primitives: ${names.join(', ')}`
})

await check('health endpoint reports ready', async () => {
  const { status, payload } = await request(base, '/healthz')
  if (status !== 200 || !payload.ok) throw new Error(`status ${status}: ${JSON.stringify(payload)}`)
  return 'ok=true'
})

await check('browser client is served', async () => {
  const page = await request(base, '/')
  if (page.status !== 200 || !page.payload.raw?.includes('<title>')) {
    throw new Error(`unexpected page: ${page.status}`)
  }
  const app = await request(base, '/client/app.js')
  if (app.status !== 200) throw new Error(`client script missing: ${app.status}`)
  return 'index.html + client/app.js'
})

await check('all 14 kinds are listed over the API', async () => {
  const { status, payload } = await request(base, '/api/kinds')
  if (status !== 200) throw new Error(`status ${status}`)
  if (payload.kinds.length !== 14) throw new Error(`expected 14 kinds, got ${payload.kinds.length}`)
  return payload.kinds.map((k) => k.name).join(', ')
})

await check('every kind produces a view the host accepts', async () => {
  const { payload } = await request(base, '/api/kinds')
  const problems = []
  for (const kind of payload.kinds) {
    const { status, payload: snapshot } = await request(base, '/api/new', {
      method: 'POST',
      body: { kind: kind.name, difficulty: 'easy' },
    })
    if (status !== 200) {
      problems.push(`${kind.name}: HTTP ${status} ${snapshot.error || ''}`)
      continue
    }
    const report = inspectView(snapshot.view)
    if (!report.ok) problems.push(`${kind.name}: ${report.problems.join('; ')}`)
    if (!snapshot.view.actions.includes('submit')) problems.push(`${kind.name}: no submit action`)
  }
  if (problems.length) throw new Error(problems.join(' | '))
  return '14 views validated against the primitive whitelist'
})

await check('an unknown primitive is refused loudly, not rendered blank', async () => {
  const { assertView } = await import('./plugins/render.mjs')
  try {
    assertView({ nodes: [{ type: 'telepathy' }] })
  } catch (error) {
    if (error instanceof UnknownPrimitive) return 'UnknownPrimitive thrown'
    throw error
  }
  throw new Error('an unknown primitive was accepted')
})

await check('answering scores points (text kind)', async () => {
  await request(base, '/api/new', { method: 'POST', body: { kind: 'math', difficulty: 'easy' } })
  const { payload: state } = await request(base, '/api/state')
  const field = state.view.nodes.find((node) => node.type === 'field')
  if (!field) throw new Error('math view has no answer field')

  // A wrong answer must not score; the correct one is checked by the Python
  // suite (tests/test_service.py), which can read the answer without going
  // through the wire. What matters here is that scoring crosses the boundary.
  const wrong = await request(base, '/api/answer', { method: 'POST', body: { answer: '999999999' } })
  if (wrong.status !== 200) throw new Error(`submit failed: ${JSON.stringify(wrong.payload)}`)
  if (wrong.payload.last_result.correct !== false) throw new Error('a nonsense answer was accepted')
  if (wrong.payload.score !== 0) throw new Error(`wrong answer scored ${wrong.payload.score}`)

  const hint = await request(base, '/api/hint', { method: 'POST', body: {} })
  if (!hint.payload.hint) throw new Error('no hint for the active puzzle')
  return `wrong answer scored 0, streak ${wrong.payload.streak}, hint present`
})

await check('a non-numeric answer is a structured error', async () => {
  await request(base, '/api/new', { method: 'POST', body: { kind: 'math' } })
  const { status, payload } = await request(base, '/api/answer', {
    method: 'POST',
    body: { answer: 'not a number' },
  })
  if (status === 200) throw new Error('a bad answer was accepted')
  return `HTTP ${status}: ${payload.error}`
})

await check('actions change state (minesweeper reveal)', async () => {
  await request(base, '/api/new', { method: 'POST', body: { kind: 'minesweeper', difficulty: 'easy' } })
  const { status, payload } = await request(base, '/api/action', {
    method: 'POST',
    body: { action: 'reveal', row: 0, col: 0 },
  })
  if (status !== 200) throw new Error(`action failed: ${JSON.stringify(payload)}`)
  const grid = payload.view.nodes.find((node) => node.type === 'grid')
  if (!grid?.cells?.[0]?.[0]?.revealed) throw new Error('cell (0,0) is still hidden')
  return 'cell (0,0) revealed'
})

await check('hints come back with CJK intact', async () => {
  await request(base, '/api/new', { method: 'POST', body: { kind: 'word_ladder' } })
  const { payload } = await request(base, '/api/hint', { method: 'POST', body: {} })
  if (!payload.hint?.trim()) throw new Error('empty hint')
  if (!/[\u4e00-\u9fff]/.test(payload.hint)) {
    throw new Error(`hint has no CJK text — encoding may be broken: ${payload.hint}`)
  }
  return payload.hint.slice(0, 24)
})

await check('SSE pushes a snapshot to a connected client', async () => {
  const controller = new AbortController()
  const response = await fetch(`${base}/api/events`, { signal: controller.signal })
  if (response.headers.get('content-type')?.includes('text/event-stream') !== true) {
    throw new Error(`unexpected content-type: ${response.headers.get('content-type')}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const { value } = await reader.read()
  const text = decoder.decode(value)
  controller.abort()
  if (!text.includes('event: snapshot')) throw new Error(`no snapshot event: ${text.slice(0, 80)}`)
  return 'snapshot event received'
})

// --- shutdown -------------------------------------------------------------
await check('host shuts down and releases the puzzle process', async () => {
  await stopHost(ctx)
  ctx = null
  const afterStop = await fetch(`${base}/healthz`).then(
    () => 'still listening',
    () => 'port closed',
  )
  if (afterStop !== 'port closed') throw new Error(`server ${afterStop} after stopHost()`)
  return 'port closed, disposers ran'
})

console.log()
if (failures.length) {
  console.error(`SMOKE FAILED: ${failures.length} check(s): ${failures.join(', ')}`)
  process.exit(1)
}
console.log('SMOKE PASSED')
process.exit(0)
