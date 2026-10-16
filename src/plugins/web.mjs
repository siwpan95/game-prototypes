// WebService plugin: serves the browser client and exposes the puzzle API.
//
// Transport choice follows the research in docs/_research/04-web-platform.md:
// turn-based play wants **POST for actions + SSE for snapshots**. POST keeps
// every action a plain request/response (trivially testable with curl), and SSE
// gives automatic reconnect with `Last-Event-ID` for free — WebSocket has no
// recovery in the protocol layer, and Node ships a WebSocket *client* but no
// server, so it would drag in a dependency for no gain here.
//
// The server is bound to the loopback interface by default: this is a
// single-player game on the user's own machine, and opening it to the LAN is a
// decision the operator must make explicitly.
import { Service } from 'cordis'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join, normalize, resolve, sep } from 'node:path'
import { assertView } from './render.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = resolve(HERE, '..', '..')
const PUBLIC_DIR = join(PROJECT_ROOT, 'public')

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
}

export class WebService extends Service {
  static provide = 'web'

  // Cordis gates access to another service behind an `inject` declaration:
  // reading ctx.puzzles without it throws at run time. Declaring the dependency
  // is also what orders the lifecycle — the web server only starts once the
  // puzzle service exists, and is disposed first if it goes away.
  static inject = ['puzzles']

  constructor(ctx, config = {}) {
    super(ctx, 'web')
    this.config = config
    this.host = config.host || '127.0.0.1'
    this.port = config.port ?? 8080
    this.sessionId = config.sessionId || 'web'
    this.server = null
    this.clients = new Set()
    this.stats = { requests: 0, errors: 0, sseClients: 0, actions: 0 }
    this.ctx.effect(() => () => this.stop())

    // Start immediately (listen() does not block) and expose readiness as a
    // promise; `bootHost` awaits it so the reported URL is a listening socket.
    this.ready = this.#listen()
  }

  get puzzles() {
    return this.ctx.puzzles
  }

  #listen() {
    this.server = createServer((req, res) => {
      this.#handle(req, res).catch((error) => this.#fail(res, error))
    })
    return new Promise((resolvePromise, rejectPromise) => {
      this.server.once('error', (error) => {
        this.ctx.logger.error('web server failed to listen on %s:%d — %s', this.host, this.port, error.message)
        rejectPromise(error)
      })
      this.server.listen(this.port, this.host, () => {
        const address = this.server.address()
        const host = this.host === '0.0.0.0' || this.host === '::' ? '127.0.0.1' : this.host
        this.url = `http://${host}:${address.port}`
        this.ctx.logger.info('web client on %s', this.url)
        resolvePromise(this.url)
      })
    })
  }

  async stop() {
    for (const client of this.clients) {
      try {
        client.end()
      } catch {
        // the socket is already gone; nothing to release
      }
    }
    this.clients.clear()
    if (!this.server) return
    const server = this.server
    this.server = null
    await new Promise((resolvePromise) => server.close(resolvePromise))
  }

  // --- routing -------------------------------------------------------------

  async #handle(req, res) {
    this.stats.requests += 1
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`)
    const route = `${req.method} ${url.pathname}`

    if (route === 'GET /healthz') {
      return this.#json(res, 200, {
        ok: this.server !== null,
        stats: { ...this.stats, sessions: 1 },
      })
    }
    if (route === 'GET /api/kinds') {
      return this.#json(res, 200, { kinds: await this.puzzles.listKinds() })
    }
    if (route === 'GET /api/profile') {
      return this.#json(res, 200, await this.puzzles.call('profile.info', {}))
    }
    if (route === 'POST /api/daily') {
      const body = await this.#body(req)
      const snapshot = await this.puzzles.call('puzzle.daily', {
        session_id: this.#session(url, body),
        day: body.day ?? null,
        difficulty: body.difficulty || 'medium',
      })
      return this.#replySnapshot(res, snapshot)
    }
    if (route === 'GET /api/share') {
      const day = url.searchParams.get('day')
      return this.#json(res, 200, await this.puzzles.call('profile.share', { day }))
    }
    if (route === 'GET /api/state') {
      return this.#json(res, 200, await this.#snapshot(this.#session(url)))
    }
    if (route === 'POST /api/new') {
      const body = await this.#body(req)
      const snapshot = await this.puzzles.newPuzzle({
        sessionId: this.#session(url, body),
        kind: body.kind ?? null,
        difficulty: body.difficulty || 'medium',
      })
      return this.#replySnapshot(res, snapshot)
    }
    if (route === 'POST /api/answer') {
      const body = await this.#body(req)
      const sessionId = this.#session(url, body)
      const result = await this.puzzles.submit({ sessionId, answer: body.answer })
      const snapshot = await this.#snapshot(sessionId)
      snapshot.last_result = result
      return this.#replySnapshot(res, snapshot)
    }
    if (route === 'POST /api/action') {
      const body = await this.#body(req)
      const { action, session_id: _ignored, ...params } = body
      if (!action) return this.#json(res, 400, { error: 'action is required' })
      this.stats.actions += 1
      const snapshot = await this.puzzles.action({
        sessionId: this.#session(url, body),
        action,
        ...params,
      })
      return this.#replySnapshot(res, snapshot)
    }
    if (route === 'POST /api/hint') {
      const body = await this.#body(req)
      const { hint } = await this.puzzles.hint({ sessionId: this.#session(url, body) })
      return this.#json(res, 200, { hint })
    }
    if (route === 'POST /api/reset') {
      const body = await this.#body(req)
      return this.#replySnapshot(res, await this.puzzles.reset({ sessionId: this.#session(url, body) }))
    }
    if (route === 'GET /api/events') {
      return this.#sse(req, res, url)
    }
    if (req.method === 'GET') {
      return this.#static(url.pathname, res)
    }
    return this.#json(res, 404, { error: `no route for ${route}` })
  }

  #session(url, body = {}) {
    return body.session_id || url.searchParams.get('session') || this.sessionId
  }

  async #snapshot(sessionId) {
    const snapshot = await this.puzzles.state({ sessionId })
    if (snapshot.view) assertView(snapshot.view)  // fail loudly, never render blank
    return snapshot
  }

  // --- responses -----------------------------------------------------------

  /** Push a snapshot to every SSE client and answer the POST that caused it. */
  #replySnapshot(res, snapshot) {
    this.#sendEvent('snapshot', snapshot)
    return this.#json(res, 200, snapshot)
  }

  #sendEvent(event, data) {
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
    for (const client of this.clients) {
      try {
        client.write(payload)
      } catch {
        this.clients.delete(client)
      }
    }
  }

  #sse(req, res, url) {
    res.writeHead(200, {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-cache, no-transform',
      connection: 'keep-alive',
    })
    this.clients.add(res)
    this.stats.sseClients = this.clients.size
    const sessionId = this.#session(url)
    this.puzzles
      .state({ sessionId })
      .then((snapshot) => {
        if (snapshot.view) assertView(snapshot.view)
        res.write(`event: snapshot\ndata: ${JSON.stringify(snapshot)}\n\n`)
      })
      .catch((error) => {
        res.write(`event: error\ndata: ${JSON.stringify({ message: error.message })}\n\n`)
      })
    const keepAlive = setInterval(() => res.write(': keep-alive\n\n'), 15_000)
    req.on('close', () => {
      clearInterval(keepAlive)
      this.clients.delete(res)
      this.stats.sseClients = this.clients.size
    })
  }

  async #static(pathname, res) {
    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '')
    const target = join(PUBLIC_DIR, normalize(relative))
    if (!target.startsWith(PUBLIC_DIR + sep)) {
      return this.#json(res, 403, { error: 'path escapes the public directory' })
    }
    try {
      const data = await readFile(target)
      const extension = target.slice(target.lastIndexOf('.'))
      res.writeHead(200, {
        'content-type': CONTENT_TYPES[extension] || 'application/octet-stream',
        'cache-control': 'no-cache',
      })
      return res.end(data)
    } catch {
      return this.#json(res, 404, { error: `not found: ${relative}` })
    }
  }

  #json(res, status, payload) {
    const body = JSON.stringify(payload)
    res.writeHead(status, {
      'content-type': 'application/json; charset=utf-8',
      'content-length': Buffer.byteLength(body),
    })
    return res.end(body)
  }

  #fail(res, error) {
    this.stats.errors += 1
    this.ctx.logger.warn('request failed: %s', error.stack || error.message)
    if (res.headersSent) return res.end()
    return this.#json(res, 500, { error: error.message, name: error.name })
  }

  async #body(req) {
    const chunks = []
    let size = 0
    for await (const chunk of req) {
      size += chunk.length
      if (size > 1_000_000) throw new Error('request body too large')
      chunks.push(chunk)
    }
    if (!chunks.length) return {}
    const text = Buffer.concat(chunks).toString('utf8')
    try {
      return JSON.parse(text)
    } catch (error) {
      throw new Error(`request body is not JSON: ${error.message}`)
    }
  }
}

// Helper kept outside the class: nothing here needs the service instance.

export default WebService
