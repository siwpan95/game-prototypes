// View-model → DOM renderer.
//
// The whole point of the view-model contract: this file renders every puzzle
// kind, and adding a kind does not touch it. When a new primitive shows up that
// this file does not know, it throws — a blank screen is a worse outcome than a
// loud error, because a blank screen looks like "the puzzle is empty".
//
// Accessibility rules applied here (WCAG 2.2, see docs/_research/04-web-platform.md):
//   * nothing is conveyed by colour alone (SC 1.4.1): every colour swatch also
//     carries a symbol and its name in text;
//   * every pointer action has a keyboard path (buttons are real <button>s,
//     grid cells are focusable, the board also offers direction buttons);
//   * state changes are announced through a polite live region.
import { PRIMITIVES, UnknownPrimitive } from './primitives.js'

export { UnknownPrimitive }

const COLOUR_SYMBOLS = {
  red: { symbol: '◆', label: '红 red' },
  green: { symbol: '●', label: '绿 green' },
  blue: { symbol: '▲', label: '蓝 blue' },
  yellow: { symbol: '■', label: '黄 yellow' },
}

// The service sends a label *key* (it does not know which client renders the view
// model); the wording lives here, in the language this client's user reads. A key
// with no entry falls back to the default text the service also sends, so an
// unhandled key shows readable English rather than a raw identifier.
const LABELS_ZH = {
  answer: '答案',
  letter: '字母',
  word: '单词',
  next_word: '下一个单词（一次一步）',
}

const DIRECTIONS = [
  { direction: 'up', label: '↑ 上' },
  { direction: 'down', label: '↓ 下' },
  { direction: 'left', label: '← 左' },
  { direction: 'right', label: '→ 右' },
]

/** Render one view model into `root`, replacing its contents. */
export function renderView(root, view, handlers = {}) {
  const fragment = document.createDocumentFragment()
  const section = document.createElement('section')
  section.className = 'view'
  section.dataset.kind = view.kind
  section.dataset.interaction = view.interaction

  for (const node of view.nodes ?? []) {
    section.append(renderNode(node, handlers))
  }
  fragment.append(section)

  if (view.solved) {
    const done = document.createElement('p')
    done.className = 'solved'
    done.textContent = '✔ 已完成 — 选择「下一题」继续'
    fragment.append(done)
  }

  root.replaceChildren(fragment)
  return section
}

function renderNode(node, handlers) {
  const type = node.type
  if (!(type in PRIMITIVES)) throw new UnknownPrimitive(type)
  switch (type) {
    case 'text':
      return renderText(node)
    case 'field':
      return renderField(node, handlers)
    case 'options':
      return renderOptions(node, handlers)
    case 'list':
    case 'clues':
      return renderList(node)
    case 'grid':
      return renderGrid(node, handlers)
    case 'sequence':
      return renderSequence(node, handlers)
    case 'keyboard':
      return renderKeyboard(node, handlers)
    case 'colors':
      return renderColors(node, handlers)
    case 'board':
      return renderBoard(node, handlers)
    default:
      throw new UnknownPrimitive(type)
  }
}

function renderText(node) {
  const p = document.createElement('p')
  p.className = node.style === 'muted' ? 'text muted' : 'text'
  p.textContent = node.text ?? ''
  return p
}

function renderField(node, handlers) {
  const label = document.createElement('label')
  label.className = 'field'
  const caption = document.createElement('span')
  caption.textContent =
    LABELS_ZH[node.label_key] || node.label || node.label_key || '答案'
  const input = document.createElement('input')
  input.type = 'text'
  input.name = node.name || 'answer'
  input.autocomplete = 'off'
  input.dataset.answerType = node.answer_type || 'str'
  input.dataset.labelKey = node.label_key || ''
  input.setAttribute('aria-label', caption.textContent)
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      handlers.onAnswer?.(input.value)
    }
  })
  label.append(caption, input)
  label.querySelector('input').focus?.()
  return label
}

function renderOptions(node, handlers) {
  const list = document.createElement('ul')
  list.className = 'options'
  list.setAttribute('role', 'group')
  for (const item of node.items ?? []) {
    const li = document.createElement('li')
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'option'
    button.textContent = item.text
    button.addEventListener('click', () => handlers.onAnswer?.(item.answer))
    li.append(button)
    list.append(li)
  }
  return list
}

function renderList(node) {
  const list = document.createElement('ol')
  list.className = `list list-${node.name || 'items'}`
  for (const item of node.items ?? []) {
    const li = document.createElement('li')
    li.textContent = Array.isArray(item) ? item.join('  ') : String(item)
    list.append(li)
  }
  return list
}

function renderGrid(node, handlers) {
  const table = document.createElement('table')
  table.className = `grid grid-${node.name || 'grid'}`
  table.setAttribute('role', 'grid')
  table.dataset.action = node.action || ''
  for (const row of node.cells ?? []) {
    const tr = document.createElement('tr')
    for (const cell of row) {
      const td = document.createElement('td')
      td.tabIndex = 0
      td.dataset.row = cell.row
      td.dataset.col = cell.col
      td.textContent = cell.text ?? ''
      if (cell.label) td.dataset.label = cell.label
      if (cell.fixed) td.classList.add('fixed')
      if (cell.revealed) td.classList.add('revealed')
      if (cell.flagged) td.classList.add('flagged')
      if (cell.matched) td.classList.add('matched')
      td.setAttribute(
        'aria-label',
        `第 ${cell.row + 1} 行第 ${cell.col + 1} 列 ${cell.text || '空'}`,
      )
      const act = (withFlag) =>
        handlers.onAction?.(node.action, {
          row: cell.row,
          col: cell.col,
          ...(withFlag ? { flag: true } : {}),
        })
      td.addEventListener('click', () => act(false))
      td.addEventListener('contextmenu', (event) => {
        if (!node.secondary_action) return
        event.preventDefault()
        handlers.onAction?.(node.secondary_action, { row: cell.row, col: cell.col })
      })
      td.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          act(false)
        }
        if (event.key === 'f' && node.secondary_action) {
          event.preventDefault()
          handlers.onAction?.(node.secondary_action, { row: cell.row, col: cell.col })
        }
      })
      tr.append(td)
    }
    table.append(tr)
  }
  return table
}

function renderSequence(node, handlers) {
  const list = document.createElement('ol')
  list.className = 'sequence'
  let selected = null
  for (const [index, token] of (node.tokens ?? []).entries()) {
    const li = document.createElement('li')
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'token'
    button.textContent = token
    button.addEventListener('click', () => {
      if (!node.clickable) return
      if (selected === null) {
        selected = index
        button.classList.add('selected')
        return
      }
      const first = selected
      selected = null
      for (const other of list.querySelectorAll('.token')) other.classList.remove('selected')
      handlers.onAction?.(node.action, { idx1: first, idx2: index })
    })
    li.append(button)
    list.append(li)
  }
  return list
}

function renderKeyboard(node, handlers) {
  const wrap = document.createElement('div')
  wrap.className = 'keyboard'
  wrap.setAttribute('role', 'group')
  wrap.setAttribute('aria-label', '字母键盘')
  for (const key of node.keys ?? []) {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = `key key-${key.state}`
    button.textContent = key.letter
    button.disabled = key.state !== 'unused'
    button.setAttribute('aria-label', `${key.letter}（${key.state}）`)
    button.addEventListener('click', () => handlers.onAction?.(node.action, { letter: key.letter }))
    wrap.append(button)
  }
  return wrap
}

function renderColors(node, handlers) {
  const wrap = document.createElement('div')
  wrap.className = 'colors'
  wrap.setAttribute('role', 'group')
  wrap.setAttribute('aria-label', '颜色按钮（同时有符号与文字标识，不仅靠颜色区分）')
  for (const swatch of node.swatches ?? []) {
    const info = COLOUR_SYMBOLS[swatch.color] || { symbol: '?', label: swatch.label }
    const button = document.createElement('button')
    button.type = 'button'
    button.className = `swatch swatch-${swatch.color}`
    button.dataset.color = swatch.color
    button.textContent = `${info.symbol} ${info.label}`
    button.setAttribute('aria-label', info.label)
    button.addEventListener('click', () => handlers.onAction?.(node.action, { color: swatch.color }))
    wrap.append(button)
  }
  return wrap
}

function renderBoard(node, handlers) {
  const wrap = document.createElement('div')
  wrap.className = 'board'
  const table = renderGrid(node, handlers)
  table.classList.add('board-grid')
  wrap.append(table)

  const pad = document.createElement('div')
  pad.className = 'direction-pad'
  for (const { direction, label } of DIRECTIONS) {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = `direction direction-${direction}`
    button.textContent = label
    button.addEventListener('click', () => handlers.onAction?.(node.action, { direction }))
    pad.append(button)
  }
  wrap.append(pad)
  return wrap
}
