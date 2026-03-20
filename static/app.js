'use strict';

// ── API helper ────────────────────────────────────────────────────────────────
async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch('/api' + path, opts);
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── State ─────────────────────────────────────────────────────────────────────
let board = [];        // [{id, name, position, cards: [...]}]
let currentCard = null;
let commentPollTimer = null;

// ── Date utilities ────────────────────────────────────────────────────────────
function formatDate(d) {
  if (!d) return null;
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function dueDateClass(d) {
  if (!d) return '';
  const today = new Date(); today.setHours(0,0,0,0);
  const due   = new Date(d + 'T00:00:00');
  const diff  = (due - today) / 86400000;
  if (diff < 0)  return 'overdue';
  if (diff <= 2) return 'due-soon';
  return '';
}

// ── HTML escaping ─────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Board rendering ───────────────────────────────────────────────────────────
async function loadBoard() {
  board = await api('/board');
  renderBoard();
}

function renderBoard() {
  const el = document.getElementById('board');
  el.innerHTML = '';
  board.forEach(col => el.appendChild(buildColumn(col)));
}

function buildColumn(col) {
  const wrap = document.createElement('div');
  wrap.className = 'column';
  wrap.dataset.colId = col.id;

  wrap.innerHTML = `
    <div class="column-header">
      <span>${esc(col.name)}</span>
      <span class="column-count">${col.cards.length}</span>
    </div>
    <div class="cards-list" id="cards-${col.id}">
      ${col.cards.map(cardHTML).join('')}
    </div>
    <div class="card-add-area">
      <div class="add-card-form" id="add-form-${col.id}">
        <textarea class="add-card-textarea" placeholder="Enter a title for this card…" rows="2"
          onkeydown="addCardKey(event,${col.id})"></textarea>
        <div class="form-actions">
          <button class="btn-primary" onclick="submitAddCard(${col.id})">Add card</button>
          <button class="btn-cancel-x" onclick="hideAddForm(${col.id})">&#x2715;</button>
        </div>
      </div>
      <button class="add-card-btn" id="add-btn-${col.id}" onclick="showAddForm(${col.id})">
        + Add a card
      </button>
    </div>`;

  initSortable(wrap.querySelector(`#cards-${col.id}`));
  return wrap;
}

function cardHTML(card) {
  const priClass = card.priority !== 'none' ? `priority-${card.priority}` : '';
  const dateStr  = formatDate(card.due_date);
  const dateClass = dueDateClass(card.due_date);
  const total = card.total_items || 0;
  const done  = card.completed_items || 0;

  const dateBadge = dateStr
    ? `<span class="badge ${dateClass}">&#128197; ${dateStr}</span>` : '';
  const clBadge = total > 0
    ? `<span class="badge ${done === total ? 'cl-done' : ''}">&#9745; ${done}/${total}</span>` : '';
  const priLabel = { low: '&#128994; Low', medium: '&#128993; Med', high: '&#128308; High' };
  const priBadge = card.priority !== 'none'
    ? `<span class="badge">${priLabel[card.priority]}</span>` : '';

  return `
    <div class="card ${priClass}" data-id="${card.id}" onclick="openCard(${card.id})">
      <div class="card-title">${esc(card.title)}</div>
      <div class="card-badges">${dateBadge}${clBadge}${priBadge}</div>
    </div>`;
}

// ── Sortable drag-and-drop ────────────────────────────────────────────────────
function initSortable(listEl) {
  Sortable.create(listEl, {
    group: 'kanban-cards',
    animation: 150,
    ghostClass: 'sortable-ghost',
    onEnd: handleDrop,
  });
}

async function handleDrop(evt) {
  const cardId      = parseInt(evt.item.dataset.id);
  const srcColEl    = evt.from.closest('.column');
  const tgtColEl    = evt.to.closest('.column');
  const srcColId    = parseInt(srcColEl.dataset.colId);
  const tgtColId    = parseInt(tgtColEl.dataset.colId);

  const srcIds = [...evt.from.querySelectorAll('.card')].map(c => parseInt(c.dataset.id));
  const tgtIds = [...evt.to.querySelectorAll('.card')].map(c => parseInt(c.dataset.id));

  try {
    await api(`/cards/${cardId}/move`, 'POST', {
      column_id:        tgtColId,
      source_column_id: srcColId,
      source_ids:       srcColId === tgtColId ? tgtIds : srcIds,
      target_ids:       tgtIds,
    });
    await loadBoard();
  } catch (e) {
    console.error('Move failed:', e);
    await loadBoard();
  }
}

// ── Add card ──────────────────────────────────────────────────────────────────
function showAddForm(colId) {
  document.getElementById(`add-form-${colId}`).classList.add('active');
  document.getElementById(`add-btn-${colId}`).style.display = 'none';
  document.querySelector(`#add-form-${colId} textarea`).focus();
}

function hideAddForm(colId) {
  document.getElementById(`add-form-${colId}`).classList.remove('active');
  document.getElementById(`add-btn-${colId}`).style.display = '';
  document.querySelector(`#add-form-${colId} textarea`).value = '';
}

function addCardKey(e, colId) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitAddCard(colId); }
  if (e.key === 'Escape') hideAddForm(colId);
}

async function submitAddCard(colId) {
  const ta = document.querySelector(`#add-form-${colId} textarea`);
  const title = ta.value.trim();
  if (!title) return;
  try {
    await api('/cards', 'POST', { title, column_id: colId });
    hideAddForm(colId);
    await loadBoard();
  } catch (e) { console.error(e); }
}

// ── Card modal open/close ─────────────────────────────────────────────────────
async function openCard(cardId) {
  try {
    currentCard = await api(`/cards/${cardId}`);
    renderModal(currentCard);
    document.getElementById('modal-overlay').classList.remove('hidden');
    await loadComments();
  } catch (e) { console.error(e); }
}

function closeModal() {
  stopCommentPoll();
  document.getElementById('modal-overlay').classList.add('hidden');
  currentCard = null;
  loadBoard(); // refresh board to pick up any changes
}

function onOverlayClick(e, overlayId) {
  if (e.target.id === overlayId) {
    if (overlayId === 'modal-overlay') closeModal();
    else closeArchive();
  }
}

// ── Modal rendering ───────────────────────────────────────────────────────────
function renderModal(card) {
  const col = board.find(c => c.id === card.column_id);
  const colName = col ? col.name : '';
  const priOptions = ['none','low','medium','high']
    .map(p => `<option value="${p}" ${card.priority===p?'selected':''}>${
      {none:'None',low:'🟢 Low',medium:'🟡 Medium',high:'🔴 High'}[p]
    }</option>`).join('');

  document.getElementById('modal').innerHTML = `
    <button class="modal-close" onclick="closeModal()">&#x2715;</button>

    <div class="modal-header">
      <span class="modal-header-icon">&#128203;</span>
      <div class="modal-title-wrap">
        <textarea class="modal-title-input" id="m-title" rows="1">${esc(card.title)}</textarea>
        <div class="modal-col-label">in column <strong>${esc(colName)}</strong></div>
      </div>
    </div>

    <div class="modal-body">
      <div class="modal-main">

        <!-- Description -->
        <div class="desc-section">
          <div class="section-heading">&#128221; Description</div>
          <div id="desc-display" class="desc-display ${!card.description ? 'placeholder' : ''}"
               onclick="editDesc()">${card.description ? esc(card.description) : 'Add a more detailed description…'}</div>
          <textarea id="desc-ta" class="desc-textarea"
            placeholder="Add a more detailed description…">${esc(card.description || '')}</textarea>
          <div id="desc-actions" class="desc-actions">
            <button class="btn-primary" onclick="saveDesc()">Save</button>
            <button class="btn-cancel-text" onclick="cancelDesc()">Cancel</button>
          </div>
        </div>

        <!-- Checklists -->
        <div id="checklists-section">
          ${card.checklists.map(checklistHTML).join('')}
        </div>

        <!-- Comments -->
        <div class="comments-section">
          <div class="section-heading">&#128172; Activity</div>
          <div id="comments-list"><div class="comments-loading">Loading…</div></div>
          <div class="comment-form">
            <textarea id="comment-ta" class="comment-textarea"
              placeholder="Write a comment… (use @claude to ask Claude)"
              rows="2" onkeydown="commentKey(event)"></textarea>
            <div class="comment-form-actions">
              <button class="btn-primary" onclick="submitComment()">Save</button>
            </div>
          </div>
        </div>

      </div>

      <div class="modal-sidebar">

        <!-- Priority -->
        <div class="sidebar-group">
          <div class="sidebar-label">Priority</div>
          <select class="sidebar-select priority-${card.priority}" id="m-priority"
                  onchange="updatePriority(this.value)">${priOptions}</select>
        </div>

        <!-- Due date -->
        <div class="sidebar-group">
          <div class="sidebar-label">Due Date</div>
          <input type="date" class="sidebar-date" id="m-due"
                 value="${card.due_date || ''}" onchange="updateDueDate(this.value)">
        </div>

        <!-- Actions -->
        <div class="sidebar-group">
          <div class="sidebar-label">Add</div>
          <button class="sidebar-btn" onclick="addChecklist()">&#9745; Checklist</button>
        </div>

        <div class="sidebar-group">
          <div class="sidebar-label">Actions</div>
          <button class="sidebar-btn danger" onclick="archiveCard()">&#128451; Archive Card</button>
          <button class="sidebar-btn danger" onclick="deleteCard()">&#128465; Delete Card</button>
        </div>

      </div>
    </div>`;

  // Auto-resize title
  const titleEl = document.getElementById('m-title');
  autoResize(titleEl);
  titleEl.addEventListener('input', () => autoResize(titleEl));
  titleEl.addEventListener('blur', saveTitle);
  titleEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); titleEl.blur(); }
  });
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ── Title save ────────────────────────────────────────────────────────────────
async function saveTitle() {
  const el = document.getElementById('m-title');
  if (!el) return;
  const title = el.value.trim();
  if (!title || title === currentCard.title) return;
  try {
    await api(`/cards/${currentCard.id}`, 'PATCH', { title });
    currentCard.title = title;
  } catch (e) { console.error(e); }
}

// ── Description ───────────────────────────────────────────────────────────────
function editDesc() {
  document.getElementById('desc-display').classList.add('editing');
  document.getElementById('desc-ta').classList.add('active');
  document.getElementById('desc-actions').classList.add('visible');
  document.getElementById('desc-ta').focus();
}

function cancelDesc() {
  document.getElementById('desc-ta').value = currentCard.description || '';
  document.getElementById('desc-display').classList.remove('editing');
  document.getElementById('desc-ta').classList.remove('active');
  document.getElementById('desc-actions').classList.remove('visible');
}

async function saveDesc() {
  const ta = document.getElementById('desc-ta');
  const desc = ta.value;
  try {
    await api(`/cards/${currentCard.id}`, 'PATCH', { description: desc });
    currentCard.description = desc;
    const display = document.getElementById('desc-display');
    display.textContent = desc || 'Add a more detailed description…';
    display.className = `desc-display${!desc ? ' placeholder' : ''}`;
    document.getElementById('desc-ta').classList.remove('active');
    document.getElementById('desc-actions').classList.remove('visible');
  } catch (e) { console.error(e); }
}

// ── Priority & due date ───────────────────────────────────────────────────────
async function updatePriority(priority) {
  try {
    await api(`/cards/${currentCard.id}`, 'PATCH', { priority });
    currentCard.priority = priority;
    const sel = document.getElementById('m-priority');
    sel.className = `sidebar-select priority-${priority}`;
  } catch (e) { console.error(e); }
}

async function updateDueDate(due_date) {
  try {
    await api(`/cards/${currentCard.id}`, 'PATCH', { due_date: due_date || null });
    currentCard.due_date = due_date || null;
  } catch (e) { console.error(e); }
}

// ── Archive / delete card ─────────────────────────────────────────────────────
async function archiveCard() {
  if (!confirm('Archive this card?')) return;
  try {
    await api(`/cards/${currentCard.id}/archive`, 'PATCH', { archived: true });
    closeModal();
  } catch (e) { console.error(e); }
}

async function deleteCard() {
  if (!confirm('Permanently delete this card? This cannot be undone.')) return;
  try {
    await api(`/cards/${currentCard.id}`, 'DELETE');
    closeModal();
  } catch (e) { console.error(e); }
}

// ── Checklists ────────────────────────────────────────────────────────────────
function checklistHTML(cl) {
  const total = cl.items.length;
  const done  = cl.items.filter(i => i.completed).length;
  const pct   = total ? Math.round((done / total) * 100) : 0;
  const partialClass = pct > 0 && pct < 100 ? ' partial' : '';

  return `
    <div class="checklist" id="cl-${cl.id}">
      <div class="checklist-header">
        <span class="checklist-icon">&#9745;</span>
        <span class="checklist-title-text" id="cl-title-${cl.id}"
              onclick="editClTitle(${cl.id})">${esc(cl.title)}</span>
        <input class="checklist-title-input" id="cl-title-inp-${cl.id}"
               value="${esc(cl.title)}"
               onblur="saveClTitle(${cl.id})"
               onkeydown="clTitleKey(event,${cl.id})">
        <button class="btn-del-checklist" onclick="deleteChecklist(${cl.id})">Delete</button>
      </div>
      <div class="progress-wrap">
        <span class="progress-pct" id="cl-pct-${cl.id}">${pct}%</span>
        <div class="progress-bg">
          <div class="progress-fill${partialClass}" id="cl-fill-${cl.id}"
               style="width:${pct}%"></div>
        </div>
      </div>
      <div id="cl-items-${cl.id}">
        ${cl.items.map(itemHTML).join('')}
      </div>
      <div class="add-item-area">
        <div class="add-item-form" id="add-item-form-${cl.id}">
          <textarea class="add-item-textarea" id="add-item-ta-${cl.id}"
            placeholder="Add an item" rows="2"
            onkeydown="addItemKey(event,${cl.id})"></textarea>
          <div class="add-item-actions">
            <button class="btn-primary" onclick="submitAddItem(${cl.id})">Add</button>
            <button class="btn-cancel-text" onclick="hideAddItemForm(${cl.id})">Cancel</button>
          </div>
        </div>
        <button class="add-item-btn" id="add-item-btn-${cl.id}"
                onclick="showAddItemForm(${cl.id})">+ Add an item</button>
      </div>
    </div>`;
}

function itemHTML(item) {
  return `
    <div class="item" id="item-${item.id}">
      <input type="checkbox" ${item.completed ? 'checked' : ''}
             onchange="toggleItem(${item.id}, this.checked)">
      <span class="item-text ${item.completed ? 'done' : ''}" id="item-text-${item.id}"
            onclick="editItem(${item.id})">${esc(item.text)}</span>
      <input class="item-input" id="item-inp-${item.id}"
             value="${esc(item.text)}"
             onblur="saveItem(${item.id})"
             onkeydown="itemKey(event,${item.id})">
      <button class="btn-del-item" onclick="deleteItem(${item.id})">&#x2715;</button>
    </div>`;
}

async function addChecklist() {
  try {
    const cl = await api(`/cards/${currentCard.id}/checklists`, 'POST', { title: 'Checklist' });
    cl.items = [];
    currentCard.checklists.push(cl);
    document.getElementById('checklists-section').insertAdjacentHTML('beforeend', checklistHTML(cl));
  } catch (e) { console.error(e); }
}

function editClTitle(clId) {
  document.getElementById(`cl-title-${clId}`).classList.add('editing');
  const inp = document.getElementById(`cl-title-inp-${clId}`);
  inp.classList.add('active');
  inp.focus(); inp.select();
}

function clTitleKey(e, clId) {
  if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
  if (e.key === 'Escape') {
    const cl = currentCard.checklists.find(c => c.id === clId);
    e.target.value = cl ? cl.title : '';
    e.target.blur();
  }
}

async function saveClTitle(clId) {
  const inp = document.getElementById(`cl-title-inp-${clId}`);
  if (!inp.classList.contains('active')) return;
  const title = inp.value.trim() || 'Checklist';
  try {
    await api(`/checklists/${clId}`, 'PATCH', { title });
    const cl = currentCard.checklists.find(c => c.id === clId);
    if (cl) cl.title = title;
    document.getElementById(`cl-title-${clId}`).textContent = title;
  } catch (e) { console.error(e); }
  document.getElementById(`cl-title-${clId}`).classList.remove('editing');
  inp.classList.remove('active');
}

async function deleteChecklist(clId) {
  try {
    await api(`/checklists/${clId}`, 'DELETE');
    document.getElementById(`cl-${clId}`).remove();
    currentCard.checklists = currentCard.checklists.filter(c => c.id !== clId);
  } catch (e) { console.error(e); }
}

// ── Checklist items ───────────────────────────────────────────────────────────
function showAddItemForm(clId) {
  document.getElementById(`add-item-form-${clId}`).classList.add('active');
  document.getElementById(`add-item-btn-${clId}`).style.display = 'none';
  document.getElementById(`add-item-ta-${clId}`).focus();
}

function hideAddItemForm(clId) {
  document.getElementById(`add-item-form-${clId}`).classList.remove('active');
  document.getElementById(`add-item-btn-${clId}`).style.display = '';
  document.getElementById(`add-item-ta-${clId}`).value = '';
}

function addItemKey(e, clId) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitAddItem(clId); }
  if (e.key === 'Escape') hideAddItemForm(clId);
}

async function submitAddItem(clId) {
  const ta = document.getElementById(`add-item-ta-${clId}`);
  const text = ta.value.trim();
  if (!text) return;
  try {
    const item = await api(`/checklists/${clId}/items`, 'POST', { text });
    document.getElementById(`cl-items-${clId}`).insertAdjacentHTML('beforeend', itemHTML(item));
    ta.value = '';
    ta.focus();
    recalcProgress(clId);
  } catch (e) { console.error(e); }
}

async function toggleItem(itemId, completed) {
  try {
    await api(`/checklist-items/${itemId}`, 'PATCH', { completed });
    const textEl = document.getElementById(`item-text-${itemId}`);
    if (completed) textEl.classList.add('done'); else textEl.classList.remove('done');
    const clEl = document.getElementById(`item-${itemId}`).closest('.checklist');
    if (clEl) recalcProgress(parseInt(clEl.id.replace('cl-', '')));
  } catch (e) { console.error(e); }
}

function editItem(itemId) {
  document.getElementById(`item-text-${itemId}`).classList.add('editing');
  const inp = document.getElementById(`item-inp-${itemId}`);
  inp.classList.add('active');
  inp.focus(); inp.select();
}

function itemKey(e, itemId) {
  if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
  if (e.key === 'Escape') {
    document.getElementById(`item-text-${itemId}`).classList.remove('editing');
    e.target.classList.remove('active');
  }
}

async function saveItem(itemId) {
  const inp = document.getElementById(`item-inp-${itemId}`);
  if (!inp.classList.contains('active')) return;
  inp.classList.remove('active');
  const text = inp.value.trim();
  const textEl = document.getElementById(`item-text-${itemId}`);
  textEl.classList.remove('editing');
  if (!text) return;
  try {
    await api(`/checklist-items/${itemId}`, 'PATCH', { text });
    textEl.textContent = text;
    inp.value = text;
  } catch (e) { console.error(e); }
}

async function deleteItem(itemId) {
  try {
    const el = document.getElementById(`item-${itemId}`);
    const clEl = el.closest('.checklist');
    await api(`/checklist-items/${itemId}`, 'DELETE');
    el.remove();
    if (clEl) recalcProgress(parseInt(clEl.id.replace('cl-', '')));
  } catch (e) { console.error(e); }
}

function recalcProgress(clId) {
  const cl = document.getElementById(`cl-${clId}`);
  if (!cl) return;
  const total = cl.querySelectorAll('.item input[type="checkbox"]').length;
  const done  = cl.querySelectorAll('.item input[type="checkbox"]:checked').length;
  const pct   = total ? Math.round((done / total) * 100) : 0;
  const fill  = document.getElementById(`cl-fill-${clId}`);
  const pctEl = document.getElementById(`cl-pct-${clId}`);
  if (fill) {
    fill.style.width = `${pct}%`;
    fill.className = `progress-fill${pct > 0 && pct < 100 ? ' partial' : ''}`;
  }
  if (pctEl) pctEl.textContent = `${pct}%`;
}

// ── Comments ──────────────────────────────────────────────────────────────────

async function loadComments() {
  if (!currentCard) return;
  try {
    const comments = await api(`/cards/${currentCard.id}/comments`);
    renderComments(comments);
    const hasPending = comments.some(c => c.has_at_claude && !c.claude_handled);
    if (hasPending && !commentPollTimer) startCommentPoll();
    else if (!hasPending && commentPollTimer) stopCommentPoll();
  } catch (e) { console.error(e); }
}

function renderComments(comments) {
  const list = document.getElementById('comments-list');
  if (!list) return;
  if (!comments.length) {
    list.innerHTML = '<div class="no-comments">No activity yet.</div>';
    return;
  }
  // Group replies by parent
  const replyMap = {};
  comments.filter(c => c.reply_to_id).forEach(r => {
    (replyMap[r.reply_to_id] = replyMap[r.reply_to_id] || []).push(r);
  });
  const topLevel = comments.filter(c => !c.reply_to_id);
  list.innerHTML = topLevel.map(c =>
    commentHTML(c) + (replyMap[c.id] || []).map(r => commentHTML(r, true)).join('')
  ).join('');
}

function commentHTML(c, isReply = false) {
  const time = new Date(c.created_at.endsWith('Z') ? c.created_at : c.created_at + 'Z')
    .toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const isClaude = c.author === 'claude';
  const avatar = isClaude ? '🤖' : '👤';
  const authorLabel = isClaude ? 'Claude' : esc(c.author);
  const pending = c.has_at_claude && !c.claude_handled
    ? '<span class="comment-pending">⏳ waiting for Claude…</span>' : '';
  const actions = !isClaude ? `
    <button class="comment-action-btn" onclick="editComment(${c.id})">Edit</button>
    <button class="comment-action-btn" onclick="deleteComment(${c.id})">Delete</button>` : '';

  return `
    <div class="comment${isReply ? ' comment-reply' : ''}${isClaude ? ' comment-claude' : ''}" id="comment-${c.id}">
      <div class="comment-header">
        <span class="comment-avatar">${avatar}</span>
        <span class="comment-author">${authorLabel}</span>
        <span class="comment-time">${time}</span>
        <div class="comment-actions">${actions}</div>
      </div>
      <div class="comment-body" id="comment-body-${c.id}">${renderMarkdown(c.text)}</div>
      <div class="comment-edit-form" id="comment-edit-${c.id}">
        <textarea class="comment-edit-ta" id="comment-edit-ta-${c.id}">${esc(c.text)}</textarea>
        <div class="comment-edit-actions">
          <button class="btn-primary" onclick="saveComment(${c.id})">Save</button>
          <button class="btn-cancel-text" onclick="cancelEditComment(${c.id})">Cancel</button>
        </div>
      </div>
      ${pending}
    </div>`;
}

function renderMarkdown(text) {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function commentKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitComment(); }
}

async function submitComment() {
  const ta = document.getElementById('comment-ta');
  const text = ta.value.trim();
  if (!text || !currentCard) return;
  try {
    await api(`/cards/${currentCard.id}/comments`, 'POST', { text });
    ta.value = '';
    await loadComments();
  } catch (e) { console.error(e); }
}

function startCommentPoll() {
  commentPollTimer = setInterval(loadComments, 2000);
}

function stopCommentPoll() {
  if (commentPollTimer) { clearInterval(commentPollTimer); commentPollTimer = null; }
}

function editComment(id) {
  document.getElementById(`comment-body-${id}`).classList.add('hidden');
  document.getElementById(`comment-edit-${id}`).classList.add('active');
  document.getElementById(`comment-edit-ta-${id}`).focus();
}

function cancelEditComment(id) {
  document.getElementById(`comment-body-${id}`).classList.remove('hidden');
  document.getElementById(`comment-edit-${id}`).classList.remove('active');
}

async function saveComment(id) {
  const ta = document.getElementById(`comment-edit-ta-${id}`);
  const text = ta.value.trim();
  if (!text) return;
  try {
    await api(`/comments/${id}`, 'PATCH', { text });
    await loadComments();
  } catch (e) { console.error(e); }
}

async function deleteComment(id) {
  if (!confirm('Delete this comment?')) return;
  try {
    await api(`/comments/${id}`, 'DELETE');
    document.getElementById(`comment-${id}`).remove();
  } catch (e) { console.error(e); }
}

// ── Archive modal ─────────────────────────────────────────────────────────────
async function openArchive() {
  try {
    const cards = await api('/archive');
    const content = document.getElementById('archive-content');
    if (!cards.length) {
      content.innerHTML = '<p style="text-align:center;color:#5e6c84;padding:32px">No archived cards</p>';
    } else {
      content.innerHTML = cards.map(card => `
        <div class="archive-card" id="archived-${card.id}">
          <div class="archive-card-info">
            <div class="archive-card-title">${esc(card.title)}</div>
            <div class="archive-card-meta">Column: ${esc(card.column_name)}</div>
          </div>
          <div class="archive-card-actions">
            <button class="btn-sm btn-restore" onclick="restoreCard(${card.id})">Restore</button>
            <button class="btn-sm btn-danger"  onclick="permDelete(${card.id})">Delete</button>
          </div>
        </div>`).join('');
    }
    document.getElementById('archive-overlay').classList.remove('hidden');
  } catch (e) { console.error(e); }
}

function closeArchive() {
  document.getElementById('archive-overlay').classList.add('hidden');
}

async function restoreCard(cardId) {
  try {
    await api(`/cards/${cardId}/archive`, 'PATCH', { archived: false });
    document.getElementById(`archived-${cardId}`).remove();
    await loadBoard();
  } catch (e) { console.error(e); }
}

async function permDelete(cardId) {
  if (!confirm('Permanently delete this card?')) return;
  try {
    await api(`/cards/${cardId}`, 'DELETE');
    document.getElementById(`archived-${cardId}`).remove();
  } catch (e) { console.error(e); }
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (!document.getElementById('modal-overlay').classList.contains('hidden')) closeModal();
    else if (!document.getElementById('archive-overlay').classList.contains('hidden')) closeArchive();
  }
});

// ── Boot ──────────────────────────────────────────────────────────────────────
loadBoard();
