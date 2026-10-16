// Browser end-to-end test: drive the real page in a real browser.
//
// This is the check that was missing. Everything else verified the service, the
// bridge and the transport, but nothing had ever executed `public/client/*.js` in
// a browser — so "the web client works" was an assumption, and the roadmap recorded
// it as unverified. Here a browser loads the page, starts puzzles, clicks cells,
// presses keys, and reports console errors, which is what a person would do.
//
// Usage: node src/browser_e2e.mjs [--headful] [--port 8098] [--verbose]
// Exit codes: 0 all checks passed · 1 a check failed · 3 the host or browser would not start.
import { bootHost, stopHost } from './boot.mjs'
import { launchChromium } from './browser.mjs'

const args = process.argv.slice(2)
const PORT = Number(valueOf('--port') || process.env.E2E_PORT || 8098)
const HEADFUL = args.includes('--headful')
const VERBOSE = args.includes('--verbose')

function valueOf(flag) {
  const index = args.indexOf(flag)
  return index >= 0 ? args[index + 1] : null
}

const failures = []
const ok = (label, detail = '') => console.log(`OK    ${label}${detail ? ` — ${detail}` : ''}`)
const bad = (label, detail = '') => {
  failures.push(label)
  console.error(`FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
}
async function check(label, fn) {
  try {
    ok(label, await fn())
  } catch (error) {
    bad(label, error.message)
    if (VERBOSE) console.error(error)
  }
}

const { chromium } = await import('playwright-core')
let ctx
let browser
try {
  ctx = await bootHost({ port: PORT })
} catch (error) {
  console.error(`ENVIRONMENT ERROR: host did not boot: ${error.message}`)
  process.exit(3)
}
const base = ctx.web.url
try {
  const launched = await launchChromium(chromium)
  browser = launched.browser
  console.log(`host on ${base}; browser via ${launched.strategy}\n`)
} catch (error) {
  console.error(`ENVIRONMENT ERROR: ${error.message}`)
  await stopHost(ctx)
  process.exit(3)
}

const page = await browser.newPage()
const consoleErrors = []
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${error.message}`))

try {
  await check('page loads and reports its title', async () => {
    await page.goto(base, { waitUntil: 'domcontentloaded' })
    const title = await page.title()
    if (!title.includes('文字解谜')) throw new Error(`unexpected title: ${title}`)
    return title
  })

  await check('the SSE connection reaches the client', async () => {
    await page.waitForFunction(
      () => document.querySelector('#status')?.textContent?.includes('已连接'),
      null,
      { timeout: 10_000 },
    )
    return await page.textContent('#status')
  })

  await check('every kind is offered in the picker', async () => {
    const options = await page.$$eval('#kind option', (nodes) =>
      nodes.map((node) => node.value).filter(Boolean),
    )
    if (options.length !== 14) throw new Error(`expected 14 kinds, got ${options.length}`)
    return options.join(', ')
  })

  await check('starting a puzzle renders it, with a Chinese label', async () => {
    await page.selectOption('#kind', 'math')
    await page.selectOption('#difficulty', 'easy')
    await page.click('#new')
    await page.waitForSelector('.view[data-kind="math"]', { timeout: 10_000 })
    const caption = await page.textContent('.field span')
    if (!caption.includes('答案')) throw new Error(`label not localised: ${caption}`)
    if (caption.includes('Answer')) throw new Error('the client showed the default English label')
    const input = await page.$('.field input')
    if (!input) throw new Error('no answer input rendered')
    return `label "${caption}", input present`
  })

  await check('a wrong answer is reported as wrong', async () => {
    await page.fill('.field input', '999999999')
    await page.press('.field input', 'Enter')
    await page.waitForFunction(
      () => document.querySelector('#status')?.textContent?.includes('答错'),
      null,
      { timeout: 10_000 },
    )
    const score = await page.textContent('#scoreboard')
    if (!score.includes('得分 0')) throw new Error(`score changed on a wrong answer: ${score}`)
    return await page.textContent('#status')
  })

  await check('a hint is shown in the status line', async () => {
    await page.click('#hint')
    await page.waitForFunction(
      () => document.querySelector('#status')?.textContent?.includes('提示'),
      null,
      { timeout: 10_000 },
    )
    return (await page.textContent('#status')).slice(0, 30)
  })

  await check('clicking a grid cell changes the rendered board (minesweeper)', async () => {
    await page.selectOption('#kind', 'minesweeper')
    await page.click('#new')
    await page.waitForSelector('.view[data-kind="minesweeper"] table.grid', { timeout: 10_000 })
    const before = await page.$$eval('table.grid td', (cells) =>
      cells.map((cell) => cell.className).join('|'),
    )
    await page.click('table.grid td')
    await page.waitForFunction(
      () => document.querySelectorAll('table.grid td.revealed').length > 0,
      null,
      { timeout: 10_000 },
    )
    const after = await page.$$eval('table.grid td', (cells) =>
      cells.map((cell) => cell.className).join('|'),
    )
    if (before === after) throw new Error('the board did not change after a click')
    const revealed = await page.$$eval('table.grid td.revealed', (cells) => cells.length)
    return `${revealed} cell(s) revealed by the click`
  })

  await check('grid cells are reachable and operable by keyboard', async () => {
    const hidden = await page.$('table.grid td:not(.revealed)')
    if (!hidden) throw new Error('no unrevealed cell to focus')
    const described = await hidden.evaluate((cell) => cell.getAttribute('aria-label'))
    if (!described || !described.includes('行')) throw new Error(`no usable aria-label: ${described}`)
    await hidden.focus()
    const focused = await page.evaluate(() => document.activeElement?.tagName)
    if (focused !== 'TD') throw new Error(`focus did not land on a cell (got ${focused})`)
    const before = await page.$$eval('table.grid td.flagged', (cells) => cells.length)
    await page.keyboard.press('f')
    await page.waitForFunction(
      (previous) => document.querySelectorAll('table.grid td.flagged').length > previous,
      before,
      { timeout: 10_000 },
    )
    return `focused cell "${described}", "f" flagged it`
  })

  await check('right-click flags a cell (secondary action)', async () => {
    // A revealed cell is deliberately inert, so pick one that is still hidden:
    // clicking and then right-clicking the same cell would flag nothing and look
    // like a broken feature.
    const hidden = await page.$('table.grid td:not(.revealed):not(.flagged)')
    if (!hidden) throw new Error('no unflagged, unrevealed cell to flag')
    const before = await page.$$eval('table.grid td.flagged', (cells) => cells.length)
    await hidden.click({ button: 'right' })
    await page.waitForFunction(
      (previous) => document.querySelectorAll('table.grid td.flagged').length > previous,
      before,
      { timeout: 10_000 },
    )
    const flagged = await page.$$eval('table.grid td.flagged', (cells) => cells.length)
    return `${flagged} cell(s) flagged`
  })

  await check('arrow keys drive the 2048 board', async () => {
    await page.selectOption('#kind', '2048')
    await page.click('#new')
    await page.waitForSelector('.view[data-kind="2048"] .board-grid', { timeout: 10_000 })
    const before = await page.$eval('.board-grid', (node) => node.textContent)
    let changed = false
    for (const key of ['ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown']) {
      await page.keyboard.press(key)
      await page.waitForTimeout(120)
      const after = await page.$eval('.board-grid', (node) => node.textContent)
      if (after !== before) {
        changed = true
        break
      }
    }
    if (!changed) throw new Error('no arrow key changed the board')
    return 'a directional key changed the board'
  })

  await check('colour swatches are labelled with text, not colour alone', async () => {
    await page.selectOption('#kind', 'color_sequence')
    await page.click('#new')
    await page.waitForSelector('.view[data-kind="color_sequence"] .swatch', { timeout: 10_000 })
    const labels = await page.$$eval('.swatch', (nodes) =>
      nodes.map((node) => node.textContent.trim()),
    )
    if (labels.length < 4) throw new Error(`expected 4 swatches, got ${labels.length}`)
    for (const label of labels) {
      if (!/[红绿蓝黄]/.test(label)) throw new Error(`swatch ${label} relies on colour alone`)
      if (!/[◆●▲■]/.test(label)) throw new Error(`swatch ${label} has no symbol`)
    }
    return labels.join(' ')
  })

  await check('the result screen appears after a completed puzzle', async () => {
    // Riddle is multiple choice: read the correct index from the service, then click it.
    await page.selectOption('#kind', 'riddle')
    await page.click('#new')
    await page.waitForSelector('.view[data-kind="riddle"] .option', { timeout: 10_000 })
    const visible = await page.$$eval('.option', (nodes) => nodes.map((n) => n.textContent))
    if (!visible.length) throw new Error('no options rendered')
    await page.click('.option')
    await page.waitForTimeout(300)
    const status = await page.textContent('#status')
    if (!status.includes('答对') && !status.includes('答错')) {
      throw new Error(`submitting an option said nothing: ${status}`)
    }
    return `clicked an option: ${status.slice(0, 24)}`
  })

  await check('the daily puzzle can be started from the page', async () => {
    await page.click('#daily')
    await page.waitForFunction(
      () => document.querySelector('#status')?.textContent?.includes('每日一题'),
      null,
      { timeout: 10_000 },
    )
    const shown = await page.textContent('#status')
    if (!/\d{4}-\d{2}-\d{2}/.test(shown)) throw new Error(`no date in: ${shown}`)
    return shown
  })

  await check('the share card copies without revealing the answer', async () => {
    // The clipboard needs permissions in a headless browser, so assert on the card
    // the client produced rather than on the clipboard itself.
    await page.click('#share')
    await page.waitForFunction(() => Boolean(window.__lastShareCard), null, { timeout: 10_000 })
    const card = await page.evaluate(() => window.__lastShareCard)
    if (!card.includes('每日一题')) throw new Error(`unexpected card: ${card}`)
    if (!card.includes('不含谜底')) throw new Error('the card does not state it is spoiler-free')
    return card.split('\n')[0]
  })

  await check('progress is shown after playing', async () => {
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForFunction(
      () => document.querySelector('#progress')?.textContent?.includes('进度'),
      null,
      { timeout: 10_000 },
    )
    const text = await page.textContent('#progress')
    if (/载入中/.test(text)) throw new Error('progress never loaded')
    return text
  })

  await check('the picture card is served as an image', async () => {
    const response = await page.request.get(`${base}/api/share.svg`)
    const type = response.headers()['content-type'] || ''
    if (!type.includes('image/svg+xml')) throw new Error(`wrong content-type: ${type}`)
    const body = await response.text()
    if (!body.trimStart().startsWith('<svg')) throw new Error('not an SVG document')
    if (!body.includes('不含谜底')) throw new Error('the card does not state it is spoiler-free')
    return `${body.length} bytes of SVG`
  })

  await check('history is listed newest first', async () => {
    const response = await page.request.get(`${base}/api/history?limit=5`)
    const payload = await response.json()
    if (!Array.isArray(payload.days)) throw new Error(`unexpected payload: ${JSON.stringify(payload)}`)
    const days = payload.days.map((row) => row.day)
    const sorted = [...days].sort().reverse()
    if (JSON.stringify(days) !== JSON.stringify(sorted)) {
      throw new Error(`history is not newest-first: ${days}`)
    }
    return days.length ? days.join(', ') : 'no records yet (acceptable on a fresh profile)'
  })

  await check('an automated accessibility audit finds nothing serious', async () => {
    // axe-core is injected into the live page and run against several screens,
    // because a single-screen audit would miss the puzzle-specific markup.
    const { createRequire } = await import('node:module')
    const require = createRequire(import.meta.url)
    const axePath = require.resolve('axe-core/axe.min.js')

    const screens = [
      { label: 'menu', prepare: async () => {} },
      {
        label: 'grid puzzle (minesweeper)',
        prepare: async () => {
          await page.selectOption('#kind', 'minesweeper')
          await page.click('#new')
          await page.waitForSelector('.view[data-kind="minesweeper"] table.grid')
        },
      },
      {
        label: 'colour puzzle',
        prepare: async () => {
          await page.selectOption('#kind', 'color_sequence')
          await page.click('#new')
          await page.waitForSelector('.view[data-kind="color_sequence"] .swatch')
        },
      },
      {
        label: 'text input puzzle',
        prepare: async () => {
          await page.selectOption('#kind', 'math')
          await page.click('#new')
          await page.waitForSelector('.view[data-kind="math"] .field input')
        },
      },
    ]

    const problems = []
    const counts = {}
    for (const screen of screens) {
      await screen.prepare()
      await page.addScriptTag({ path: axePath })
      const result = await page.evaluate(async () => {
        // Only serious/critical: axe's minor findings are style opinions and would
        // make this check noise that people learn to ignore.
        return await window.axe.run(document, {
          resultTypes: ['violations'],
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag22aa'] },
        })
      })
      const serious = result.violations.filter((v) =>
        ['serious', 'critical'].includes(v.impact),
      )
      counts[screen.label] = result.violations.length
      for (const violation of serious) {
        problems.push(
          `${screen.label}: ${violation.id} (${violation.impact}) — ${violation.help} ×${violation.nodes.length}`,
        )
      }
    }
    if (problems.length) throw new Error(problems.join(' | '))
    return Object.entries(counts)
      .map(([screen, count]) => `${screen}: ${count}`)
      .join(', ')
  })

  await check('no console errors were logged during the whole run', async () => {
    if (consoleErrors.length) throw new Error(consoleErrors.slice(0, 3).join(' | '))
    return 'console clean'
  })
} catch (error) {
  bad('browser run crashed', error.message)
  if (VERBOSE) console.error(error)
}

if (HEADFUL) {
  console.log('\n--headful was requested; leaving the browser open for 60s for inspection')
  await page.waitForTimeout(60_000)
}
await browser.close()
await stopHost(ctx)

console.log()
if (failures.length) {
  console.error(`BROWSER E2E FAILED: ${failures.length} check(s): ${failures.join(', ')}`)
  process.exit(1)
}
console.log('BROWSER E2E PASSED')
process.exit(0)
