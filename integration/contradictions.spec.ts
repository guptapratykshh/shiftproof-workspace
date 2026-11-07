import {
  test,
  expect,
  request as createRequest,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const PASSWORD = "Browser-testing-532";
const PIN = "583719";
const adminEmail = `qa-conflict-admin-${process.pid}@example.com`;
const supervisorEmail = `qa-conflict-supervisor-${process.pid}@example.com`;
const API = process.env.SHIFTPROOF_CONTRADICTION_API || "http://127.0.0.1:8001/api/v1";
const layoutWidths = [320, 390, 768, 900, 1169, 1470, 1600, 1920, 2560];
const appearances = [
  { theme: "dark", language: "en" },
  { theme: "light", language: "hi" },
];

async function setAppearance(page: Page, appearance = appearances[0]) {
  await page.evaluate((value) => {
    localStorage.setItem("shiftproof-theme", value.theme);
    localStorage.setItem("shiftproof-language", value.language);
  }, appearance);
  await page.reload();
}

async function checkWorkspaceLayout(page: Page, label: string, width: number) {
  await expect(page.locator(".workspace-content h1"), label).toBeVisible();
  await expect(page.locator(".work-loading")).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
  const layout = await page.evaluate(() => {
    const grid = document
      .querySelector(".workspace-grid")!
      .getBoundingClientRect();
    const content = document.querySelector(".workspace-content")!;
    const padding = getComputedStyle(content);
    const controls = content.querySelectorAll(
      "h1, h2, h3, button, a.button, input, select, textarea",
    );
    const clipped = [...controls]
      .filter((element) => {
        const box = element.getBoundingClientRect();
        if (!box.width || !box.height) return false;
        // A table or other local scroller may extend inside its own panel.
        let parent = element.parentElement;
        while (parent && parent !== content) {
          if (
            ["auto", "scroll"].includes(getComputedStyle(parent).overflowX) &&
            parent.scrollWidth > parent.clientWidth + 1
          )
            return false;
          parent = parent.parentElement;
        }
        return (
          box.left < -1 ||
          box.right > innerWidth + 1 ||
          (!["INPUT", "SELECT", "TEXTAREA"].includes(element.tagName) &&
            element.scrollWidth > element.clientWidth + 1)
        );
      })
      .map((element) => element.textContent?.trim() || element.id);
    return {
      width: document.documentElement.scrollWidth,
      gridLeft: grid.left,
      gridWidth: grid.width,
      contentRight: content.getBoundingClientRect().right,
      paddingLeft: parseFloat(padding.paddingLeft),
      paddingRight: parseFloat(padding.paddingRight),
      clipped,
    };
  });
  const gutter =
    width <= 600
      ? 16
      : width <= 1000
        ? 24
        : Math.min(48, Math.max(32, width * 0.025));
  expect(layout.width, label).toBeLessThanOrEqual(width + 1);
  expect(layout.gridLeft, label).toBe(0);
  expect(layout.gridWidth, label).toBe(width);
  expect(layout.contentRight, label).toBe(width);
  expect(layout.paddingLeft, label).toBeCloseTo(gutter, 1);
  expect(layout.paddingRight, label).toBeCloseTo(gutter, 1);
  expect(layout.clipped, label).toEqual([]);
}

let seed: {
  organizationId: string;
  departmentId: string;
  shiftId: string;
  teamId: string;
  workerId: string;
  worker2Id: string;
  supervisorId: string;
  taskId: string;
};

function deliveryToken(email: string) {
  return execFileSync(
    path.resolve("backend/.venv/bin/python"),
    ["tests/read_browser_email.py", email],
    {
      encoding: "utf8",
      cwd: path.resolve("backend"),
      env: { ...process.env, PYTHONPATH: "." },
    },
  ).trim();
}
async function send(
  context: APIRequestContext,
  endpoint: string,
  values: unknown,
  method = "post",
) {
  const state = await context.storageState();
  const csrf = state.cookies.find(
    (cookie) => cookie.name === "shiftproof_csrf",
  )?.value;
  const response = await context.fetch(`${API}${endpoint}`, {
    method,
    data: values,
    headers: csrf ? { "X-CSRF-Token": csrf } : {},
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}
const savedAuth = new Map<string, string>();
async function login(
  page: Page,
  role: "organization" | "supervisor" | "worker",
  employee = "QA-01",
) {
  const key = `${role}:${employee}`;
  const cached = savedAuth.get(key);
  if (cached) {
    await page.context().clearCookies();
    await page.context().addCookies(JSON.parse(cached));
    await page.goto('/workspace');
    await expect(page.locator('.workspace-content')).toBeVisible();
    return;
  }
  await page.context().clearCookies();
  await page.goto(`/signin/${role}`);
  if (role !== "organization")
    await page
      .getByLabel("Organization ID", { exact: true })
      .fill(seed.organizationId);
  if (role === "worker") {
    await page.getByLabel("Employee ID", { exact: true }).fill(employee);
    await page.getByLabel("6-digit PIN", { exact: true }).fill(PIN);
  } else {
    await page
      .getByLabel(
        role === "organization"
          ? "Official organization email"
          : "Email address",
        { exact: true },
      )
      .fill(role === "organization" ? adminEmail : supervisorEmail);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  }
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await expect(page.locator(".workspace-content")).toBeVisible();
  savedAuth.set(key, JSON.stringify(await page.context().cookies()));
}

test.beforeAll(async () => {
  const context = await createRequest.newContext();
  await send(context, "/auth/register", {
    fullName: "QA Administrator",
    organizationName: "QA Contradiction Lab",
    organizationType: "manufacturing",
    email: adminEmail,
    password: PASSWORD,
  });
  const verified = await send(context, "/auth/verify", {
    token: deliveryToken(adminEmail),
  });
  await send(context, "/auth/login/organization", {
    email: adminEmail,
    password: PASSWORD,
  });
  await send(
    context,
    "/organization",
    {
      name: "QA Contradiction Lab",
      industry: "manufacturing",
      contact_email: adminEmail,
      timezone: "Asia/Kolkata",
    },
    "put",
  );
  const department = await send(context, "/departments", {
    name: "Production",
    description: "Browser-test department",
  });
  const team = await send(context, "/teams", {
    name: "Packing line",
    department_id: department.id,
  });
  const shift = await send(context, "/shifts", {
    name: "Day shift",
    starts_at: "06:00",
    ends_at: "14:00",
    days: [0, 1, 2, 3, 4, 5, 6],
  });
  const supervisor = await send(context, "/supervisors/invite", {
    name: "QA Supervisor",
    email: supervisorEmail,
    departments: [
      {
        department_id: department.id,
        primary: true,
        permissions: [
          "view",
          "manage",
          "review",
          "publish",
          "workforce",
          "evidence",
        ],
      },
    ],
  });
  await send(context, "/auth/activate", {
    token: deliveryToken(supervisorEmail),
    password: PASSWORD,
    confirm: PASSWORD,
  });
  await send(context, "/organization/activate", {});
  const workers = [];
  for (let index = 1; index <= 2; index++) {
    const worker = await send(context, "/workers", {
      name: `QA Worker ${index}`,
      employee_code: `QA-0${index}`,
      department_ids: [department.id],
      primary_department_id: department.id,
      team_ids: [team.id],
      shift_id: shift.id,
      skills: ["packing"],
    });
    await send(context, "/auth/activate", {
      token: new URL(worker.activation_url).searchParams.get("token"),
      pin: PIN,
      confirm: PIN,
    });
    workers.push(worker);
  }
  await send(context, "/auth/login/supervisor", {
    email: supervisorEmail,
    password: PASSWORD,
    organizationId: verified.organizationId,
  });
  const task = await send(context, "/tasks", {
    title: "Verify the packing line",
    description: "Inspect the sealed batch before release.",
    instructions: "Keep inspection pending until the reviewer confirms.",
    department_id: department.id,
    worker_id: workers[0].id,
    critical: true,
    priority: "critical",
    required_skills: ["packing"],
    deadline: new Date(Date.now() + 3600000).toISOString(),
  });
  seed = {
    organizationId: verified.organizationId,
    departmentId: department.id,
    shiftId: shift.id,
    teamId: team.id,
    workerId: workers[0].id,
    worker2Id: workers[1].id,
    supervisorId: supervisor.id,
    taskId: task.id,
  };
  await context.dispose();
});


type Claim = { text: string; fields: Record<string, string | number | null | string[]> };
type Scenario = { id: string; title: string; a: Claim; b: Claim; expected: string[]; different_shifts?: boolean; offset_seconds?: number };
const cases: Scenario[] = JSON.parse(execFileSync(process.execPath, ['-e', 'process.stdout.write(require("fs").readFileSync("fixtures/contradiction-cases.json","utf8"))'], {encoding:'utf8'}));

const labels: Record<string, string> = {
  category: 'Category', machine: 'Machine / equipment', batch: 'Batch ID', order: 'Order ID',
  task_reference: 'Task ID / name', product: 'Product', work_area: 'Work area',
  quantity: 'Quantity', unit: 'Unit', operational_status: 'Operational status',
  reference_period: 'Reporting period', observation_time: 'Observation time in source',
  quantity_basis: 'Counting basis', quality_status: 'Quality status', dispatch_status: 'Dispatch status',
  machine_status: 'Machine status', task_status: 'Task status',
};
const selects = new Set(['category', 'quantity_basis', 'quality_status', 'dispatch_status', 'machine_status', 'task_status']);

for (const scenario of cases) {
  test(`${scenario.id}: ${scenario.title} through Chrome and API`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    const reportIds: string[] = [];
    for (const [index, key] of ['a', 'b'].entries()) {
      await login(page, 'worker', index === 0 ? 'QA-01' : 'QA-02');
      const claim = scenario[key as 'a' | 'b'];
      const fields = { ...claim.fields, product: `${scenario.id}: ${claim.fields.product || 'QA product'}` };
      if (scenario.id.startsWith('TC-')) {
        await page.goto('/workspace/record');
        await page.getByLabel('Your update — type or correct the transcript').fill(claim.text);
        const details = page.locator('details.report-details');
        if ((await details.getAttribute('open')) === null) await details.locator('summary').click();
        for (const [field, value] of Object.entries(fields)) {
          if (!labels[field] || value === null || Array.isArray(value)) continue;
          const input = page.getByLabel(labels[field], { exact: true });
          if (selects.has(field)) await page.getByRole('combobox', {name: labels[field], exact:true}).selectOption(String(value));
          else await input.fill(String(value));
        }
        await page.getByLabel('I reviewed this report and any uncertainty is stated clearly.').check();
        const response = page.waitForResponse(response => response.url().endsWith('/api/v1/reports') && response.request().method() === 'POST');
        await page.getByRole('button', { name: 'Confirm and send', exact: true }).click();
        const result = await response;
        expect(result.status(), await result.text()).toBe(201);
        reportIds.push((await result.json()).report.id);
        await expect(page).toHaveURL(/\/workspace\/reports\//);
      } else {
        const body = {
          client_request_id: crypto.randomUUID(), department_id: seed.departmentId,
          shift_id: scenario.different_shifts && index === 1 ? null : seed.shiftId,
          occurred_at: new Date(Date.now() - 26 * 3600_000 + (index ? (scenario.offset_seconds || 0) * 1000 : 0)).toISOString(),
          text: claim.text, fields, confirmed: true,
        };
        const result = await send(page.request, '/reports', body);
        reportIds.push(result.report.id);
        const retry = await send(page.request, '/reports', body);
        expect(retry.report.id).toBe(result.report.id);
      }
    }
    await login(page, 'supervisor');
    const report = await (await page.request.get(`${API}/reports/${reportIds[1]}`)).json();
    expect(report.conflict_ids.length).toBe(scenario.expected.length ? 1 : 0);
    if (scenario.expected.length) {
      const detail = await (await page.request.get(`${API}/conflicts/${report.conflict_ids[0]}`)).json();
      expect(detail.findings.map((item: {category: string}) => item.category)).toEqual(scenario.expected);
      expect(detail.reports.map((item: {id: string}) => item.id).sort()).toEqual([...reportIds].sort());
      await page.goto(`/workspace/conflicts/${detail.id}`);
      await expect(page.locator('.report-original').filter({hasText: scenario.a.text})).toBeVisible();
      await expect(page.locator('.report-original').filter({hasText: scenario.b.text})).toBeVisible();
      if (scenario.id.startsWith('TC-')) {
        for (const width of [320, 390, 768, 1600]) {
          await page.setViewportSize({width, height: 1000});
          await checkWorkspaceLayout(page, scenario.id, width);
        }
        await page.screenshot({path:testInfo.outputPath(`${scenario.id}-evidence.png`), fullPage:true});
        await page.getByRole('button', {name:'Record supervisor resolution',exact:true}).click();
        await page.getByRole('dialog').getByRole('textbox', {name: /^Resolution/}).fill('QA verification: compared both original sources against the production register and inspection evidence.');
        await page.getByRole('dialog').getByRole('button',{name:'Save changes',exact:true}).click();
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(page.getByText('resolved',{exact:true}).first()).toBeVisible();
        await page.reload();
        await expect(page.locator('.report-original').filter({hasText: scenario.a.text})).toBeVisible();
        await expect(page.locator('.report-original').filter({hasText: scenario.b.text})).toBeVisible();
      }
    }
    expect(errors).toEqual([]);
  });
}
