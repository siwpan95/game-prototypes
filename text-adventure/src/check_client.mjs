// Acceptance check for the browser client that the pytest suite cannot do:
// the client files must parse as modules, and every DOM id the client selects
// must exist in index.html. A typo here would surface as a blank page with a
// console error, which no server-side test would catch.
//
// Exit codes: 0 all good · 1 a check failed.
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

// `node:module`'s parse() is not available in this Node line, and `new Function`
// cannot compile `import` statements. SourceTextModule is the documented way to
// compile ESM in-process; it needs --experimental-vm-modules, so fall back to a
// token-level check that still catches unbalanced brackets and stray quotes
// rather than silently passing the files as "unchecked".
const canCompileModules = (() => {
  try {
    new vm.SourceTextModule('export const ok = 1')
    return true
  } catch {
    return false
  }
})()

function syntaxProblems(source, file) {
  if (canCompileModules) {
    try {
      new vm.SourceTextModule(source, { identifier: file })
      return null
    } catch (error) {
      return error.message
    }
  }
  const stripped = source
    .replace(/^\s*import\s.+$/gm, '')
    .replace(/^\s*export\s+(?=(const|let|var|function|class))/gm, '')
    .replace(/^\s*export\s*\{[^}]*\}\s*;?$/gm, '')
  try {
    new Function(stripped)
    return null
  } catch (error) {
    return `${error.message} (checked without --experimental-vm-modules)`
  }
}

const failures = []
const ok = (label, detail = '') => console.log(`OK    ${label}${detail ? ` — ${detail}` : ''}`)
const bad = (label, detail = '') => {
  failures.push(label)
  console.error(`FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
}

for (const file of ['public/client/app.js', 'public/client/render.js', 'public/client/primitives.js']) {
  const source = readFileSync(file, 'utf8')
  const problem = syntaxProblems(source, file)
  if (problem) bad(`parses as a module: ${file}`, problem)
  else ok(`parses as a module: ${file}`)
}

const html = readFileSync('public/index.html', 'utf8')
const app = readFileSync('public/client/app.js', 'utf8')
const htmlIds = new Set([...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]))
const selected = new Set([...app.matchAll(/\$\('#([A-Za-z0-9_-]+)'\)/g)].map((m) => m[1]))

if (!selected.size) bad('app.js selects DOM elements', 'no $("#id") selectors found')
const unbound = [...selected].filter((id) => !htmlIds.has(id))
if (unbound.length) bad('every selected id exists in index.html', unbound.join(', '))
else ok('every selected id exists in index.html', [...selected].join(', '))

// The client must import the whitelist copy, not redeclare one.
if (!app.includes("from './render.js'")) bad('app.js imports the renderer', 'no import found')
else ok('app.js imports the renderer')

// The stylesheet must keep the keyboard-visible focus ring (accessibility guard).
if (!html.includes(':focus-visible')) bad('index.html keeps a visible focus ring')
else ok('index.html keeps a visible focus ring')

console.log()
if (failures.length) {
  console.error(`CLIENT CHECK FAILED: ${failures.join(', ')}`)
  process.exit(1)
}
console.log('CLIENT CHECK PASSED')
