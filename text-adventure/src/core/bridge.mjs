// JSON-RPC 2.0 client for the Python puzzle service, over newline-delimited JSON
// on the child process's stdio.
//
// Why the Python process owns puzzle state: the puzzles are written in Python
// (14 kinds under text_adventure_zh/gameplay_pool/). The host orchestrates and
// renders; it never re-implements puzzle logic. Keeping the boundary at a
// documented method table is what makes the two sides independently testable.
//
// Two platform details this file exists to get right:
//   * the child is spawned with an explicit UTF-8 environment, because a Chinese
//     Windows console defaults to a legacy code page and would mangle every CJK
//     string crossing the bridge;
//   * stdout carries protocol frames only. The child's stderr is forwarded to the
//     host logger, never parsed, so diagnostics can never corrupt a reply.
import { spawn } from 'node:child_process'
import { createInterface } from 'node:readline'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
export const PROJECT_ROOT = resolve(HERE, '..', '..')
const SERVER_SCRIPT = join(PROJECT_ROOT, 'python', 'rpc_server.py')

export class RpcError extends Error {
  constructor(code, message, data) {
    super(`[${code}] ${message}`)
    this.name = 'RpcError'
    this.code = code
    this.data = data
  }
}

/**
 * A JSON-RPC client bound to one puzzle-service child process.
 *
 * Events: 'exit' (code, signal), 'stderr' (line).
 */
export class PuzzleBridge extends EventTarget {
  #child
  #pending = new Map()
  #nextId = 1
  #closed = false

  constructor({ python = process.env.TEXT_ADVENTURE_PYTHON || defaultPython(), language = 'zh', timeoutMs = 10_000, env = {} } = {}) {
    super()
    this.language = language
    this.timeoutMs = timeoutMs
    this.#child = spawn(python, [SERVER_SCRIPT, '--language', language], {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
        PYTHONUNBUFFERED: '1',
        ...env,
      },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    })

    const replies = createInterface({ input: this.#child.stdout, crlfDelay: Infinity })
    replies.on('line', (line) => this.#onLine(line))

    const diagnostics = createInterface({ input: this.#child.stderr, crlfDelay: Infinity })
    diagnostics.on('line', (line) => {
      this.dispatchEvent(new CustomEvent('stderr', { detail: line }))
    })

    this.#child.on('exit', (code, signal) => {
      this.#closed = true
      const error = new Error(`puzzle service exited (code=${code}, signal=${signal})`)
      for (const { reject, timer } of this.#pending.values()) {
        clearTimeout(timer)
        reject(error)
      }
      this.#pending.clear()
      this.dispatchEvent(new CustomEvent('exit', { detail: { code, signal } }))
    })
  }

  get closed() {
    return this.#closed
  }

  /** One request. Resolves with the `result` field, rejects with RpcError. */
  call(method, params = {}) {
    if (this.#closed) return Promise.reject(new Error('puzzle service is not running'))
    const id = this.#nextId++
    const frame = JSON.stringify({ jsonrpc: '2.0', id, method, params })

    return new Promise((resolvePromise, rejectPromise) => {
      const timer = setTimeout(() => {
        this.#pending.delete(id)
        rejectPromise(new Error(`timeout after ${this.timeoutMs}ms: ${method}`))
      }, this.timeoutMs)
      this.#pending.set(id, { resolve: resolvePromise, reject: rejectPromise, timer, method })
      this.#child.stdin.write(frame + '\n', 'utf8')
    })
  }

  /** Fire-and-forget notification (no reply is expected). */
  notify(method, params = {}) {
    if (this.#closed) return
    this.#child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n', 'utf8')
  }

  #onLine(line) {
    const text = line.trim()
    if (!text) return
    let frame
    try {
      frame = JSON.parse(text)
    } catch {
      this.dispatchEvent(new CustomEvent('stderr', {
        detail: `puzzle service wrote a non-JSON line on stdout: ${text.slice(0, 200)}`,
      }))
      return
    }
    const entry = this.#pending.get(frame.id)
    if (!entry) return
    this.#pending.delete(frame.id)
    clearTimeout(entry.timer)
    if (frame.error) {
      entry.reject(new RpcError(frame.error.code, frame.error.message, frame.error.data))
    } else {
      entry.resolve(frame.result)
    }
  }

  async info() {
    return this.call('server.info')
  }

  async listKinds() {
    return this.call('puzzle.list')
  }

  async newPuzzle({ sessionId = 'default', kind = null, difficulty = 'medium' } = {}) {
    return this.call('puzzle.new', { session_id: sessionId, kind, difficulty })
  }

  async submit({ sessionId = 'default', answer }) {
    return this.call('puzzle.submit', { session_id: sessionId, answer })
  }

  async action({ sessionId = 'default', action, ...params }) {
    return this.call('puzzle.action', { session_id: sessionId, action, ...params })
  }

  async hint({ sessionId = 'default' } = {}) {
    return this.call('puzzle.hint', { session_id: sessionId })
  }

  async state({ sessionId = 'default' } = {}) {
    return this.call('puzzle.state', { session_id: sessionId })
  }

  /** Ask the service to stop, then wait for the process to go away. */
  async close({ graceMs = 2000 } = {}) {
    if (this.#closed) return
    try {
      await Promise.race([
        this.call('server.shutdown'),
        new Promise((r) => setTimeout(r, 250)),
      ])
    } catch {
      // the child may already be gone; fall through to the hard stop
    }
    if (this.#closed) return
    await new Promise((resolvePromise) => {
      const done = () => resolvePromise()
      this.#child.once('exit', done)
      this.#child.kill()
      setTimeout(done, graceMs).unref?.()
    })
  }
}

function defaultPython() {
  return process.platform === 'win32' ? 'python' : 'python3'
}

export default PuzzleBridge
