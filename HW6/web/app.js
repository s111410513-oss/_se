const taskForm = document.querySelector('#task-form');
const taskInput = document.querySelector('#task-input');
const taskList = document.querySelector('#task-list');
const emptyState = document.querySelector('#empty-state');
const formMessage = document.querySelector('#form-message');
const filterButtons = document.querySelectorAll('.filter-button');
let tasks = [];
let currentFilter = 'all';

const today = new Date();
document.querySelector('#today-date').textContent = new Intl.DateTimeFormat('zh-TW', {
  year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
}).format(today);

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = '操作失敗，請稍後再試。';
    try { message = (await response.json()).error || message; } catch (_) {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function loadTasks() {
  try {
    tasks = await request('/api/tasks');
    renderTasks();
  } catch (error) {
    formMessage.textContent = '無法連線到伺服器，請重新整理頁面。';
  }
}

function renderTasks() {
  const visibleTasks = tasks.filter(task => {
    if (currentFilter === 'active') return !task.completed;
    if (currentFilter === 'completed') return task.completed;
    return true;
  });
  taskList.replaceChildren();
  visibleTasks.forEach(task => {
    const item = document.createElement('li');
    item.className = `task-item${task.completed ? ' done' : ''}`;
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'task-check';
    checkbox.checked = task.completed;
    checkbox.setAttribute('aria-label', `完成：${task.title}`);
    checkbox.addEventListener('change', () => toggleTask(task.id));
    const title = document.createElement('span');
    title.className = 'task-title';
    title.textContent = task.title;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'delete-button';
    remove.textContent = '×';
    remove.setAttribute('aria-label', `刪除：${task.title}`);
    remove.addEventListener('click', () => deleteTask(task.id));
    item.append(checkbox, title, remove);
    taskList.append(item);
  });
  const completed = tasks.filter(task => task.completed).length;
  const percentage = tasks.length ? Math.round(completed / tasks.length * 100) : 0;
  document.querySelector('#progress-number').textContent = `${percentage}%`;
  document.querySelector('.progress-ring').style.background = `conic-gradient(#89a987 ${percentage * 3.6}deg, #edf1e9 0deg)`;
  document.querySelector('#all-count').textContent = tasks.length;
  document.querySelector('#task-total').textContent = `${tasks.length} 個項目`;
  emptyState.hidden = visibleTasks.length !== 0;
}

taskForm.addEventListener('submit', async event => {
  event.preventDefault();
  const title = taskInput.value.trim();
  if (!title) {
    formMessage.textContent = '請先輸入待辦事項。';
    taskInput.focus();
    return;
  }
  try {
    const created = await request('/api/tasks', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    tasks.push(created);
    taskInput.value = '';
    formMessage.textContent = '';
    currentFilter = 'all';
    updateFilterButtons();
    renderTasks();
    taskInput.focus();
  } catch (error) {
    formMessage.textContent = error.message;
  }
});

async function toggleTask(id) {
  try {
    const updated = await request(`/api/tasks/${id}/toggle`, { method: 'POST' });
    tasks = tasks.map(task => task.id === id ? updated : task);
    renderTasks();
  } catch (error) { formMessage.textContent = error.message; }
}

async function deleteTask(id) {
  try {
    await request(`/api/tasks/${id}`, { method: 'DELETE' });
    tasks = tasks.filter(task => task.id !== id);
    renderTasks();
  } catch (error) { formMessage.textContent = error.message; }
}

function updateFilterButtons() {
  filterButtons.forEach(button => button.classList.toggle('active', button.dataset.filter === currentFilter));
}
filterButtons.forEach(button => button.addEventListener('click', () => {
  currentFilter = button.dataset.filter;
  updateFilterButtons();
  renderTasks();
}));

loadTasks();
