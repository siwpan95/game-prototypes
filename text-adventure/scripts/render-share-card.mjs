// Render a share card to a PNG.
//
// The card itself is SVG (produced by the Python service, see
// puzzle_service/profile.py). SVG is right for sharing — text stays text, so it
// scales, stays readable by a screen reader, and can be checked by a test — but a
// PNG is what a chat app or a README wants. This converts one to the other with
// the same browser the end-to-end test uses; no imaging dependency needed.
//
// Usage: node scripts/render-share-card.mjs <card.svg> <out.png> [width] [height]
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { launchChromium } from '../src/browser.mjs'

const [svgArg, pngArg, widthArg, heightArg] = process.argv.slice(2)
if (!svgArg || !pngArg) {
  console.error('usage: node scripts/render-share-card.mjs <card.svg> <out.png> [width] [height]')
  process.exit(2)
}

const svg = readFileSync(resolve(svgArg), 'utf8')
if (!svg.trimStart().startsWith('<svg')) {
  console.error(`${svgArg} does not look like an SVG document`)
  process.exit(2)
}

const width = Number(widthArg) || 480
const height = Number(heightArg) || 260

const { chromium } = await import('playwright-core')
const { browser } = await launchChromium(chromium)
try {
  const page = await browser.newPage({ viewport: { width: width + 40, height: height + 40 } })
  await page.setContent(`<body style="margin:0;background:#11111a">${svg}</body>`, {
    waitUntil: 'domcontentloaded',
  })
  await page.locator('svg').screenshot({ path: resolve(pngArg) })
  console.log(`wrote ${pngArg}`)
} finally {
  await browser.close()
}
