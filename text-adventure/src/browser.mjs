// Launch a Chromium for the browser test, trying the cheapest option first.
//
// Why this is more than `chromium.launch()`: this machine already has a Playwright
// browser cache, but its build number (1243) does not match the one the installed
// playwright-core expects (1248), and Playwright's default headless mode insists on
// a separate "headless shell" package. `channel: 'chromium'` uses the full browser
// binary instead, which the existing cache satisfies — so nothing has to be
// downloaded. On a machine with no cache at all, the first strategy simply works.
//
// Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to point at a specific binary.
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

function cachedChromium() {
  const explicit = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  if (explicit && existsSync(explicit)) return explicit

  const cache = process.env.PLAYWRIGHT_BROWSERS_PATH && process.env.PLAYWRIGHT_BROWSERS_PATH !== '0'
    ? process.env.PLAYWRIGHT_BROWSERS_PATH
    : join(homedir(), 'AppData', 'Local', 'ms-playwright')
  if (!existsSync(cache)) return null

  // Newest build first: the cache keeps every build ever downloaded.
  const builds = readdirSync(cache)
    .filter((name) => /^chromium-\d+$/.test(name))
    .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
  for (const build of builds) {
    for (const relative of ['chrome-win64/chrome.exe', 'chrome-linux/chrome', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium']) {
      const candidate = join(cache, build, relative)
      if (existsSync(candidate)) return candidate
    }
  }
  return null
}

/** Launch Chromium, reporting which strategy worked. */
export async function launchChromium(chromium) {
  const cached = cachedChromium()
  const attempts = [
    { label: 'playwright default', options: { headless: true } },
    { label: 'channel=chromium', options: { headless: true, channel: 'chromium' } },
    ...(cached ? [{ label: `cached build (${cached})`, options: { headless: true, executablePath: cached } }] : []),
    ...(cached
      ? [{ label: 'channel=chromium + cached build', options: { headless: true, channel: 'chromium', executablePath: cached } }]
      : []),
  ]

  const problems = []
  for (const attempt of attempts) {
    try {
      const browser = await chromium.launch(attempt.options)
      return { browser, strategy: attempt.label }
    } catch (error) {
      problems.push(`${attempt.label}: ${error.message.split('\n')[0]}`)
    }
  }
  const error = new Error(
    `could not launch Chromium.\n  ${problems.join('\n  ')}\n` +
      'Install a browser with: npx playwright install chromium',
  )
  error.problems = problems
  throw error
}
