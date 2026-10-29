// The primitive whitelist, browser copy.
//
// The authoritative copy is src/plugins/render.mjs, which the Node host uses to
// validate every view model before it is sent (an unknown primitive becomes a
// 500, not a blank page). This file mirrors the *names* only, so the browser
// renderer can fail with the same message instead of guessing. A test asserts
// the two lists stay equal (tests/test_host_contract.py).
export const PRIMITIVES = {
  text: 'plain text',
  field: 'labelled text input',
  options: 'clickable choices',
  list: 'text list',
  clues: 'numeric clue list',
  grid: 'table of cells',
  sequence: 'ordered tokens',
  keyboard: 'letter keyboard',
  colors: 'colour swatches with symbols',
  board: 'directional board',
}

export class UnknownPrimitive extends Error {
  constructor(type) {
    super(
      `view primitive ${JSON.stringify(type)} is not registered; ` +
        `known primitives: ${Object.keys(PRIMITIVES).join(', ')}. ` +
        'Add it to src/plugins/render.mjs and public/client/render.js together.',
    )
    this.name = 'UnknownPrimitive'
    this.primitive = type
  }
}
