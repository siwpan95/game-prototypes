// Browser client: POST for actions, SSE for snapshots.
//
// The client holds no game logic. It renders whatever view model arrives and
// posts user intent back, which is what lets one client serve all 14 puzzle
// kinds and lets the host move to another port or process without a rebuild.
import { renderView } from './render.js'

const $ = (selector) => document.querySelector(selector)
const status = $('#status')
const scoreboard = $('#scoreboard')
const progress = $('#progress')
const board = $('#board')

let lastPuzzleId = null
let kinds = []

function announce(message) {
  status.textContent = message
}

async function api(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  const payload = await response.json().catch(() => ({ error: 'server sent no JSON' }))
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`)
  return payload
}

function paint(snapshot) {
  if (!snapshot) return
  scoreboard.textContent =
    `得分 ${snapshot.score} · 连击 ${snapshot.streak} · 已完成 ${snapshot.solved} · 用时 ${snapshot.elapsed}s`
  if (snapshot.profile) {
    progress.textContent =
      `进度：玩过 ${snapshot.profile.days_played} 天 · 累计完成 ${snapshot.profile.total_solved} · ` +
      `连续 ${snapshot.profile.current_streak} 天（最佳 ${snapshot.profile.best_streak} 天）`
  }
  if (snapshot.daily) {
    status.textContent =
      `每日一题 ${snapshot.daily.day}（${snapshot.daily.kind}）` +
      (snapshot.daily.played ? ' — 这一天已玩过，按最好成绩保留' : '')
  }
  if (!snapshot.view) {
    board.replaceChildren(Object.assign(document.createElement('p'), {
      className: 'placeholder', textContent: '选择一种谜题开始。',
    }))
    return
  }
  const isNewPuzzle = snapshot.puzzle_id !== lastPuzzleId
  lastPuzzleId = snapshot.puzzle_id
  renderView(board, snapshot.view, {
    onAnswer: submitAnswer,
    onAction: (action, params) => performAction(action, params, isNewPuzzle),
  })
  if (snapshot.last_result && 'correct' in snapshot.last_result) {
    announce(snapshot.last_result.correct ? '答对了！' : '答错了，连击已重置')
  }
  if (snapshot.action_result?.message) announce(String(snapshot.action_result.message))
}

async function submitAnswer(answer) {
  try {
    paint(await api('/api/answer', { answer: String(answer ?? '') }))
  } catch (error) {
    announce(`提交失败：${error.message}`)
  }
}

async function performAction(action, params, quiet) {
  try {
    const snapshot = await api('/api/action', { action, ...params })
    paint(snapshot)
    if (!quiet) announce(`已执行 ${action}`)
  } catch (error) {
    announce(`操作失败：${error.message}`)
  }
}

async function newPuzzle() {
  try {
    const kind = $('#kind').value
    const difficulty = $('#difficulty').value
    lastPuzzleId = null
    paint(await api('/api/new', { kind: kind || null, difficulty }))
    announce(`新谜题：${kind || '自动选择'}`)
  } catch (error) {
    announce(`开局失败：${error.message}`)
  }
}

async function hint() {
  try {
    const { hint: text } = await api('/api/hint', {})
    announce(`提示：${text}`)
  } catch (error) {
    announce(`提示失败：${error.message}`)
  }
}

function subscribe() {
  const events = new EventSource('/api/events')
  events.addEventListener('snapshot', (event) => paint(JSON.parse(event.data)))
  events.addEventListener('error', (event) => {
    if (event.data) announce(`服务端错误：${JSON.parse(event.data).message}`)
  })
  events.addEventListener('open', () => announce('已连接'))
  events.addEventListener('error', () => {
    // EventSource reconnects on its own; say so instead of pretending it is fine.
    announce('连接中断，正在重连…')
  })
}

async function loadKinds() {
  const payload = await (await fetch('/api/kinds')).json()
  kinds = payload.kinds || []
  const select = $('#kind')
  for (const kind of kinds) {
    const option = document.createElement('option')
    option.value = kind.name
    option.textContent = `${kind.title}（${kind.interaction}）`
    select.append(option)
  }
}

async function startDaily() {
  try {
    lastPuzzleId = null
    paint(await api('/api/daily', {}))
  } catch (error) {
    announce(`每日一题开局失败：${error.message}`)
  }
}

async function showShare() {
  try {
    const { card } = await (await fetch('/api/share')).json()
    announce('分享卡片已复制到剪贴板')
    // Best effort: the clipboard needs a secure context and a user gesture, so a
    // failure is shown rather than swallowed.
    try {
      await navigator.clipboard.writeText(card)
    } catch {
      announce(`无法自动复制，请手动复制：\n${card}`)
    }
    window.__lastShareCard = card
  } catch (error) {
    announce(`分享卡片失败：${error.message}`)
  }
}

async function refreshProgress() {
  try {
    const payload = await (await fetch('/api/profile')).json()
    if (payload.remember) {
      progress.textContent =
        `进度：玩过 ${payload.days_played} 天 · 累计完成 ${payload.total_solved} · ` +
        `连续 ${payload.current_streak} 天（最佳 ${payload.best_streak} 天）`
    } else {
      progress.textContent = '进度记录未开启'
    }
  } catch {
    progress.textContent = ''
  }
}

$('#new').addEventListener('click', newPuzzle)
$('#daily').addEventListener('click', startDaily)
$('#share').addEventListener('click', showShare)
$('#hint').addEventListener('click', hint)
$('#reset').addEventListener('click', async () => {
  paint(await api('/api/reset', {}))
  announce('已重置')
})

// Arrow keys drive directional puzzles without hunting for the buttons.
document.addEventListener('keydown', (event) => {
  const map = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' }
  const direction = map[event.key]
  if (!direction) return
  if (document.activeElement && document.activeElement.tagName === 'INPUT') return
  event.preventDefault()
  performAction('move', { direction }, true)
})

loadKinds()
  .then(refreshProgress)
  .then(subscribe)
  .catch((error) => announce(`初始化失败：${error.message}`))
