// PuzzleService plugin: owns the Python puzzle process and exposes it as ctx.puzzles.
//
// The Cordis half of "everything is a plugin": the host does not know what a
// puzzle is, only that a service can list kinds, start one, submit an answer or
// perform an action. Swapping the backend (another language, another process,
// a recorded fixture) means replacing this one file.
//
// Lifecycle is Cordis's job, not the caller's: the child process is stopped when
// the plugin is disposed, and `ctx.effect` is what guarantees it.
import { Service } from 'cordis'
import { PuzzleBridge } from '../core/bridge.mjs'

export class PuzzleService extends Service {
  static provide = 'puzzles'

  constructor(ctx, config = {}) {
    super(ctx, 'puzzles')
    this.config = config
    this.bridge = new PuzzleBridge({
      language: config.language || 'zh',
      python: config.python || undefined,
      timeoutMs: config.timeoutMs || 15_000,
    })
    this.bridge.addEventListener('stderr', (event) => this.ctx.logger.debug('[python] %s', event.detail))
    this.bridge.addEventListener('exit', (event) => {
      if (!this.#disposing) this.ctx.logger.warn('puzzle process exited: %o', event.detail)
    })
    this.ctx.effect(() => () => this.bridge.close())

    // `ready` is the host's gate: bootHost awaits it, so "the host is up" means
    // the puzzle process answered, not merely that the plugin was constructed.
    this.ready = this.#handshake()
  }

  #disposing = false

  async #handshake() {
    try {
      const info = await this.bridge.info()
      this.ctx.logger.info('puzzle service ready (language=%s, kinds=%d)', info.language, info.kinds)
      return info
    } catch (error) {
      this.ctx.logger.error('puzzle service handshake failed: %s', error.message)
      throw error
    }
  }

  listKinds() {
    return this.bridge.listKinds()
  }

  newPuzzle(options) {
    return this.bridge.newPuzzle(options)
  }

  submit(options) {
    return this.bridge.submit(options)
  }

  action(options) {
    return this.bridge.action(options)
  }

  hint(options) {
    return this.bridge.hint(options)
  }

  state(options) {
    return this.bridge.state(options)
  }

  reset(options) {
    return this.bridge.reset(options)
  }

  /** Ask the child to stop before the Cordis dispose runs. */
  async stop() {
    this.#disposing = true
    await this.bridge.close()
  }
}

export default PuzzleService
