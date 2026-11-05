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
const adminEmail = `qa-admin-${process.pid}@example.com`;
const supervisorEmail = `qa-supervisor-${process.pid}@example.com`;
const API = "http://127.0.0.1:8001/api/v1";
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
  await page.evaluate(() => new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  }));
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
          ) return false;
          parent = parent.parentElement;
        }
        return (
          box.left < -1 || box.right > innerWidth + 1 ||
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
    width <= 600 ? 16 : width <= 1000 ? 24
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
    { encoding: "utf8", cwd: path.resolve("backend"), env: { ...process.env, PYTHONPATH: "." } },
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
async function login(
  page: Page,
  role: "organization" | "supervisor" | "worker",
  employee = "QA-01",
) {
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
}

test.beforeAll(async () => {
  const context = await createRequest.newContext();
  await send(context, "/auth/register", {
    fullName: "QA Administrator",
    organizationName: "QA Manufacturing",
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
      name: "QA Manufacturing",
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

test("worker completes critical work and supervisor verifies it through the real API", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page, "worker");
  await page.screenshot({
    path: testInfo.outputPath("worker-desktop.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator(".theme-menu, #theme-options")).toHaveCount(0);
  await page.goto(`/workspace/tasks/${seed.taskId}`);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await page.getByRole("button", { name: "Complete", exact: true }).click();
  await expect(
    page.locator(".work-tags").first().getByText("completed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Verify", exact: true }),
  ).toHaveCount(0);
  await login(page, "supervisor");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.goto(`/workspace/tasks/${seed.taskId}`);
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Reason")
    .fill("Packing inspection complete; evidence reviewed against the batch.");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.locator(".work-tags").first().getByText("verified", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(
    page.locator(".work-tags").first().getByText("closed", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("offline report sync is server confirmed and local drafts are encrypted and account isolated", async ({
  page,
  context,
}, testInfo) => {
  await login(page, "worker");
  await page.goto("/workspace/record");
  const update =
    "Offline browser test: packing complete; inspection remains pending.";
  await page
    .getByLabel("Your update — type or correct the transcript")
    .fill(update);
  await page
    .getByLabel("I reviewed this report and any uncertainty is stated clearly.")
    .check();
  await context.setOffline(true);
  await page
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(page.getByText("Pending sync", { exact: true })).toBeVisible();
  await page
    .getByRole("link", { name: "Local drafts", exact: true })
    .first()
    .click();
  await expect(page.getByText(update)).toBeVisible();
  const raw = await page.evaluate(
    async () =>
      new Promise<string>((resolve, reject) => {
        const request = indexedDB.open("shiftproof-private-drafts");
        request.onsuccess = () => {
          const all = request.result
            .transaction("drafts")
            .objectStore("drafts")
            .getAll();
          all.onsuccess = () => resolve(JSON.stringify(all.result));
          all.onerror = reject;
        };
        request.onerror = reject;
      }),
  );
  expect(raw).not.toContain(update);
  await context.setOffline(false);
  await expect(page.getByText("Submitted", { exact: true })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("link", { name: "Read report" }).click();
  await expect(page.locator(".report-original")).toHaveText(update);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".workspace-nav")).toBeHidden();
  const navigation = page.getByRole("button", {
    name: "Open workspace navigation",
    exact: true,
  });
  await navigation.click();
  await expect(page.locator(".workspace-nav")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".workspace-nav")).toBeHidden();
  await expect(navigation).toBeFocused();
  await page.screenshot({
    path: testInfo.outputPath("worker-report-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/workspace/record");
  await page
    .getByLabel("Your update — type or correct the transcript")
    .fill("Private unfinished draft belonging to worker one.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Draft saved on this device.", { exact: true }),
  ).toBeVisible();
  await login(page, "worker", "QA-02");
  await page.goto("/workspace/drafts");
  await expect(page.getByText("No records yet")).toBeVisible();
  await expect(
    page.getByText("Private unfinished draft belonging to worker one."),
  ).toHaveCount(0);
});

test("admin and supervisor routes remain usable across target widths, themes and Hindi", async ({
  page,
}, testInfo) => {
  test.setTimeout(600_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page, "organization");
  const routes = [
    "",
    "/onboarding",
    "/departments",
    "/workforce",
    "/shifts",
    "/supervisors",
    "/policies",
    "/analytics",
    "/audit",
    "/settings",
    "/notifications",
    "/attention",
    "/tasks",
    "/reports",
    "/handovers",
    "/alerts",
    "/conflicts",
    "/follow-ups",
    `/departments/${seed.departmentId}`,
    `/teams/${seed.teamId}`,
    `/supervisors/${seed.supervisorId}`,
  ];
  for (const appearance of appearances) {
    await setAppearance(page, appearance);
    for (const route of routes) {
      await page.goto(`/workspace${route}`);
      if (route === "/settings") {
        await expect(page.getByRole("combobox", { name: /^(Appearance|दिखावट)$/ })).toHaveCount(0);
      }
      for (const width of layoutWidths) {
        await page.setViewportSize({ width, height: 1000 });
        await checkWorkspaceLayout(
          page, `${route}, ${appearance.language}, ${width}px`, width,
        );
      }
    }
  }
  await setAppearance(page);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/workspace");
  await expect(
    page.getByText("Active departments", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("admin-desktop.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/workspace/analytics");
  await page.screenshot({
    path: testInfo.outputPath("analytics-desktop.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Switch to Hindi" }).click();
  await page.getByRole("button", { name: "हल्की थीम पर जाएँ" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({
    path: testInfo.outputPath("analytics-mobile-hindi-light.png"),
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("immediate report keeps one alert and published handover has separate receipts", async ({
  page,
}, testInfo) => {
  await login(page, "worker");
  await page.goto("/workspace/record");
  await page
    .getByLabel("Your update — type or correct the transcript")
    .fill("Safety check: stop the packing line until inspection is complete.");
  await page.getByLabel("This is an immediate safety concern").check();
  await page.getByRole("button", { name: "Alert supervisor now" }).click();
  await expect(
    page.getByText(
      "Supervisor alerted. This report will stay linked to that alert.",
    ),
  ).toBeVisible();
  await page
    .getByLabel("I reviewed this report and any uncertainty is stated clearly.")
    .check();
  await page
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(page).toHaveURL(/\/workspace\/reports\//);
  await login(page, "supervisor");
  await page.goto("/workspace/alerts");
  await expect(
    page
      .locator(".work-list-row")
      .filter({ hasText: "Safety check: stop the packing line" }),
  ).toHaveCount(1);
  await page.goto("/workspace/attention");
  await expect(
    page.getByText("Immediate safety concern", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("supervisor-attention-desktop.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/workspace/handovers");
  await page
    .getByRole("button", { name: "Create handover", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Department", { exact: false })
    .selectOption(seed.departmentId);
  await dialog
    .getByLabel("Shift *", { exact: true })
    .selectOption(seed.shiftId);
  await dialog
    .getByLabel("Notes", { exact: true })
    .fill("Packing line inspection remains open. Incoming shift must review.");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  await page
    .locator(".work-list-row")
    .filter({ hasText: "Production" })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Publish version", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(
    page.getByText("published", { exact: true }).first(),
  ).toBeVisible();
  const handoverPath = new URL(page.url()).pathname;
  await login(page, "worker");
  await page.goto(handoverPath);
  await page
    .getByRole("button", { name: "Confirm receipt", exact: true })
    .click();
  await expect(
    page.getByText("Receipt confirmed", { exact: false }),
  ).toBeVisible();
  const critical = page.getByRole("button", {
    name: "Acknowledge this item",
    exact: true,
  });
  expect(await critical.count()).toBeGreaterThan(0);
  while (await critical.count()) {
    const count = await critical.count();
    await critical.first().click();
    await expect(critical).toHaveCount(count - 1);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("handover-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
});

test("production shell works offline without caching account data or unlocking a session", async ({
  page,
  context,
}) => {
  test.skip(
    process.env.SHIFTPROOF_BUILD_TEST !== "1",
    "Service worker is enabled in production builds only.",
  );
  await page.goto("/signin");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true);
  const cached = await page.evaluate(async () => {
    const keys = await caches.keys();
    const urls: string[] = [];
    for (const key of keys) {
      for (const request of await (await caches.open(key)).keys())
        urls.push(new URL(request.url).pathname);
    }
    return urls;
  });
  expect(cached).toContain("/");
  expect(cached.some((path) => path.startsWith("/assets/"))).toBe(true);
  expect(
    cached.every(
      (path) =>
        path === "/" || path === "/favicon.svg" || path.startsWith("/assets/"),
    ),
  ).toBe(true);
  await context.setOffline(true);
  await page.goto("/signin/worker");
  await expect(page.getByLabel("Employee ID", { exact: true })).toBeVisible();
  await page.goto("/workspace/record");
  await expect(
    page.getByRole("heading", { name: "Your workspace is private." }),
  ).toBeVisible();
  await expect(page.locator(".workspace-content")).toHaveCount(0);
});

test("operational detail pages and task views fit every target width for both roles", async ({
  page,
}, testInfo) => {
  test.setTimeout(900_000);
  const context = await createRequest.newContext();
  await send(context, "/auth/login/worker", {
    organizationId: seed.organizationId,
    employeeId: "QA-01",
    pin: PIN,
  });
  const first = await send(context, "/reports", {
    client_request_id: crypto.randomUUID(),
    department_id: seed.departmentId,
    occurred_at: new Date().toISOString(),
    text: "Inspection pending for batch RESP-1. Count 40.",
    fields: {
      category: "quality",
      description: "Inspection is pending",
      batch: "RESP-1",
      machine: "M-RESP",
      quantity: 40,
    },
    confirmed: true,
  });
  const immediate = await send(context, "/alerts/immediate", {
    department_id: seed.departmentId,
    title: "Responsive review safety concern",
    client_request_id: crypto.randomUUID(),
  });
  await send(context, "/auth/login/worker", {
    organizationId: seed.organizationId,
    employeeId: "QA-02",
    pin: PIN,
  });
  await send(context, "/reports", {
    client_request_id: crypto.randomUUID(),
    department_id: seed.departmentId,
    occurred_at: new Date().toISOString(),
    text: "Inspection pending for batch RESP-1. Count 42.",
    fields: {
      category: "quality",
      description: "Inspection is pending",
      batch: "RESP-1",
      machine: "M-RESP",
      quantity: 42,
    },
    confirmed: true,
  });
  await send(context, "/auth/login/supervisor", {
    organizationId: seed.organizationId,
    email: supervisorEmail,
    password: PASSWORD,
  });
  const conflicts = await (await context.get(`${API}/conflicts`)).json();
  expect(conflicts.length).toBeGreaterThan(0);
  const handovers = await (await context.get(`${API}/handovers`)).json();
  const handover =
    handovers[0] ||
    (await send(context, "/handovers", {
      department_id: seed.departmentId,
      shift_id: seed.shiftId,
      shift_date: new Date().toISOString().slice(0, 10),
      notes: "Review inspection before release.",
    }));
  if (!handover.latest_version)
    await send(context, `/handovers/${handover.id}/publish`, {
      version: handover.version,
      changes: "Publish the inspection context",
      notes: "Review inspection before release.",
    });
  await context.dispose();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const role of ["supervisor", "worker"] as const) {
    await login(page, role);
    const routes = [
      "",
      "/tasks",
      `/tasks/${seed.taskId}`,
      "/record",
      "/drafts",
      "/reports",
      `/reports/${first.report.id}`,
      "/alerts",
      `/alerts/${immediate.id}`,
      "/handovers",
      `/handovers/${handover.id}`,
      "/notifications",
      "/settings",
      ...(role === "supervisor"
        ? [
            "/conflicts",
            `/conflicts/${conflicts[0].id}`,
            "/follow-ups",
            "/workforce",
            "/shifts",
            "/analytics",
            "/attention",
            `/departments/${seed.departmentId}`,
            `/teams/${seed.teamId}`,
            `/workforce/${seed.workerId}`,
          ]
        : []),
    ];
    for (const appearance of appearances) {
      await setAppearance(page, appearance);
      for (const route of routes) {
        await page.goto(`/workspace${route}`);
        for (const width of layoutWidths) {
          await page.setViewportSize({ width, height: 1000 });
          await checkWorkspaceLayout(
            page, `${role} ${route}, ${appearance.language}, ${width}px`, width,
          );
          if (role === "supervisor" && appearance.language === "en" && width === 320
            && ["/attention", "/notifications"].includes(route)) {
            await page.screenshot({
              path: testInfo.outputPath(`supervisor-${route.slice(1)}-mobile.png`),
              fullPage: true,
              animations: "disabled",
            });
          }
        }
      }
    }
    await setAppearance(page);
    if (role === "supervisor") {
      await page.setViewportSize({ width: 320, height: 900 });
      await page.goto("/workspace/tasks");
      for (const name of ["View board", "View calendar"]) {
        await page.getByRole("button", { name, exact: true }).click();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
        ).toBeTruthy();
      }
      await page
        .getByRole("button", { name: "Create task", exact: true })
        .click();
      await expect(page.getByRole("dialog")).toBeVisible();
      expect(
        await page
          .getByRole("dialog")
          .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
      ).toBeTruthy();
      await page.screenshot({
        path: testInfo.outputPath("task-form-mobile.png"),
        fullPage: true,
        animations: "disabled",
      });
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "Close", exact: true })
        .click();
    }
  }
  expect(errors).toEqual([]);
});
