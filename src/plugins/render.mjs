// View-primitive registry: the whitelist that makes "one client renders every kind" safe.
//
// The Python service publishes view models built from a fixed primitive set. This
// module is the other half of that contract: each primitive maps to known
// semantic HTML, and an unknown primitive fails loudly instead of silently
// rendering an empty screen. That failure mode matters — a half-added puzzle kind
// must be visible in the smoke test, not in a user's browser.
//
// Each entry: { tag, role, describe, accessibility } where `accessibility`
// records how the primitive stays usable without a mouse or a screen.
export const PRIMITIVES = {
  text: {
    tag: 'p',
    role: null,
    accessibility: 'plain text, read in document order',
  },
  field: {
    tag: 'label',
    role: 'textbox',
    accessibility: 'native <input> labelled by its prompt; Enter submits',
  },
  options: {
    tag: 'ul',
    role: 'radiogroup',
    accessibility: 'option buttons are real <button>s, reachable by Tab',
  },
  list: {
    tag: 'ol',
    role: 'list',
    accessibility: 'clue list rendered as text, not as an image',
  },
  clues: {
    tag: 'ol',
    role: 'list',
    accessibility: 'numeric clue list rendered as text',
  },
  grid: {
    tag: 'table',
    role: 'grid',
    accessibility: 'cells are focusable; row/column announced via aria-label',
  },
  sequence: {
    tag: 'ol',
    role: 'list',
    accessibility: 'tokens have textual labels; clicking is never the only action',
  },
  keyboard: {
    tag: 'div',
    role: 'group',
    accessibility: 'letter buttons state (correct/wrong/unused) is announced in the label',
  },
  colors: {
    tag: 'div',
    role: 'group',
    accessibility:
      'never colour-only (WCAG 2.2 SC 1.4.1): every swatch carries a symbol and a name',
  },
  board: {
    tag: 'table',
    role: 'grid',
    accessibility: 'arrow keys move; board also offers on-screen direction buttons',
  },
}

export class UnknownPrimitive extends Error {
  constructor(type) {
    super(
      `view primitive ${JSON.stringify(type)} is not registered; ` +
        `known primitives: ${Object.keys(PRIMITIVES).join(', ')}. ` +
        'Add it to src/plugins/render.mjs (and to puzzle_service/views.py) together.',
    )
    this.name = 'UnknownPrimitive'
    this.primitive = type
  }
}

/** Names of the registered primitives. */
export function primitives() {
  return Object.keys(PRIMITIVES)
}

/**
 * Validate a whole view model before any of it is sent to a client.
 *
 * Returns `{ ok, primitives: [...], problems: [...] }`. Callers decide whether a
 * problem is fatal; `assertView` is the strict form used on the request path.
 */
export function inspectView(view) {
  const problems = []
  const seen = new Set()
  if (!view || typeof view !== 'object') {
    return { ok: false, primitives: [], problems: ['view is not an object'] }
  }
  const nodes = Array.isArray(view.nodes) ? view.nodes : []
  if (!nodes.length) problems.push('view has no nodes')
  for (const [index, node] of nodes.entries()) {
    const type = node?.type
    if (!type) {
      problems.push(`node ${index} has no type`)
      continue
    }
    if (!(type in PRIMITIVES)) {
      problems.push(`node ${index}: unknown primitive ${JSON.stringify(type)}`)
      continue
    }
    seen.add(type)
    if (type === 'field' && !node.answer_type) {
      problems.push(`node ${index}: field has no answer_type`)
    }
    if (type === 'grid' && !Array.isArray(node.cells)) {
      problems.push(`node ${index}: grid has no cells array`)
    }
    if (type === 'options' && !Array.isArray(node.items)) {
      problems.push(`node ${index}: options has no items array`)
    }
  }
  return { ok: problems.length === 0, primitives: [...seen], problems }
}

/** Strict form: throw on the first problem so the caller returns a 500, not a blank page. */
export function assertView(view) {
  const report = inspectView(view)
  if (!report.ok) {
    const first = report.problems[0]
    if (first.includes('unknown primitive')) {
      const match = first.match(/unknown primitive "([^"]+)"/)
      throw new UnknownPrimitive(match ? match[1] : '?')
    }
    throw new Error(`invalid view model: ${report.problems.join('; ')}`)
  }
  return report
}

export default { PRIMITIVES, primitives, inspectView, assertView, UnknownPrimitive }
