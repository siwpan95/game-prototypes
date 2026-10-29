// Sole host entry point: boot, report, and shut down on a signal.
//
// Every other entry point (the smoke test, future test files) imports
// `bootHost`/`stopHost` from here, so there is exactly one definition of "how
// the host starts" — two bootstraps drift, and the drift shows up as a smoke
// test that passes while the real server does not.
import { pathToFileURL } from 'node:url'

/** Start the Cordis host from cordis.json. Returns the root Context. */
export async function bootHost({ config = 'cordis.json', quiet = false, port = null } = {}) {
  const { readFile } = await import('node:fs/promises')
  const { Context } = await import('cordis')
  const { default: Loader } = await import('@cordisjs/plugin-loader')
  const { default: ConsoleExporter } = await import('@cordisjs/plugin-logger-console')

  const ctx = new Context()
  // The console exporter must be installed first: without it, loader failures
  // travel the logger's error path and the host dies without saying why.
  await ctx.plugin(ConsoleExporter)

  await ctx.plugin(Loader, { baseUrl: pathToFileURL(process.cwd() + '/').href })
  if (!ctx.loader) {
    throw new Error('@cordisjs/plugin-loader did not expose ctx.loader; refusing to continue')
  }
  if (quiet && ctx.loader.config) {
    ctx.loader.config.levels = { default: 2 }
  }
  const entries = JSON.parse(await readFile(config, 'utf8')).entries || []
  for (const entry of entries) {
    // A caller-supplied port wins over cordis.json so a smoke test never fights
    // a game the user already has running on the default port.
    const override =
      port && entry.id === 'web' ? { ...entry, config: { ...(entry.config || {}), port } } : entry
    await ctx.loader.create({ ...override })
  }
  await ctx.loader.await()

  // A loaded plugin is not yet a working service: wait for the puzzle process to
  // answer and the socket to listen, so callers of bootHost() can use it at once.
  const gates = [ctx.puzzles?.ready, ctx.web?.ready].filter(Boolean)
  if (!gates.length) {
    throw new Error(`no service became ready; check the entries in ${config}`)
  }
  await Promise.all(gates)
  return ctx
}

/**
 * Shut the host down: dispose the top-level entries in reverse order, then stop
 * the puzzle child explicitly (a killed child would otherwise outlive the host).
 *
 * Note: in this loader version a tree entry is an object, not the key/value pair
 * that `Map` iteration suggests, so entries without a `fiber` are skipped.
 */
export async function stopHost(ctx) {
  if (!ctx) return
  const entries = [...ctx.loader.root.tree.entries()]
  const withFiber = entries.filter((entry) => entry && typeof entry === 'object' && entry.fiber)
  for (const entry of withFiber.reverse()) {
    try {
      await entry.fiber.dispose()
    } catch (error) {
      ctx.logger.warn('dispose %s failed: %s', entry.options?.id, error.message)
    }
  }
  if (ctx.puzzles) {
    await ctx.puzzles.stop().catch(() => {})
  }
  ctx.logger.info('host stopped (disposed %d entries)', withFiber.length)
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href
if (isMain) {
  const ctx = await bootHost()
  if (!ctx.web) {
    ctx.logger.error('web plugin did not load; check cordis.json entries and the logs above')
    await stopHost(ctx)
    process.exit(1)
  }
  ctx.logger.info('ready — open %s', ctx.web.url)
  const shutdown = async (signal) => {
    ctx.logger.info('received %s, stopping', signal)
    await stopHost(ctx)
    process.exit(0)
  }
  process.on('SIGINT', () => shutdown('SIGINT'))
  process.on('SIGTERM', () => shutdown('SIGTERM'))
}
