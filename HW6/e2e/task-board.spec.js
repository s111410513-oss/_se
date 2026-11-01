const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  // 每個案例先清除前一個案例留下的資料，確保測試互不影響。
  const existingTasks = await page.request.get('/api/tasks');
  for (const task of await existingTasks.json()) {
    await page.request.delete(`/api/tasks/${task.id}`);
  }
  await page.goto('/');
});

test('shows the task board and empty state', async ({ page }) => {
  await expect(page.getByRole('heading', { name: '今日清單' })).toBeVisible();
  await expect(page.getByText('清單還空空的')).toBeVisible();
});

test('user can add a task and see it in the list', async ({ page }) => {
  await page.getByLabel('新增待辦事項').fill('完成 Playwright 作業');
  await page.getByRole('button', { name: '新增待辦事項' }).click();
  await expect(page.getByText('完成 Playwright 作業')).toBeVisible();
  await expect(page.locator('#task-total')).toHaveText('1 個項目');
});

test('user can complete and filter a task', async ({ page }) => {
  await page.getByLabel('新增待辦事項').fill('練習系統測試');
  await page.getByRole('button', { name: '新增待辦事項' }).click();
  await page.getByRole('checkbox', { name: '完成：練習系統測試' }).check();
  await expect(page.locator('.task-item')).toHaveClass(/done/);
  await page.getByRole('button', { name: '未完成' }).click();
  await expect(page.getByText('練習系統測試')).toHaveCount(0);
  await page.getByRole('button', { name: '已完成' }).click();
  await expect(page.getByText('練習系統測試')).toBeVisible();
});

test('user can delete a task', async ({ page }) => {
  await page.getByLabel('新增待辦事項').fill('這件事要刪除');
  await page.getByRole('button', { name: '新增待辦事項' }).click();
  await page.getByRole('button', { name: '刪除：這件事要刪除' }).click();
  await expect(page.getByText('這件事要刪除')).toHaveCount(0);
  await expect(page.getByText('清單還空空的')).toBeVisible();
});
