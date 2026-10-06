/* ===== 主應用程式：各模組渲染與互動 ===== */
window.App = (function () {
  'use strict';

  var user = null;          // 目前登入使用者
  var currentView = 'home';
  var newsKw = '', newsCat = 'all';
  var coursesKw = '', coursesDept = 'all', courseTab = 'list';
  var affairTab = 'profile';
  var accTab = 'users', userKw = '';
  var SEM = (function () { var p = DB.getDb().portal; return (p && p.semesterKey) || '115-1'; })();
  var DAY = ['', '一', '二', '三', '四', '五', '六', '日'];
  var PERIOD_TIME = { 1: '08:10', 2: '09:10', 3: '10:10', 4: '11:10', 5: '13:10', 6: '14:10', 7: '15:10', 8: '16:10' };
  var DEPT_COLOR = {
    '資訊工程學系': '#1a5fb4', '通識教育中心': '#2e8b57', '體育室': '#9a6b00',
    '企業管理學系': '#8e44ad', '觀光管理學系': '#c0392b', '學務處': '#2471a3'
  };

  /* ---------- 工具 ---------- */
  function h(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function $(id) { return document.getElementById(id); }
  var modalRoot;
  function openModal(html) { if (modalRoot) modalRoot.innerHTML = '<div class="modal-mask"><div class="modal">' + html + '</div></div>'; }
  function closeModal() { if (modalRoot) modalRoot.innerHTML = ''; }
  function toast(msg, ok) {
    var d = document.createElement('div');
    d.style.cssText = 'position:fixed;top:78px;right:22px;z-index:999;background:' + (ok === false ? '#c0392b' : '#2e8b57') + ';color:#fff;padding:11px 18px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.25);font-size:14px';
    d.textContent = msg;
    document.body.appendChild(d);
    setTimeout(function () { d.style.transition = 'opacity .4s'; d.style.opacity = '0'; setTimeout(function () { d.remove(); }, 400); }, 2200);
  }
  function byId(id) { return DB.userById(id); }
  function courseByCode(code) { return DB.courseByCode(code); }
  function enrolledStudentIds(code) {
    var db = DB.getDb(), out = [];
    db.enrollments.forEach(function (e) { if (e.courseCode === code && e.semester === SEM) out.push(e.studentId); });
    return out;
  }
  function isEnrolled(studentId, code) {
    var db = DB.getDb();
    return db.enrollments.some(function (e) { return e.courseCode === code && e.studentId === studentId && e.semester === SEM; });
  }
  function scheduleText(course) {
    if (!course.schedule || !course.schedule.length) return '時間另訂';
    return course.schedule.map(function (s) {
      return DAY[s.day] + ' ' + (s.start === s.end ? s.start : s.start + '-' + s.end) + ' 節';
    }).join('、');
  }
  function gradePoints(rank) {
    var m = { 'A+': 4.3, 'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7, 'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D': 1.0, 'F': 0 };
    return m[rank] != null ? m[rank] : 0;
  }
  function avatarText(name) { return name && name.length ? name.charAt(0) : '?'; }
  function enrollCredits(studentId) {
    var db = DB.getDb();
    return db.enrollments.filter(function (e) { return e.studentId === studentId && e.semester === SEM; })
      .reduce(function (s, e) { var c = courseByCode(e.courseCode); return s + (c ? c.credits : 0); }, 0);
  }
  function deptOptions(sel) {
    var db = DB.getDb(), seen = {}, out = '';
    db.courses.forEach(function (c) { if (!seen[c.dept]) { seen[c.dept] = 1; out += '<option value="' + h(c.dept) + '"' + (c.dept === sel ? ' selected' : '') + '>' + h(c.dept) + '</option>'; } });
    return out;
  }
  function hasConflictWith(studentId, code) {
    var db = DB.getDb();
    var target = courseByCode(code);
    if (!target || !target.schedule) return false;
    var mine = db.enrollments.filter(function (e) { return e.studentId === studentId && e.semester === SEM; });
    for (var i = 0; i < mine.length; i++) {
      if (mine[i].courseCode === code) continue;
      var c = courseByCode(mine[i].courseCode);
      if (!c || !c.schedule) continue;
      for (var a = 0; a < target.schedule.length; a++) {
        for (var b = 0; b < c.schedule.length; b++) {
          if (target.schedule[a].day === c.schedule[b].day &&
            target.schedule[a].start <= c.schedule[b].end && c.schedule[b].start <= target.schedule[a].end) return true;
        }
      }
    }
    return false;
  }

  /* ---------- 側邊欄 ---------- */
  function buildSidebar() {
    var groups = [
      { title: '總覽', items: [{ key: 'home', ico: '🏠', label: '個人首頁' }] },
      { title: '校園資訊', items: [{ key: 'news', ico: '📢', label: '校務公告' }] },
      { title: '課務', items: [
        { key: 'courses', ico: '📚', label: '選課系統' },
        { key: 'schedule', ico: '🗓', label: '課表管理' },
        { key: 'grades', ico: '📈', label: '成績查詢' }
      ] },
      { title: '行政', items: [{ key: 'affairs', ico: '🏛', label: '教務 / 學務行政' }] },
      { title: '個人', items: [{ key: 'account', ico: '👤', label: '帳號管理' }] }
    ];
    $('sidebar').innerHTML = groups.map(function (g) {
      return '<div class="nav-group"><div class="nav-title">' + g.title + '</div>' +
        g.items.map(function (it) {
          return '<div class="nav-item' + (currentView === it.key ? ' active' : '') + '" data-view="' + it.key + '">' +
            '<span class="ico">' + it.ico + '</span>' + h(it.label) + '</div>';
        }).join('') + '</div>';
    }).join('') +
      '<div class="footer">NQU 校務資訊系統<br>純前端示範專案 v1.0</div>';
    var items = $('sidebar').querySelectorAll('.nav-item');
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener('click', (function (v) { return function () { showView(v); }; })(items[i].dataset.view));
    }
  }

  /* ---------- 頁面切換 ---------- */
  var VIEWS = ['home', 'news', 'courses', 'schedule', 'grades', 'affairs', 'account'];
  function showView(name) {
    currentView = name;
    VIEWS.forEach(function (v) { $('view-' + v).classList.add('hidden'); });
    $('view-' + name).classList.remove('hidden');
    buildSidebar();
    renderCurrent();
    window.scrollTo(0, 0);
  }
  var RENDERERS = { home: renderHome, news: renderNews, courses: renderCourses, schedule: renderSchedule, grades: renderGrades, affairs: renderAffairs, account: renderAccount };
  function renderCurrent() { var fn = RENDERERS[currentView]; if (fn) fn(); }

  /* ---------- 首頁 ---------- */
  function renderHome() {
    var db = DB.getDb(), html = '';
    if (user.role === 'student') {
      var credits = enrollCredits(user.id);
      var enrolled = db.enrollments.filter(function (e) { return e.studentId === user.id && e.semester === SEM; });
      var myGrades = db.grades.filter(function (g) { return g.studentId === user.id; });
      var totalC = myGrades.reduce(function (s, g) { return s + g.credits; }, 0);
      var gpa = totalC ? (myGrades.reduce(function (s, g) { return s + g.credits * gradePoints(g.rank); }, 0) / totalC) : 0;
      html =
        '<div class="hero-card"><h2>親愛的 ' + h(user.name) + '，歡迎回來</h2>' +
        '<p>' + h(user.dept) + ' · ' + h(user.grade) + ' · 學號 ' + h(user.studentId) + '</p>' +
        '<div class="welcome">📅 今天是 ' + new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) + '</div></div>' +
        '<div class="stat-grid">' +
        '<div class="stat"><div class="num">' + credits + '</div><div class="lbl">本學期已選學分（' + db.portal.maxCredits + ' 上限）</div></div>' +
        '<div class="stat"><div class="num">' + enrolled.length + '</div><div class="lbl">本學期選課數</div></div>' +
        '<div class="stat"><div class="num">' + totalC + '</div><div class="lbl">累計修習學分</div></div>' +
        '<div class="stat"><div class="num">' + gpa.toFixed(2) + '</div><div class="lbl">累計 GPA</div></div>' +
        '</div>';
    } else if (user.role === 'teacher') {
      var myCourses = db.courses.filter(function (c) { return c.teacherId === user.id; });
      var roster = myCourses.reduce(function (s, c) { return s + enrolledStudentIds(c.code).length; }, 0);
      var pend = db.leaves.filter(function (l) { return l.status === '待審核'; }).length;
      html =
        '<div class="hero-card"><h2>' + h(user.name) + ' 教師，您好</h2><p>' + h(user.dept) + ' · ' + h(user.title) + '</p></div>' +
        '<div class="stat-grid">' +
        '<div class="stat"><div class="num">' + myCourses.length + '</div><div class="lbl">本學期授課數</div></div>' +
        '<div class="stat"><div class="num">' + roster + '</div><div class="lbl">授課學生人次</div></div>' +
        '<div class="stat"><div class="num">' + pend + '</div><div class="lbl">待審核請假</div></div>' +
        '<div class="stat"><div class="num">' + db.rewards.length + '</div><div class="lbl">全校獎懲筆數</div></div>' +
        '</div>';
    } else {
      var selCnt = db.enrollments.filter(function (e) { return e.semester === SEM; }).length;
      var full = db.courses.filter(function (c) { return enrolledStudentIds(c.code).length >= c.capacity; }).length;
      html =
        '<div class="hero-card"><h2>' + h(user.name) + ' 管理員，您好</h2><p>教務系統管理作業中台 · ' + h(user.dept) + '</p></div>' +
        '<div class="stat-grid">' +
        '<div class="stat"><div class="num">' + db.courses.length + '</div><div class="lbl">課程總數</div></div>' +
        '<div class="stat"><div class="num">' + selCnt + '</div><div class="lbl">本學期選課人次</div></div>' +
        '<div class="stat"><div class="num">' + full + '</div><div class="lbl">額滿課程</div></div>' +
        '<div class="stat"><div class="num">' + db.users.length + '</div><div class="lbl">系統帳號數</div></div>' +
        '</div>';
    }
    html += '<div class="card"><h3>📢 最新公告</h3>' + newsListHTML(3, true) + '</div>';
    $('view-home').innerHTML = html;
  }

  /* ---------- 校務公告 ---------- */
  function newsListHTML(limit, clickable) {
    var db = DB.getDb();
    var list = db.announcements.slice().sort(function (a, b) { return b.important - a.important || b.date.localeCompare(a.date); });
    if (limit) list = list.slice(0, limit);
    if (!list.length) return '<div class="empty-tip">目前尚無公告</div>';
    return list.map(function (a) {
      var catColor = { '教務': 'blue', '學務': 'green', '總務': 'gold', '圖書館': 'gray' }[a.category] || 'gray';
      return '<div class="news-item" ' + (clickable ? 'onclick="App.openNews(\'' + a.id + '\')"' : '') + '>' +
        '<div class="title">' + (a.important ? '<span class="badge red">置頂</span>' : '') +
        '<span class="badge ' + catColor + '">' + h(a.category) + '</span>' + h(a.title) + '</div>' +
        '<div class="meta"><span>發布單位：' + h(a.author) + '</span><span>日期：' + h(a.date) + '</span></div>' +
        '</div>';
    }).join('');
  }
  function renderNews() {
    var db = DB.getDb();
    var filterBar = '<div class="toolbar">' +
      '<input type="text" placeholder="搜尋公告標題…" value="' + h(newsKw) + '" oninput="App.setNewsKw(this.value)" style="width:240px">' +
      '<select onchange="App.setNewsCat(this.value)"><option value="all">全部分類</option>' +
      ['教務', '學務', '總務', '圖書館'].map(function (c) { return '<option value="' + c + '"' + (newsCat === c ? ' selected' : '') + '>' + c + '</option>'; }).join('') +
      '</select>' +
      (user.role === 'admin' ? '<div class="spacer" style="flex:1"></div><button class="btn primary" onclick="App.openNewsForm()">＋ 發布公告</button>' : '') +
      '</div>';
    var list = db.announcements.slice().filter(function (a) {
      var okK = !newsKw || a.title.indexOf(newsKw) !== -1 || a.content.indexOf(newsKw) !== -1;
      var okC = newsCat === 'all' || a.category === newsCat;
      return okK && okC;
    }).sort(function (a, b) { return b.important - a.important || b.date.localeCompare(a.date); });
    var table = list.map(function (a) {
      var catColor = { '教務': 'blue', '學務': 'green', '總務': 'gold', '圖書館': 'gray' }[a.category] || 'gray';
      var adminBtns = user.role === 'admin'
        ? '<button class="btn sm" onclick="App.openNewsForm(\'' + a.id + '\')">編輯</button> ' +
          '<button class="btn sm danger" onclick="App.deleteNews(\'' + a.id + '\')">刪除</button>'
        : '';
      return '<tr onclick="App.openNews(\'' + a.id + '\')" style="cursor:pointer">' +
        '<td>' + (a.important ? '<span class="badge red">置頂</span> ' : '') + h(a.title) + '</td>' +
        '<td class="num-c"><span class="badge ' + catColor + '">' + h(a.category) + '</span></td>' +
        '<td>' + h(a.author) + '</td><td>' + h(a.date) + '</td>' +
        '<td>' + adminBtns + '</td></tr>';
    }).join('') || '<tr><td colspan="5" class="empty-tip">沒有符合條件的公告</td></tr>';
    $('view-news').innerHTML =
      '<div class="page-head"><h2>校務公告</h2><div class="desc">各單位最新消息與重要行政公告</div></div>' +
      filterBar +
      '<div class="card" style="padding:6px"><table class="tbl"><thead><tr><th>標題</th><th style="width:90px">分類</th><th style="width:130px">發布單位</th><th style="width:110px">日期</th><th style="width:150px">操作</th></tr></thead><tbody>' + table + '</tbody></table></div>';
  }
  function openNews(id) {
    var db = DB.getDb(), a = null;
    db.announcements.forEach(function (x) { if (x.id === id) a = x; });
    if (!a) return;
    openModal(
      '<div class="modal-head"><h3>' + (a.important ? '<span class="badge red">置頂</span> ' : '') + h(a.category) + ' 公告</h3><button class="close" onclick="App.closeModal()">×</button></div>' +
      '<div class="modal-body"><h3 style="font-size:18px;margin-bottom:8px">' + h(a.title) + '</h3>' +
      '<div style="color:#6b7a8c;font-size:13px;margin-bottom:14px">發布單位：' + h(a.author) + ' ｜ 公告日期：' + h(a.date) + '</div>' +
      '<div style="line-height:1.9;white-space:pre-wrap">' + h(a.content) + '</div></div>'
    );
  }
  function openNewsForm(id) {
    var db = DB.getDb(), a = null, isEdit = false;
    if (id) { isEdit = true; db.announcements.forEach(function (x) { if (x.id === id) a = x; }); }
    var category = a ? a.category : '教務', important = a ? a.important : false;
    openModal(
      '<div class="modal-head"><h3>' + (isEdit ? '編輯' : '發布') + '公告</h3><button class="close" onclick="App.closeModal()">×</button></div>' +
      '<div class="modal-body">' +
      '<div class="form-row"><label>分類</label><select id="nt_category">' + ['教務', '學務', '總務', '圖書館'].map(function (c) { return '<option' + (category === c ? ' selected' : '') + '>' + c + '</option>'; }).join('') + '</select></div>' +
      '<div class="form-row"><label>標題</label><input id="nt_title" value="' + h(a ? a.title : '') + '"></div>' +
      '<div class="form-row"><label>置頂</label><select id="nt_imp"><option value="0"' + (!important ? ' selected' : '') + '>否</option><option value="1"' + (important ? ' selected' : '') + '>是</option></select></div>' +
      '<div class="form-row"><label>內容</label><textarea id="nt_content" rows="5">' + h(a ? a.content : '') + '</textarea></div>' +
      '<div class="form-actions"><button class="btn" onclick="App.closeModal()">取消</button>' +
      '<button class="btn primary" onclick="App.saveNews(\'' + (isEdit ? id : '') + '\')">儲存</button></div>' +
      '</div>'
    );
  }
  function saveNews(id) {
    var db = DB.getDb();
    var title = $('nt_title').value.trim(), content = $('nt_content').value.trim(), cat = $('nt_category').value;
    if (!title || !content) { toast('請填寫標題與內容', false); return; }
    var today = new Date().toISOString().slice(0, 10);
    if (id) {
      db.announcements.forEach(function (a) { if (a.id === id) { a.title = title; a.content = content; a.category = cat; a.important = $('nt_imp').value === '1'; } });
    } else {
      db.announcements.unshift({ id: 'a' + Date.now(), title: title, content: content, category: cat, important: $('nt_imp').value === '1', author: user.dept, date: today });
    }
    DB.save(db); closeModal(); renderNews(); toast('公告已儲存');
  }
  function deleteNews(id) {
    var db = DB.getDb();
    if (!confirm('確定要刪除這則公告嗎？')) return;
    db.announcements = db.announcements.filter(function (a) { return a.id !== id; });
    DB.save(db); renderNews(); toast('公告已刪除', false);
  }
  function setNewsKw(v) { newsKw = v; renderNews(); }
  function setNewsCat(v) { newsCat = v; renderNews(); }

  /* ---------- 選課系統 ---------- */
  function renderCourses() {
    var db = DB.getDb(), html = '', body = '';
    if (user.role === 'student') {
      var credits = enrollCredits(user.id);
      var enrolled = db.enrollments.filter(function (e) { return e.studentId === user.id && e.semester === SEM; });
      var max = db.portal.maxCredits;
      html += '<div class="page-head"><h2>選課系統</h2><div class="desc">加退選截止日：' + h(db.portal.enrollDeadline) + ' ｜ 最低 ' + db.portal.minCredits + ' 學分 / 上限 ' + max + ' 學分</div></div>';
      html += '<div class="stat-grid" style="margin-bottom:18px">' +
        '<div class="stat"><div class="num">' + credits + '</div><div class="lbl">已選學分（上限 ' + max + '）</div></div>' +
        '<div class="stat"><div class="num">' + enrolled.length + '</div><div class="lbl">已選課程數</div></div>' +
        '<div class="stat"><div class="num">' + (max - credits) + '</div><div class="lbl">可選學分餘額</div></div>' +
        '</div>';

      html += '<div class="tab-bar"><div class="tab' + (courseTab === 'list' ? ' active' : '') + '" onclick="App.setCourseTab(\'list\')">全校課程</div>' +
        '<div class="tab' + (courseTab === 'mine' ? ' active' : '') + '" onclick="App.setCourseTab(\'mine\')">我的已選課程 (' + enrolled.length + ')</div></div>';

      if (courseTab === 'list') {
        var filtered = db.courses.filter(function (c) {
          var okK = !coursesKw || c.name.indexOf(coursesKw) !== -1 || c.code.indexOf(coursesKw.toUpperCase().trim()) !== -1;
          var okD = coursesDept === 'all' || c.dept === coursesDept;
          return okK && okD;
        });
        body = '<div class="toolbar">' +
          '<input type="text" placeholder="輸入課程名稱或代碼搜尋" style="width:260px" value="' + h(coursesKw) + '" oninput="App.setCoursesKw(this.value)">' +
          '<select onchange="App.setCoursesDept(this.value)"><option value="all">全部系所</option>' + deptOptions(coursesDept) + '</select>' +
          '</div>';
        body += '<table class="tbl"><thead><tr><th>開課代碼</th><th>課程名稱</th><th>學分</th><th>系所</th><th>授課教師</th><th>上課時間</th><th>教室</th><th>名額</th><th>動作</th></tr></thead><tbody>';
        body += filtered.map(function (c) {
          var takers = enrolledStudentIds(c.code).length;
          var full = takers >= c.capacity;
          var isMine = isEnrolled(user.id, c.code);
          var conflict = hasConflictWith(user.id, c.code);
          var btn;
          if (isMine) btn = '<button class="btn sm danger" onclick="App.dropCourse(\'' + c.code + '\')">退選</button>';
          else if (full) btn = '<button class="btn sm" disabled>已額滿</button>';
          else btn = '<button class="btn sm primary" onclick="App.enrollCourse(\'' + c.code + '\')">選課</button>';
          return '<tr>' +
            '<td>' + h(c.code) + '</td><td><b>' + h(c.name) + '</b>' + (c.note ? '<div style="font-size:11px;color:#6b7a8c">' + h(c.note) + '</div>' : '') + '</td>' +
            '<td class="num-c">' + c.credits + '</td><td>' + h(c.dept) + '</td><td>' + h(byId(c.teacherId) ? byId(c.teacherId).name : '-') + '</td>' +
            '<td>' + scheduleText(c) + '</td><td>' + h(c.room) + '</td>' +
            '<td class="num-c">' + takers + '/' + c.capacity + (full ? '<div><span class="badge red">滿</span></div>' : '') + '</td>' +
            '<td>' + btn + (conflict ? ' <span class="badge gold">時間衝突</span>' : '') + '</td></tr>';
        }).join('') || '<tr><td colspan="9" class="empty-tip">查無符合條件的課程</td></tr>';
        body += '</tbody></table>';
      } else {
        if (!enrolled.length) {
          body = '<div class="empty-tip">你尚未選修任何課程，請到「全校課程」分頁進行加選。</div>';
        } else {
          body = '<table class="tbl"><thead><tr><th>開課代碼</th><th>課程名稱</th><th>學分</th><th>授課教師</th><th>上課時間</th><th>教室</th><th>動作</th></tr></thead><tbody>' +
            enrolled.map(function (e) {
              var c = courseByCode(e.courseCode);
              return '<tr><td>' + h(c.code) + '</td><td><b>' + h(c.name) + '</b></td><td class="num-c">' + c.credits + '</td>' +
                '<td>' + h(byId(c.teacherId) ? byId(c.teacherId).name : '-') + '</td><td>' + scheduleText(c) + '</td><td>' + h(c.room) + '</td>' +
                '<td><button class="btn sm danger" onclick="App.dropCourse(\'' + c.code + '\')">退選</button></td></tr>';
            }).join('') + '</tbody></table>' +
            '<div class="credit-sum" style="margin-top:10px">本學期合計：' + credits + ' 學分</div>';
        }
      }
    } else if (user.role === 'teacher') {
      var mine = db.courses.filter(function (c) { return c.teacherId === user.id; });
      var totalRoster = mine.reduce(function (s, c) { return s + enrolledStudentIds(c.code).length; }, 0);
      html += '<div class="page-head"><h2>選課系統</h2><div class="desc">本學期授課與選課名單管理</div></div>';
      html += '<div class="stat-grid" style="margin-bottom:18px">' +
        '<div class="stat"><div class="num">' + mine.length + '</div><div class="lbl">授課課程數</div></div>' +
        '<div class="stat"><div class="num">' + totalRoster + '</div><div class="lbl">選課學生人次</div></div>' +
        '</div>';
      body = '<table class="tbl"><thead><tr><th>開課代碼</th><th>課程名稱</th><th>學分</th><th>上課時間</th><th>教室</th><th>選課人數</th><th>動作</th></tr></thead><tbody>';
      body += mine.map(function (c) {
        var n = enrolledStudentIds(c.code).length;
        return '<tr><td>' + h(c.code) + '</td><td><b>' + h(c.name) + '</b></td><td class="num-c">' + c.credits + '</td>' +
          '<td>' + scheduleText(c) + '</td><td>' + h(c.room) + '</td><td class="num-c">' + n + '/' + c.capacity + '</td>' +
          '<td><button class="btn sm" onclick="App.courseRoster(\'' + c.code + '\')">檢視名單</button></td></tr>';
      }).join('') || '<tr><td colspan="7" class="empty-tip">本學期尚無授課課程</td></tr>';
      body += '</tbody></table>';
    } else {
      var totalSel = db.enrollments.filter(function (e) { return e.semester === SEM; }).length;
      var fullCount = db.courses.filter(function (c) { return enrolledStudentIds(c.code).length >= c.capacity; }).length;
      html += '<div class="page-head"><h2>選課系統</h2><div class="desc">全校課程與選課總覽</div></div>';
      html += '<div class="stat-grid" style="margin-bottom:18px">' +
        '<div class="stat"><div class="num">' + db.courses.length + '</div><div class="lbl">課程總數</div></div>' +
        '<div class="stat"><div class="num">' + totalSel + '</div><div class="lbl">本學期選課人次</div></div>' +
        '<div class="stat"><div class="num">' + fullCount + '</div><div class="lbl">額滿課程</div></div>' +
        '</div>';
      var filterBar = '<div class="toolbar"><input type="text" placeholder="搜尋課程…" style="width:220px" value="' + h(coursesKw) + '" oninput="App.setCoursesKw(this.value)">' +
        '<select onchange="App.setCoursesDept(this.value)"><option value="all">全部系所</option>' + deptOptions(coursesDept) + '</select>' +
        '<div class="spacer" style="flex:1"></div><button class="btn primary" onclick="App.openCourseForm()">＋ 新增課程</button></div>';
      body = filterBar + '<table class="tbl"><thead><tr><th>開課代碼</th><th>課程名稱</th><th>學分</th><th>系所</th><th>授課教師</th><th>上課時間</th><th>教室</th><th>選課人數</th><th>狀態</th></tr></thead><tbody>' +
        db.courses.filter(function (c) {
          return (coursesDept === 'all' || c.dept === coursesDept) && (!coursesKw || c.name.indexOf(coursesKw) !== -1 || c.code.indexOf(coursesKw.toUpperCase().trim()) !== -1);
        }).map(function (c) {
          var n = enrolledStudentIds(c.code).length;
          var full = n >= c.capacity;
          return '<tr><td>' + h(c.code) + '</td><td><b>' + h(c.name) + '</b></td><td class="num-c">' + c.credits + '</td><td>' + h(c.dept) + '</td>' +
            '<td>' + h(byId(c.teacherId) ? byId(c.teacherId).name : '-') + '</td><td>' + scheduleText(c) + '</td><td>' + h(c.room) + '</td>' +
            '<td class="num-c">' + n + '/' + c.capacity + '</td><td>' + (full ? '<span class="badge red">額滿</span>' : '<span class="badge blue">開放中</span>') + '</td></tr>';
        }).join('') + '</tbody></table>';
    }
    html += '<div class="card">' + body + '</div>';
    $('view-courses').innerHTML = html;
  }
  function setCourseTab(t) { courseTab = t; renderCourses(); }
  function setCoursesKw(v) { coursesKw = v; renderCourses(); }
  function setCoursesDept(v) { coursesDept = v; renderCourses(); }
  function enrollCourse(code) {
    var db = DB.getDb();
    var c = courseByCode(code);
    if (!confirm('確定加選「' + c.name + '」嗎？')) return;
    if (isEnrolled(user.id, code)) { toast('你已選過此課程', false); return; }
    if (hasConflictWith(user.id, code)) { toast('與已選課程時間衝突，無法加選！', false); return; }
    if (enrollCredits(user.id) + c.credits > db.portal.maxCredits) { toast('超過本學期學分上限（' + db.portal.maxCredits + '）', false); return; }
    if (enrolledStudentIds(code).length >= c.capacity) { toast('課程已額滿', false); return; }
    db.enrollments.push({ studentId: user.id, courseCode: code, semester: SEM });
    DB.save(db); renderCourses(); toast('加選成功！');
  }
  function dropCourse(code) {
    if (!confirm('確定退選「' + courseByCode(code).name + '」嗎？')) return;
    var db = DB.getDb();
    db.enrollments = db.enrollments.filter(function (e) { return !(e.courseCode === code && e.studentId === user.id && e.semester === SEM); });
    DB.save(db); renderCourses(); toast('已退選課程', false);
  }
  function courseRoster(code) {
    var c = courseByCode(code);
    var ids = enrolledStudentIds(code);
    var rows = ids.map(function (sid) {
      var s = byId(sid);
      return '<tr><td>' + (s ? h(s.studentId || s.id) : sid) + '</td><td>' + (s ? h(s.name) : '') + '</td><td>' + (s ? h(s.dept) : '') + '</td></tr>';
    }).join('') || '<tr><td colspan="3" class="empty-tip">目前無人選課</td></tr>';
    openModal(
      '<div class="modal-head"><h3>' + h(c.code) + ' ' + h(c.name) + ' 選課名單</h3><button class="close" onclick="App.closeModal()">×</button></div>' +
      '<div class="modal-body"><div style="font-size:13px;color:#6b7a8c;margin-bottom:10px">選課人數：' + ids.length + ' / ' + c.capacity + '</div>' +
      '<table class="tbl"><thead><tr><th>學號</th><th>姓名</th><th>系所</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
    );
  }
  function openCourseForm() {
    openModal(
      '<div class="modal-head"><h3>新增課程</h3><button class="close" onclick="App.closeModal()">×</button></div>' +
      '<div class="modal-body">' +
      '<div class="form-row"><label>開課代碼</label><input id="nc_code" placeholder="例：CSE3999"></div>' +
      '<div class="form-row"><label>課程名稱</label><input id="nc_name"></div>' +
      '<div class="form-row"><label>學分數</label><input id="nc_credits" type="number" min="1" max="6" value="3"></div>' +
      '<div class="form-row"><label>系所</label><input id="nc_dept" placeholder="例：資訊工程學系"></div>' +
      '<div class="form-row"><label>教室</label><input id="nc_room" placeholder="例：工一A101"></div>' +
      '<div class="form-row"><label>上課時間（星期 / 起始節 / 結束節）</label><div style="display:flex;gap:8px">' +
      '<input id="nc_day" placeholder="星期 1-7" style="width:86px"><input id="nc_start" placeholder="起始節" style="width:86px"><input id="nc_end" placeholder="結束節" style="width:86px"></div></div>' +
      '<div class="form-actions"><button class="btn" onclick="App.closeModal()">取消</button><button class="btn primary" onclick="App.saveCourse()">儲存</button></div>' +
      '</div>'
    );
  }
  function saveCourse() {
    var db = DB.getDb();
    var code = $('nc_code').value.trim().toUpperCase(), name = $('nc_name').value.trim();
    if (!code || !name) { toast('請填寫代碼與名稱', false); return; }
    if (courseByCode(code)) { toast('課程代碼已存在', false); return; }
    var d = parseInt($('nc_day').value, 10) || 1, s = parseInt($('nc_start').value, 10) || 1, e = parseInt($('nc_end').value, 10) || 2;
    db.courses.push({
      code: code, name: name, teacherId: user.id, credits: parseInt($('nc_credits').value, 10) || 3,
      dept: $('nc_dept').value.trim() || user.dept, room: $('nc_room').value.trim() || '未指定',
      grade: '各年級', capacity: 60, enrolled: 0,
      schedule: [{ day: d, start: Math.max(1, s), end: Math.max(1, e) }], note: ''
    });
    DB.save(db); closeModal(); renderCourses(); toast('課程已建立');
  }

  /* ---------- 課表管理 ---------- */
  function buildScheduleMatrix(courses) {
    var pos = [];
    for (var p = 1; p <= 8; p++) { pos[p] = []; for (var d = 1; d <= 5; d++) pos[p][d] = null; }
    var blocks = [];
    courses.forEach(function (c) {
      (c.schedule || []).forEach(function (s) {
        if (s.day >= 1 && s.day <= 5) blocks.push({ c: c, day: s.day, start: s.start, end: s.end });
      });
    });
    var used = [];
    blocks.forEach(function (b) {
      var sp = Math.min(8, Math.max(1, b.end)) - b.start + 1, rows = 0;
      for (var p = b.start; p <= Math.min(8, b.end); p++) {
        if (!used[p]) used[p] = [];
        used[p][b.day] = b;
        rows++;
      }
    });
    var htmlRows = '';
    for (p = 1; p <= 8; p++) {
      htmlRows += '<tr><td class="row-label">第' + p + '節<br>' + (PERIOD_TIME[p] || '') + '</td>';
      for (d = 1; d <= 5; d++) {
        var blk = used[p] && used[p][d];
        if (blk == null) { htmlRows += '<td class="empty"></td>'; continue; }
        if (blk.start !== p) { htmlRows += '<td></td>'; continue; }
        var span = Math.min(8, blk.end) - blk.start + 1;
        var color = DEPT_COLOR[blk.c.dept] || '#1a5fb4';
        var teacher = byId(blk.c.teacherId);
        var extra = teacher ? '<div class="c-room">' + h(teacher.name) + '</div>' : '';
        htmlRows += '<td rowspan="' + span + '" style="padding:3px"><div class="course-cell" style="background:' + color + ';border-color:' + color + ';color:#fff">' +
          '<div class="c-name">' + h(blk.c.name) + '</div>' +
          '<div class="c-room">' + h(blk.c.room) + ' · ' + h(blk.c.code) + '</div>' + extra + '</div></td>';
      }
      htmlRows += '</tr>';
    }
    return '<div class="schedule-wrap"><table class="schedule"><thead><tr><th class="row-label">星期\節次</th>' +
      '<th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th></tr></thead><tbody>' + htmlRows + '</tbody></table></div>';
  }
  function listCourses(list) {
    if (!list.length) return '<div class="empty-tip">尚無課程</div>';
    return '<table class="tbl"><thead><tr><th>代碼</th><th>課程</th><th>學分</th><th>教師</th><th>時間</th><th>教室</th></tr></thead><tbody>' +
      list.map(function (c) {
        var teacher = byId(c.teacherId);
        return '<tr><td>' + h(c.code) + '</td><td><b>' + h(c.name) + '</b></td><td class="num-c">' + c.credits + '</td><td>' + h(teacher ? teacher.name : '-') + '</td>' +
          '<td>' + scheduleText(c) + '</td><td>' + h(c.room) + '</td></tr>';
      }).join('') + '</tbody></table>';
  }
  function renderSchedule() {
    var db = DB.getDb(), courses = [], extra = '';
    if (user.role === 'student') {
      courses = db.enrollments.filter(function (e) { return e.studentId === user.id && e.semester === SEM; })
        .map(function (e) { return courseByCode(e.courseCode); }).filter(Boolean);
      var credits = courses.reduce(function (s, c) { return s + c.credits; }, 0);
      extra = '<div class="page-head"><h2>我的課表</h2><div class="desc">' + h(user.name) + ' · ' + h(user.dept) + ' ' + h(user.grade) + ' · 共 ' + courses.length + ' 門課 / ' + credits + ' 學分</div></div>' +
        '<div class="card">' + (courses.length ? buildScheduleMatrix(courses) : '<div class="empty-tip">目前尚未選課，請先至選課系統加選課程</div>') + '</div>' +
        '<div class="card"><h3>課程明細</h3>' + listCourses(courses) + '</div>';
    } else if (user.role === 'teacher') {
      courses = db.courses.filter(function (c) { return c.teacherId === user.id; });
      extra = '<div class="page-head"><h2>授課課表</h2><div class="desc">' + h(user.name) + ' 教師 · 本學期授課 ' + courses.length + ' 門</div></div>' +
        '<div class="card">' + (courses.length ? buildScheduleMatrix(courses) : '<div class="empty-tip">本學期尚無授課</div>') + '</div>' +
        '<div class="card"><h3>授課明細</h3>' + listCourses(courses) + '</div>';
    } else {
      courses = db.courses;
      extra = '<div class="page-head"><h2>全校課程課表</h2><div class="desc">各系所課程配置總覽（依系所色彩區分）</div></div>' +
        '<div class="card">' + buildScheduleMatrix(courses) + '</div>' +
        '<div class="card"><h3>色彩對照</h3><div style="display:flex;gap:16px;flex-wrap:wrap">' +
        Object.keys(DEPT_COLOR).map(function (k) { return '<span><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:' + DEPT_COLOR[k] + ';margin-right:6px;vertical-align:-2px"></span>' + h(k) + '</span>'; }).join('') +
        '</div></div>';
    }
    $('view-schedule').innerHTML = extra;
  }

  /* ---------- 成績查詢 ---------- */
  function renderGrades() {
    var db = DB.getDb(), html = '', body = '';
    if (user.role === 'student') {
      var myGrades = db.grades.filter(function (g) { return g.studentId === user.id; });
      var sems = [], seen = {};
      myGrades.forEach(function (g) { if (!seen[g.semester]) { seen[g.semester] = 1; sems.push(g.semester); } });
      sems.sort().reverse();
      var totalC = myGrades.reduce(function (s, g) { return s + g.credits; }, 0);
      var gpa = totalC ? (myGrades.reduce(function (s, g) { return s + g.credits * gradePoints(g.rank); }, 0) / totalC) : 0;
      html += '<div class="page-head"><h2>成績查詢</h2><div class="desc">歷年修課成績與平均分析</div></div>';
      html += '<div class="stat-grid" style="margin-bottom:18px">' +
        '<div class="stat"><div class="num">' + sems.length + '</div><div class="lbl">已修習學期數</div></div>' +
        '<div class="stat"><div class="num">' + totalC + '</div><div class="lbl">累計取得學分</div></div>' +
        '<div class="stat"><div class="num">' + gpa.toFixed(2) + '</div><div class="lbl">累計 GPA</div></div>' +
        '<div class="stat"><div class="num">' + myGrades.length + '</div><div class="lbl">課程總數</div></div>' +
        '</div>';
      sems.forEach(function (s) {
        var gs = myGrades.filter(function (g) { return g.semester === s; });
        var c = gs.reduce(function (x, g) { return x + g.credits; }, 0);
        var sgpa = c ? (gs.reduce(function (x, g) { return x + g.credits * gradePoints(g.rank); }, 0) / c) : 0;
        body += '<div class="card"><h3>' + h(s) + ' 學期 <span class="badge-inline badge blue">平均 GPA ' + sgpa.toFixed(2) + '</span></h3>' +
          '<table class="tbl"><thead><tr><th>課程</th><th>代碼</th><th>學分</th><th>分數</th><th>等第</th></tr></thead><tbody>' +
          gs.map(function (g) {
            var rankColor = { 'A': 'green', 'A+': 'green', 'A-': 'green', 'B+': 'blue', 'B': 'blue', 'B-': 'blue', 'C+': 'gold', 'C': 'gold', 'C-': 'gold' }[g.rank] || 'gray';
            return '<tr><td><b>' + h(g.courseName) + '</b></td><td>' + h(g.code) + '</td><td class="num-c">' + g.credits + '</td>' +
              '<td class="num-c">' + (g.score != null ? g.score : '-') + '</td><td class="num-c"><span class="badge ' + rankColor + '">' + h(g.rank) + '</span></td></tr>';
          }).join('') + '</tbody></table></div>';
      });
      if (!sems.length) body = '<div class="empty-tip">尚無成績紀錄</div>';
    } else if (user.role === 'teacher') {
      var myCourses = db.courses.filter(function (c) { return c.teacherId === user.id; });
      html += '<div class="page-head"><h2>成績登錄</h2><div class="desc">選擇課程輸入學生成績</div></div>';
      body = '<table class="tbl"><thead><tr><th>課程</th><th>代碼</th><th>學分</th><th>修課人數</th><th>動作</th></tr></thead><tbody>' +
        myCourses.map(function (c) {
          return '<tr><td><b>' + h(c.name) + '</b></td><td>' + h(c.code) + '</td><td class="num-c">' + c.credits + '</td>' +
            '<td class="num-c">' + enrolledStudentIds(c.code).length + '</td><td><button class="btn sm primary" onclick="App.openGradeEntry(\'' + c.code + '\')">輸入成績</button></td></tr>';
        }).join('') + '</tbody></table>';
      if (!myCourses.length) body = '<div class="empty-tip">本學期尚無授課</div>';
    } else {
      var allStudents = db.users.filter(function (u) { return u.role === 'student'; });
      html += '<div class="page-head"><h2>全校成績查詢</h2><div class="desc">學生歷年成績總覽</div></div>';
      var rows = allStudents.map(function (s) {
        var gs = db.grades.filter(function (g) { return g.studentId === s.id; });
        var c = gs.reduce(function (x, g) { return x + g.credits; }, 0);
        var gpa = c ? (gs.reduce(function (x, g) { return x + g.credits * gradePoints(g.rank); }, 0) / c) : 0;
        return '<tr><td>' + h(s.studentId || s.id) + '</td><td>' + h(s.name) + '</td><td>' + h(s.dept) + '</td>' +
          '<td class="num-c">' + gs.length + '</td><td class="num-c">' + c + '</td><td class="num-c">' + gpa.toFixed(2) + '</td></tr>';
      }).join('');
      body = '<div class="card"><table class="tbl"><thead><tr><th>學號</th><th>姓名</th><th>系所</th><th>課程數</th><th>取得學分</th><th>GPA</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    }
    $('view-grades').innerHTML = html + body;
  }
  function openGradeEntry(code) {
    var c = courseByCode(code);
    var ids = enrolledStudentIds(code);
    if (!ids.length) { toast('此課程無人選修', false); return; }
    var db = DB.getDb();
    var rows = ids.map(function (sid) {
      var s = byId(sid);
      var existing = null;
      db.grades.forEach(function (g) { if (g.studentId === sid && g.semester === SEM && g.code === code) existing = g; });
      return '<tr><td>' + (s ? h(s.studentId || sid) : sid) + '</td><td>' + (s ? h(s.name) : '') + '</td>' +
        '<td class="num-c"><input id="gs-' + sid + '" type="number" min="0" max="100" value="' + (existing && existing.score != null ? existing.score : '') + '" style="width:70px;text-align:center"></td>' +
        '<td class="num-c"><button class="btn sm" onclick="App.saveGrade(\'' + code + '\',\'' + sid + '\')">儲存</button></td></tr>';
    }).join('');
    openModal(
      '<div class="modal-head"><h3>' + h(c.code) + ' ' + h(c.name) + ' 成績登錄</h3><button class="close" onclick="App.closeModal()">×</button></div>' +
      '<div class="modal-body"><div style="font-size:13px;color:#6b7a8c;margin-bottom:10px">輸入 0-100 分，儲存後自動換算等第。</div>' +
      '<table class="tbl"><thead><tr><th>學號</th><th>姓名</th><th>分數</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>' +
      '<div class="form-actions"><button class="btn" onclick="App.closeModal()">完成</button></div></div>'
    );
  }
  function saveGrade(code, sid) {
    var val = $('gs-' + sid);
    var score = parseInt(val.value, 10);
    if (isNaN(score) || score < 0 || score > 100) { toast('請輸入 0-100 的分數', false); return; }
    var rank = score >= 90 ? 'A+' : score >= 85 ? 'A' : score >= 80 ? 'A-' : score >= 77 ? 'B+' : score >= 73 ? 'B' : score >= 70 ? 'B-' : score >= 67 ? 'C+' : score >= 63 ? 'C' : score >= 60 ? 'C-' : score >= 50 ? 'D' : 'F';
    var db = DB.getDb();
    var idx = -1;
    db.grades.forEach(function (g, i) { if (g.studentId === sid && g.semester === SEM && g.code === code) idx = i; });
    var c = courseByCode(code);
    if (idx >= 0) { db.grades[idx].score = score; db.grades[idx].rank = rank; }
    else db.grades.push({ studentId: sid, semester: SEM, courseName: c.name, code: code, credits: c.credits, score: score, rank: rank });
    DB.save(db);
    toast('已儲存 ' + (byId(sid) ? byId(sid).name : sid) + ' 的成績（' + rank + '）');
  }

  /* ---------- 教務 / 學務行政 ---------- */
  function renderAffairs() {
    var db = DB.getDb(), html = '', body = '', tabs = [];
    html += '<div class="page-head"><h2>教務 / 學務行政</h2><div class="desc">學籍資料管理、請假申請與審核、獎懲紀錄</div></div>';
    if (user.role === 'student') {
      tabs = [{ k: 'profile', l: '學籍資料' }, { k: 'leave', l: '請假申請' }, { k: 'reward', l: '獎懲紀錄' }];
      html += tabBar(tabs, affairTab);
      if (affairTab === 'profile') {
        body = profileTable(user);
      } else if (affairTab === 'leave') {
        var myLeaves = db.leaves.filter(function (l) { return l.studentId === user.id; });
        body += '<div class="card"><h3>新增請假申請</h3>' +
          '<div class="form-row"><label>假別</label><select id="lv_type"><option>病假</option><option>事假</option><option>公假</option><option>喪假</option><option>生理假</option></select></div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0 14px"><div class="form-row"><label>起日</label><input id="lv_start" type="date"></div><div class="form-row"><label>迄日</label><input id="lv_end" type="date"></div></div>' +
          '<div class="form-row"><label>事由</label><textarea id="lv_reason" rows="3"></textarea></div>' +
          '<div class="form-actions"><button class="btn primary" onclick="App.submitLeave()">送出申請</button></div></div>';
        body += '<div class="card"><h3>我的請假紀錄</h3>' +
          (myLeaves.length ? '<table class="tbl"><thead><tr><th>假別</th><th>日期</th><th>事由</th><th>狀態</th><th>審核者</th></tr></thead><tbody>' +
            myLeaves.map(function (l) {
              var st = { '待審核': 'gold', '已核准': 'green', '已駁回': 'red' }[l.status];
              return '<tr><td>' + h(l.type) + '</td><td>' + h(l.start) + ' ~ ' + h(l.end) + '</td><td>' + h(l.reason) + '</td>' +
                '<td><span class="badge ' + st + '">' + h(l.status) + '</span></td><td>' + h(l.reviewer || '-') + '</td></tr>';
            }).join('') + '</tbody></table>' : '<div class="empty-tip">尚無請假紀錄</div>') + '</div>';
      } else {
        var rewards = db.rewards.filter(function (r) { return r.studentId === user.id; });
        var rep = { '嘉獎': 1, '小功': 3, '大功': 9, '警告': -1, '小過': -3, '大過': -9 };
        var merit = rewards.reduce(function (s, r) { return s + (rep[r.item] || 0); }, 0);
        body = '<div class="card"><h3>德育總分：' + merit + ' 分</h3>' +
          (rewards.length ? '<table class="tbl"><thead><tr><th>日期</th><th>類別</th><th>獎懲</th><th>事由</th></tr></thead><tbody>' +
            rewards.map(function (r) {
              return '<tr><td>' + h(r.date) + '</td><td><span class="badge ' + (r.kind === '獎勵' ? 'green' : 'red') + '">' + h(r.kind) + '</span></td><td><b>' + h(r.item) + '</b></td><td>' + h(r.reason) + '</td></tr>';
            }).join('') + '</tbody></table>' : '<div class="empty-tip">尚無獎懲紀錄</div>') + '</div>';
      }
    } else if (user.role === 'teacher') {
      tabs = [{ k: 'leave', l: '學生請假審核' }, { k: 'reward', l: '獎懲紀錄' }];
      html += tabBar(tabs, affairTab);
      if (affairTab === 'leave') {
        var pend = db.leaves.filter(function (l) { return l.status === '待審核'; });
        body = '<div class="card"><h3>待審核請假申請（' + pend.length + '）</h3>' +
          (pend.length ? '<table class="tbl"><thead><tr><th>學生</th><th>系所</th><th>假別</th><th>日期</th><th>事由</th><th>動作</th></tr></thead><tbody>' +
            pend.map(function (l) {
              var s = byId(l.studentId);
              return '<tr><td>' + (s ? h(s.name) : '') + '</td><td>' + (s ? h(s.dept) : '') + '</td><td>' + h(l.type) + '</td><td>' + h(l.start) + ' ~ ' + h(l.end) + '</td><td>' + h(l.reason) + '</td>' +
                '<td><button class="btn sm success" onclick="App.reviewLeave(\'' + l.id + '\',1)">核准</button> <button class="btn sm danger" onclick="App.reviewLeave(\'' + l.id + '\',0)">駁回</button></td></tr>';
            }).join('') + '</tbody></table>' : '<div class="empty-tip">目前沒有待審核的請假申請</div>') + '</div>';
      } else {
        body = '<div class="card">' + rewardTable(db.rewards) + '</div>';
      }
    } else {
      tabs = [{ k: 'leave', l: '全校請假審核' }, { k: 'reward', l: '全校獎懲' }, { k: 'profile', l: '學籍總覽' }];
      html += tabBar(tabs, affairTab);
      if (affairTab === 'leave') {
        body = '<div class="card"><h3>全校請假申請</h3><table class="tbl"><thead><tr><th>學生</th><th>系所</th><th>假別</th><th>日期</th><th>事由</th><th>狀態</th><th>動作</th></tr></thead><tbody>' +
          db.leaves.slice().sort(function (a, b) { return b.id.localeCompare(a.id); }).map(function (l) {
            var s = byId(l.studentId);
            var st = { '待審核': 'gold', '已核准': 'green', '已駁回': 'red' }[l.status];
            var act = l.status === '待審核' ? '<button class="btn sm success" onclick="App.reviewLeave(\'' + l.id + '\',1)">核准</button> <button class="btn sm danger" onclick="App.reviewLeave(\'' + l.id + '\',0)">駁回</button>' : '-';
            return '<tr><td>' + (s ? h(s.name) : '') + '</td><td>' + (s ? h(s.dept) : '') + '</td><td>' + h(l.type) + '</td><td>' + h(l.start) + ' ~ ' + h(l.end) + '</td><td>' + h(l.reason) + '</td>' +
              '<td><span class="badge ' + st + '">' + h(l.status) + '</span></td><td>' + act + '</td></tr>';
          }).join('') + '</tbody></table></div>';
      } else if (affairTab === 'reward') {
        body = '<div class="card"><h3>全校獎懲紀錄</h3>' + rewardTable(db.rewards) + '</div>';
      } else {
        var studs = db.users.filter(function (u) { return u.role === 'student'; });
        body = '<div class="card"><table class="tbl"><thead><tr><th>學號</th><th>姓名</th><th>系所</th><th>年級</th><th>入學年</th><th>導師</th><th>學籍狀態</th></tr></thead><tbody>' +
          studs.map(function (s) {
            return '<tr><td>' + h(s.studentId || s.id) + '</td><td>' + h(s.name) + '</td><td>' + h(s.dept) + '</td><td>' + h(s.grade) + '</td><td>' + h(s.enrollYear || '-') + '</td>' +
              '<td>' + h(s.advisor || '-') + '</td><td><span class="badge ' + (s.status === '在學' ? 'green' : 'gold') + '">' + h(s.status || '在學') + '</span></td></tr>';
          }).join('') + '</tbody></table></div>';
      }
    }
    $('view-affairs').innerHTML = html + body;
  }
  function tabBar(tabs, active) {
    return '<div class="tab-bar">' + tabs.map(function (t) {
      return '<div class="tab' + (active === t.k ? ' active' : '') + '" onclick="App.setAffairTab(\'' + t.k + '\')">' + t.l + '</div>';
    }).join('') + '</div>';
  }
  function setAffairTab(t) { affairTab = t; renderAffairs(); }
  function rewardTable(list) {
    return '<table class="tbl"><thead><tr><th>學生</th><th>日期</th><th>類別</th><th>獎懲</th><th>事由</th></tr></thead><tbody>' +
      (list.length ? list.map(function (r) {
        var s = byId(r.studentId);
        return '<tr><td>' + (s ? h(s.name) + '（' + h(s.studentId || s.id) + '）' : '') + '</td><td>' + h(r.date) + '</td>' +
          '<td><span class="badge ' + (r.kind === '獎勵' ? 'green' : 'red') + '">' + h(r.kind) + '</span></td><td><b>' + h(r.item) + '</b></td><td>' + h(r.reason) + '</td></tr>';
      }).join('') : '<tr><td colspan="5" class="empty-tip">尚無獎懲紀錄</td></tr>') + '</tbody></table>';
  }
  function profileTable(u) {
    var rows = [
      ['學號 / 帳號', u.studentId || u.id], ['姓名', u.name], ['系所', u.dept],
      ['年級', u.grade || u.title || '-'], ['輔導老師', u.advisor || '-'], ['入學年度', u.enrollYear || '-'],
      ['學籍狀態', u.status || '在學'], ['E-mail', u.email], ['聯絡電話', u.phone]
    ];
    return '<div class="card"><h3>基本學籍資料</h3>' +
      '<table class="tbl"><tbody>' + rows.map(function (r) { return '<tr><td style="width:160px;color:#6b7a8c">' + r[0] + '</td><td><b>' + h(r[1]) + '</b></td></tr>'; }).join('') + '</tbody></table></div>';
  }
  function submitLeave() {
    var type = $('lv_type').value, start = $('lv_start').value, end = $('lv_end').value, reason = $('lv_reason').value.trim();
    if (!start || !end || !reason) { toast('請完整填寫請假資料', false); return; }
    var db = DB.getDb();
    db.leaves.unshift({ id: 'l' + Date.now(), studentId: user.id, type: type, start: start, end: end, reason: reason, status: '待審核', reviewer: '' });
    DB.save(db); renderAffairs(); toast('請假申請已送出，待審核');
  }
  function reviewLeave(id, approve) {
    var db = DB.getDb();
    db.leaves.forEach(function (l) { if (l.id === id) { l.status = approve ? '已核准' : '已駁回'; l.reviewer = user.name + '（' + Auth.roleLabel(user.role) + '）'; } });
    DB.save(db); renderAffairs(); toast(approve ? '已核准請假' : '已駁回請假', approve ? true : false);
  }

  /* ---------- 帳號管理 ---------- */
  function accountBody(u) {
    var row = function (a, b) { return '<tr><td style="width:160px;color:#6b7a8c">' + a + '</td><td><b>' + h(b) + '</b></td></tr>'; };
    return '' +
      '<div class="card"><h3>個人基本資料</h3><table class="tbl"><tbody>' +
      row('帳號', u.username) + row('姓名', u.name) + row('角色', Auth.roleLabel(u.role)) +
      row('系所 / 單位', u.dept) + row('年級 / 職稱', u.grade || u.title || '-') +
      row('E-mail', u.email) + row('聯絡電話', u.phone) + '</tbody></table></div>' +
      '<div class="two-col">' +
      '<div class="card"><h3>編輯個人資料</h3>' +
      '<div class="form-row"><label>E-mail</label><input id="pr_email" value="' + h(u.email || '') + '"></div>' +
      '<div class="form-row"><label>聯絡電話</label><input id="pr_phone" value="' + h(u.phone || '') + '"></div>' +
      '<div class="form-actions"><button class="btn primary" onclick="App.saveProfile()">儲存</button></div></div>' +
      '<div class="card"><h3>變更密碼</h3>' +
      '<div class="form-row"><label>目前密碼</label><input id="pw_old" type="password"></div>' +
      '<div class="form-row"><label>新密碼</label><input id="pw_new" type="password" placeholder="至少 6 字元"></div>' +
      '<div class="form-row"><label>確認新密碼</label><input id="pw_new2" type="password"></div>' +
      '<div class="form-actions"><button class="btn primary" onclick="App.changePassword()">變更密碼</button></div></div>' +
      '</div>';
  }
  function renderAccount() {
    var db = DB.getDb(), html = '';
    if (user.role === 'admin') {
      html += '<div class="page-head"><h2>帳號管理</h2><div class="desc">系統帳號維護與個人資料</div></div>';
      html += '<div class="tab-bar"><div class="tab' + (accTab === 'users' ? ' active' : '') + '" onclick="App.setAccTab(\'users\')">全校帳號</div>' +
        '<div class="tab' + (accTab === 'profile' ? ' active' : '') + '" onclick="App.setAccTab(\'profile\')">我的個人資料</div></div>';
      if (accTab === 'users') {
        html += '<div class="toolbar"><input type="text" placeholder="搜尋帳號、姓名…" value="' + h(userKw) + '" oninput="App.setUserKw(this.value)" style="width:240px">' +
          '<div class="spacer" style="flex:1"></div><button class="btn primary" onclick="App.openUserForm()">＋ 新增帳號</button></div>';
        html += '<div class="card"><table class="tbl"><thead><tr><th>帳號</th><th>姓名</th><th>角色</th><th>系所 / 單位</th><th>聯絡資訊</th><th>動作</th></tr></thead><tbody>' +
          db.users.filter(function (u) { return !userKw || u.username.indexOf(userKw) !== -1 || u.name.indexOf(userKw) !== -1; }).map(function (u) {
            var roleCls = { admin: 'admin', teacher: 'teacher', student: 'student' }[u.role];
            var resetBtn = user.id !== u.id ? '<button class="btn sm" onclick="App.resetPwd(\'' + u.id + '\')">重設密碼</button>' : '';
            var delBtn = user.id !== u.id ? '<button class="btn sm danger" onclick="App.removeUser(\'' + u.id + '\')">刪除</button>' : '';
            return '<tr><td>' + h(u.username) + '</td><td><b>' + h(u.name) + '</b></td>' +
              '<td><span class="role-tag ' + roleCls + '">' + Auth.roleLabel(u.role) + '</span></td>' +
              '<td>' + h(u.dept) + (u.grade ? ' · ' + h(u.grade) : '') + '</td><td>' + h(u.email || '-') + '<br>' + h(u.phone || '-') + '</td>' +
              '<td>' + resetBtn + ' ' + delBtn + '</td></tr>';
          }).join('') + '</tbody></table></div>';
      } else {
        html += accountBody(user);
      }
    } else {
      html += '<div class="page-head"><h2>帳號管理</h2><div class="desc">個人資料與安全設定</div></div>' + accountBody(user);
    }
    $('view-account').innerHTML = html;
  }
  function setAccTab(t) { accTab = t; renderAccount(); }
  function setUserKw(v) { userKw = v; renderAccount(); }
  function saveProfile() {
    var db = DB.getDb();
    db.users.forEach(function (u) { if (u.id === user.id) { u.email = $('pr_email').value.trim(); u.phone = $('pr_phone').value.trim(); } });
    DB.save(db); user = DB.userById(user.id); if (user) DB.setCurrent(user); renderAccount(); toast('個人資料已更新');
  }
  function changePassword() {
    var oldP = $('pw_old').value, nu = $('pw_new').value, nu2 = $('pw_new2').value;
    if (oldP !== user.password) { toast('目前密碼錯誤', false); return; }
    if (nu.length < 6) { toast('新密碼至少 6 字元', false); return; }
    if (nu !== nu2) { toast('兩次輸入的新密碼不一致', false); return; }
    var db = DB.getDb();
    db.users.forEach(function (u) { if (u.id === user.id) u.password = nu; });
    DB.save(db); user.password = nu; DB.setCurrent(user);
    $('pw_old').value = $('pw_new').value = $('pw_new2').value = '';
    toast('密碼已變更');
  }
  function openUserForm() {
    openModal(
      '<div class="modal-head"><h3>新增系統帳號</h3><button class="close" onclick="App.closeModal()">×</button></div>' +
      '<div class="modal-body">' +
      '<div class="form-row"><label>帳號</label><input id="nu_username"></div>' +
      '<div class="form-row"><label>姓名</label><input id="nu_name"></div>' +
      '<div class="form-row"><label>角色</label><select id="nu_role"><option value="student">學生</option><option value="teacher">教師</option><option value="admin">管理員</option></select></div>' +
      '<div class="form-row"><label>系所 / 單位</label><input id="nu_dept" placeholder="例：資訊工程學系"></div>' +
      '<div class="form-row"><label>初始密碼</label><input id="nu_pwd" value="123456"></div>' +
      '<div class="form-actions"><button class="btn" onclick="App.closeModal()">取消</button><button class="btn primary" onclick="App.saveUser()">建立</button></div>' +
      '</div>'
    );
  }
  function saveUser() {
    var db = DB.getDb();
    var un = $('nu_username').value.trim(), name = $('nu_name').value.trim(), role = $('nu_role').value, dept = $('nu_dept').value.trim();
    if (!un || !name) { toast('請填寫帳號與姓名', false); return; }
    for (var i = 0; i < db.users.length; i++) if (db.users[i].username === un) { toast('帳號名稱已存在', false); return; }
    db.users.push({
      id: 'u' + Date.now(), username: un, password: $('nu_pwd').value || '123456', name: name, role: role,
      dept: dept || '未指定', studentId: role === 'student' ? un : '', status: '在學'
    });
    DB.save(db); closeModal(); renderAccount(); toast('帳號已建立');
  }
  function resetPwd(id) {
    if (!confirm('確認將此帳號密碼重設為 123456？')) return;
    var db = DB.getDb();
    db.users.forEach(function (u) { if (u.id === id) u.password = '123456'; });
    DB.save(db); renderAccount(); toast('密碼已重設為 123456');
  }
  function removeUser(id) {
    if (id === user.id) { toast('無法刪除自己的帳號', false); return; }
    if (!confirm('確定刪除此帳號？')) return;
    var db = DB.getDb();
    db.users = db.users.filter(function (u) { return u.id !== id; });
    DB.save(db); renderAccount(); toast('帳號已刪除', false);
  }

  /* ---------- 全域 API（供 inline handler 使用） ---------- */
  var api = {
    showView: showView,
    closeModal: closeModal,
    openNews: openNews,
    openNewsForm: openNewsForm,
    saveNews: saveNews,
    deleteNews: deleteNews,
    setNewsKw: setNewsKw,
    setNewsCat: setNewsCat,
    setCourseTab: setCourseTab,
    setCoursesKw: setCoursesKw,
    setCoursesDept: setCoursesDept,
    enrollCourse: enrollCourse,
    dropCourse: dropCourse,
    courseRoster: courseRoster,
    openCourseForm: openCourseForm,
    saveCourse: saveCourse,
    openGradeEntry: openGradeEntry,
    saveGrade: saveGrade,
    setAffairTab: setAffairTab,
    submitLeave: submitLeave,
    reviewLeave: reviewLeave,
    setAccTab: setAccTab,
    setUserKw: setUserKw,
    saveProfile: saveProfile,
    changePassword: changePassword,
    openUserForm: openUserForm,
    saveUser: saveUser,
    resetPwd: resetPwd,
    removeUser: removeUser
  };

  /* ---------- 即時時鐘（對齊系統真實時間） ---------- */
  var WEEK = ['日', '一', '二', '三', '四', '五', '六'];
  function pad2(n) { return n < 10 ? '0' + n : '' + n; }
  function startRealTimeClock() {
    var el = $('realtime');
    if (!el) return;
    function tick() {
      var now = new Date();
      el.textContent = now.getFullYear() + ' 年 ' + (now.getMonth() + 1) + ' 月 ' + now.getDate() + ' 日 星期' + WEEK[now.getDay()] +
        '  ' + pad2(now.getHours()) + ':' + pad2(now.getMinutes()) + ':' + pad2(now.getSeconds());
    }
    tick();
    setInterval(tick, 1000);
  }

  /* ---------- 初始化 ---------- */
  function init() {
    modalRoot = $('modalRoot');
    user = Auth.requireLogin();
    if (!user) return;
    $('userName').textContent = user.name;
    $('userRole').textContent = Auth.roleLabel(user.role) + ' · ' + user.dept;
    $('userAvatar').textContent = avatarText(user.name);
    var portal = DB.getDb().portal;
    if (portal && portal.semester) $('semesterLabel').textContent = portal.semester;
    $('logoutBtn').addEventListener('click', Auth.logout);
    document.addEventListener('click', function (e) {
      if (e.target.classList && e.target.classList.contains('modal-mask')) closeModal();
    });
    buildSidebar();
    renderHome();
    startRealTimeClock();
  }

  document.addEventListener('DOMContentLoaded', init);

  return api;
})();