/* ===== 資料層：以 localStorage 模擬資料庫（日期全部動態對齊真實時間） ===== */
window.DB = (function () {
  var DB_KEY = 'nqu_system_db_v2';
  var CURRENT_KEY = 'nqu_system_current_user';

  /* ---------- 日期工具 ---------- */
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function fmtDate(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function addDays(base, n) { var d = new Date(base); d.setDate(d.getDate() + n); return d; }
  function daysAgo(n) { return fmtDate(addDays(new Date(), -n)); }
  function upcoming(n) { return fmtDate(addDays(new Date(), n)); }

  /* 依目前日期計算台灣學年學期（第 1 學期：9-1 月；第 2 學期：2-8 月） */
  function academic() {
    var now = new Date(), greg = now.getFullYear(), month = now.getMonth() + 1, year, sem;
    if (month >= 9) { year = greg - 1911; sem = 1; }
    else { year = greg - 1912; sem = 2; }
    return {
      key: year + '-' + sem,
      text: year + ' 學年度 第 ' + sem + ' 學期',
      prev: sem === 1 ? (year - 1) + '-2' : year + '-1'
    };
  }

  function seedData() {
    var ac = academic();
    return {
      portal: {
        semester: ac.text,
        semesterKey: ac.key,
        prevSemester: ac.prev,
        enrollDeadline: upcoming(14),
        maxCredits: 25,
        minCredits: 9
      },
      users: [
        { id: 'admin', username: 'admin', password: 'admin123', name: '張依婷', role: 'admin', dept: '教務處', title: '教務組長', email: 'admin@email.nqu.edu.tw', phone: '082-313301' },
        { id: 't01', username: 'teacher1', password: 'teacher123', name: '李建國', role: 'teacher', dept: '資訊工程學系', title: '副教授', email: 'cklee@email.nqu.edu.tw', phone: '082-313513' },
        { id: 't04', username: 'teacher2', password: 'teacher123', name: '陳淑芬', role: 'teacher', dept: '通識教育中心', title: '助理教授', email: 'sfchen@email.nqu.edu.tw', phone: '082-313401' },
        { id: 's01', username: 'student1', password: 'student123', name: '陳小明', role: 'student', dept: '資訊工程學系', grade: '三年級', studentId: '10923001', email: '10923001@email.nqu.edu.tw', phone: '0911-234567', advisor: '李建國', enrollYear: '109', status: '在學' },
        { id: 's02', username: 'student2', password: 'student123', name: '王曉華', role: 'student', dept: '資訊工程學系', grade: '三年級', studentId: '10923002', email: '10923002@email.nqu.edu.tw', phone: '0922-345678', advisor: '李建國', enrollYear: '109', status: '在學' },
        { id: 's03', username: 'student3', password: 'student123', name: '林怡君', role: 'student', dept: '企業管理學系', grade: '二年級', studentId: '11024003', email: '11024003@email.nqu.edu.tw', phone: '0933-456789', advisor: '黃文忠', enrollYear: '110', status: '在學' }
      ],
      courses: [
        { code: 'CSE2101', name: '資料結構', teacherId: 't01', credits: 3, dept: '資訊工程學系', grade: '二年級', room: '工一A103', capacity: 60, enrolled: 52, schedule: [{ day: 2, start: 2, end: 4 }], note: '必修，需先修「計算機概論」' },
        { code: 'CSE2102', name: '物件導向程式設計', teacherId: 't01', credits: 3, dept: '資訊工程學系', grade: '三年級', room: '計中202', capacity: 55, enrolled: 40, schedule: [{ day: 1, start: 5, end: 7 }], note: '含上機實習' },
        { code: 'CSE3201', name: '資料庫系統', teacherId: 't01', credits: 3, dept: '資訊工程學系', grade: '三年級', room: '工一A102', capacity: 60, enrolled: 45, schedule: [{ day: 3, start: 3, end: 4 }, { day: 4, start: 2, end: 2 }], note: '專業選修' },
        { code: 'CSE3202', name: '作業系統', teacherId: 't01', credits: 3, dept: '資訊工程學系', grade: '三年級', room: '計中203', capacity: 50, enrolled: 38, schedule: [{ day: 5, start: 2, end: 4 }], note: '專業選修' },
        { code: 'GEN1011', name: '微積分(二)', teacherId: 't04', credits: 3, dept: '通識教育中心', grade: '一年級', room: '綜合大樓B203', capacity: 90, enrolled: 75, schedule: [{ day: 1, start: 2, end: 2 }, { day: 4, start: 3, end: 4 }], note: '通識數理領域' },
        { code: 'GEN1021', name: '英文(二)', teacherId: 't04', credits: 2, dept: '通識教育中心', grade: '一年級', room: '綜B101', capacity: 60, enrolled: 58, schedule: [{ day: 2, start: 5, end: 6 }], note: '進階英文會話' },
        { code: 'PED3011', name: '體育(三)', teacherId: 't04', credits: 2, dept: '體育室', grade: '三年級', room: '體育館', capacity: 45, enrolled: 30, schedule: [{ day: 3, start: 6, end: 7 }], note: '羽球' },
        { code: 'MGT2011', name: '統計學', teacherId: 't04', credits: 3, dept: '企業管理學系', grade: '二年級', room: '管A201', capacity: 60, enrolled: 49, schedule: [{ day: 5, start: 5, end: 7 }], note: '必修' },
        { code: 'TOU2011', name: '觀光英語會話', teacherId: 't04', credits: 3, dept: '觀光管理學系', grade: '二年級', room: '觀光大樓505', capacity: 40, enrolled: 22, schedule: [{ day: 2, start: 7, end: 8 }], note: '專業選修' },
        { code: 'SOC1011', name: '服務學習', teacherId: 't04', credits: 1, dept: '學務處', grade: '一年級', room: '綜B303', capacity: 80, enrolled: 66, schedule: [{ day: 4, start: 8, end: 8 }], note: '志工實作課程' }
      ],
      enrollments: [
        { studentId: 's01', courseCode: 'CSE2101', semester: ac.key },
        { studentId: 's01', courseCode: 'CSE2102', semester: ac.key },
        { studentId: 's01', courseCode: 'GEN1021', semester: ac.key },
        { studentId: 's01', courseCode: 'PED3011', semester: ac.key },
        { studentId: 's02', courseCode: 'CSE2101', semester: ac.key },
        { studentId: 's02', courseCode: 'CSE3201', semester: ac.key },
        { studentId: 's02', courseCode: 'GEN1011', semester: ac.key },
        { studentId: 's03', courseCode: 'MGT2011', semester: ac.key },
        { studentId: 's03', courseCode: 'GEN1021', semester: ac.key },
        { studentId: 's03', courseCode: 'TOU2011', semester: ac.key },
        { studentId: 's03', courseCode: 'GEN1011', semester: ac.key }
      ],
      announcements: [
        { id: 'a1', title: '期中考試公告', category: '教務', important: true, author: '教務處', date: daysAgo(0), content: '本學期期中考試將於 11 月 4 日至 11 月 8 日舉行，請各位同學依各課程授課教師公布之考試時間與教室應試。考試期間請攜帶學生證，遵守考場規則。' },
        { id: 'a2', title: '宿舍網路維護通知', category: '總務', important: false, author: '總務處', date: daysAgo(2), content: '因配合機房設備更新，近日夜間 00:00~06:00 宿舍網路將暫停服務，造成不便敬請見諒。' },
        { id: 'a3', title: '圖書館週活動開跑！', category: '圖書館', important: false, author: '圖書館', date: daysAgo(5), content: '圖書館週活動已開辦，包含主題書展、講座與抽獎活動，歡迎全校師生踴躍參與，詳情請見圖書館網頁。' },
        { id: 'a4', title: '學雜費繳費截止提醒', category: '總務', important: true, author: '總務處/出納組', date: daysAgo(7), content: '學雜費繳費單已開放列印，繳費截止日為 ' + upcoming(7) + '，逾期未繳者將依規定無法選課。' },
        { id: 'a5', title: '校園週邊交通安全宣導', category: '學務', important: false, author: '學務處', date: daysAgo(12), content: '近來校園週邊發生多起機車事故，請同學騎乘機車務必戴妥安全帽、減速慢行，遵守交通規則，確保行車安全。' }
      ],
      grades: [
        { studentId: 's01', semester: ac.prev, courseName: '計算機概論', code: 'CSE1101', credits: 3, score: 85, rank: 'A' },
        { studentId: 's01', semester: ac.prev, courseName: '微積分(一)', code: 'GEN1010', credits: 3, score: 78, rank: 'B+' },
        { studentId: 's01', semester: ac.prev, courseName: '英文(一)', code: 'GEN1020', credits: 2, score: 90, rank: 'A+' },
        { studentId: 's01', semester: ac.prev, courseName: '體育(一)', code: 'PED2011', credits: 2, score: 88, rank: 'A-' },
        { studentId: 's02', semester: ac.prev, courseName: '計算機概論', code: 'CSE1101', credits: 3, score: 70, rank: 'B-' },
        { studentId: 's02', semester: ac.prev, courseName: '微積分(一)', code: 'GEN1010', credits: 3, score: 62, rank: 'C+' },
        { studentId: 's02', semester: ac.prev, courseName: '線性代數', code: 'MATH2101', credits: 3, score: 74, rank: 'B' },
        { studentId: 's03', semester: ac.prev, courseName: '管理學', code: 'MGT1101', credits: 3, score: 82, rank: 'A-' },
        { studentId: 's03', semester: ac.prev, courseName: '經濟學', code: 'MGT1201', credits: 3, score: 77, rank: 'B+' },
        { studentId: 's03', semester: ac.prev, courseName: '會計學', code: 'MGT1301', credits: 3, score: 69, rank: 'C+' }
      ],
      leaves: [
        { id: 'l1', studentId: 's01', type: '病假', start: daysAgo(0), end: daysAgo(0), reason: '感冒發燒，至金門醫院就診', status: '待審核', reviewer: '' },
        { id: 'l2', studentId: 's01', type: '事假', start: daysAgo(20), end: daysAgo(19), reason: '家中長輩喪禮', status: '已核准', reviewer: '導師 李建國' }
      ],
      rewards: [
        { id: 'r1', studentId: 's01', kind: '獎勵', item: '嘉獎', date: daysAgo(130), reason: '協助系學會辦理迎新活動，表現優良' },
        { id: 'r2', studentId: 's01', kind: '獎勵', item: '小功', date: daysAgo(90), reason: '代表學校參加全國程式競賽獲佳作' },
        { id: 'r3', studentId: 's02', kind: '懲處', item: '警告', date: daysAgo(160), reason: '上課使用手機影響秩序' }
      ]
    };
  }

  function load() {
    var raw;
    try { raw = localStorage.getItem(DB_KEY); } catch (e) { raw = null; }
    if (!raw) {
      var d = seedData();
      save(d);
      return d;
    }
    try { return JSON.parse(raw); } catch (e) { return seedData(); }
  }

  function save(db) { localStorage.setItem(DB_KEY, JSON.stringify(db)); }

  function getDb() { return load(); }
  function reset() { localStorage.removeItem(DB_KEY); localStorage.removeItem(CURRENT_KEY); window.location.reload(); }

  function setCurrent(user) { localStorage.setItem(CURRENT_KEY, JSON.stringify(user)); }
  function getCurrent() {
    try { return JSON.parse(localStorage.getItem(CURRENT_KEY)) || null; } catch (e) { return null; }
  }
  function clearCurrent() { localStorage.removeItem(CURRENT_KEY); }

  function userById(id) {
    var db = load();
    for (var i = 0; i < db.users.length; i++) if (db.users[i].id === id) return db.users[i];
    return null;
  }
  function courseByCode(code) {
    var db = load();
    for (var i = 0; i < db.courses.length; i++) if (db.courses[i].code === code) return db.courses[i];
    return null;
  }

  return {
    getDb: getDb,
    load: load,
    save: save,
    reset: reset,
    setCurrent: setCurrent,
    getCurrent: getCurrent,
    clearCurrent: clearCurrent,
    userById: userById,
    courseByCode: courseByCode,
    academic: academic,
    today: function () { return fmtDate(new Date()); },
    daysAgo: daysAgo,
    upcoming: upcoming,
    dbKey: DB_KEY
  };
})();