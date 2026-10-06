/* ===== 登入驗證邏輯 ===== */
window.Auth = (function () {
  function login(username, password) {
    var db = DB.getDb();
    for (var i = 0; i < db.users.length; i++) {
      var u = db.users[i];
      if (u.username === username && u.password === password) {
        DB.setCurrent(u);
        return { ok: true, user: u };
      }
    }
    return { ok: false, msg: '帳號或密碼錯誤，請重新輸入' };
  }

  function logout() { DB.clearCurrent(); window.location.href = 'index.html'; }

  function current() { return DB.getCurrent(); }

  function requireLogin() {
    var u = DB.getCurrent();
    if (!u) { window.location.href = 'index.html'; return null; }
    // 以最新資料重新取得使用者（避免帳號異動後資料過期）
    var fresh = DB.userById(u.id);
    if (!fresh) { logout(); return null; }
    return fresh;
  }

  var ROLE_LABEL = { student: '學生', teacher: '教師', admin: '管理員' };
  function roleLabel(r) { return ROLE_LABEL[r] || r; }

  function checkPermission(user, targets) {
    return targets.indexOf(user.role) !== -1;
  }

  return {
    login: login,
    logout: logout,
    current: current,
    requireLogin: requireLogin,
    roleLabel: roleLabel,
    checkPermission: checkPermission
  };
})();