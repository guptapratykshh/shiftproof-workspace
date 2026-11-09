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
const API = "http://127.0.0.1:8013/api/v1";
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
  receivingId: string;
  sourceReportId: string;
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
  const receiving = await send(context, "/departments", {
    name: "Receiving",
    description: "Transfer receiving",
  });
  await send(context, "/department-links", {
    source_department_id: department.id,
    receiving_department_id: receiving.id,
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
        department_id: receiving.id,
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
  for (let index = 1; index <= 3; index++) {
    const worker = await send(context, "/workers", {
      name: `QA Worker ${index}`,
      employee_code: `QA-0${index}`,
      department_ids: [index === 2 ? receiving.id : department.id],
      primary_department_id: index === 2 ? receiving.id : department.id,
      team_ids: index === 1 ? [team.id] : [],
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
  await send(context, "/auth/login/worker", {
    organizationId: verified.organizationId,
    employeeId: "QA-01",
    pin: PIN,
  });
  const source = await send(context, "/reports", {
    client_request_id: crypto.randomUUID(),
    department_id: department.id,
    shift_id: shift.id,
    occurred_at: new Date().toISOString(),
    confirmed: true,
    text: "Manufactured 100 pieces for Batch B12, transfer MOVE-1.",
    fields: {
      category: "progress",
      description: "Manufactured 100 pieces.",
      batch: "B12",
      quantity: 100,
      unit: "pieces",
      quantity_stage: "manufactured",
      transfer_reference: "MOVE-1",
    },
  });
  seed = {
    receivingId: receiving.id,
    sourceReportId: source.report.id,
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

async function fakeRecorder(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }),
      },
    });
    class Recorder {
      static isTypeSupported() {
        return true;
      }
      state = "inactive";
      mimeType = "audio/wav";
      ondataavailable: ((value: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        this.ondataavailable?.({
          data: new Blob(
            [
              (() => {
                const data = new ArrayBuffer(3244);
                const view = new DataView(data);
                const put = (offset: number, text: string) =>
                  [...text].forEach((c, i) =>
                    view.setUint8(offset + i, c.charCodeAt(0)),
                  );
                put(0, "RIFF");
                view.setUint32(4, 3236, true);
                put(8, "WAVEfmt ");
                view.setUint32(16, 16, true);
                view.setUint16(20, 1, true);
                view.setUint16(22, 1, true);
                view.setUint32(24, 16000, true);
                view.setUint32(28, 32000, true);
                view.setUint16(32, 2, true);
                view.setUint16(34, 16, true);
                put(36, "data");
                view.setUint32(40, 3200, true);
                return data;
              })(),
            ],
            { type: "audio/wav" },
          ),
        });
        this.onstop?.();
      }
    }
    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      value: Recorder,
    });
  });
}

test("recording asks about 100 versus 85 aloud, accepts a voice reply, and routes verification", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await fakeRecorder(page);
  await page.addInitScript(() => {
    Object.defineProperty(window, "voicePlayAttempts", {
      value: 0,
      writable: true,
    });
    HTMLMediaElement.prototype.play = function () {
      const state = window as unknown as { voicePlayAttempts: number };
      state.voicePlayAttempts++;
      return Promise.reject(
        new DOMException("Playback needs a tap", "NotAllowedError"),
      );
    };
  });
  await login(page, "worker", "QA-02");
  await page.goto("/workspace/record");
  await page
    .getByLabel(
      "I consent to recording and authorized review under my organization’s retention policy.",
    )
    .check();
  await page
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Cancel recording", exact: true })
    .click();
  await expect(
    page.getByText("Recording cancelled. Your previous update is unchanged."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  const question = page.locator(".conversation-question");
  await expect(question).toContainText("100");
  await expect(question).toContainText("85");
  await expect(question).toContainText("15");
  await expect(
    page.getByRole("button", { name: "Check recording again", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Tap to hear the question" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { voicePlayAttempts: number }).voicePlayAttempts,
    ),
  ).toBeGreaterThan(0);
  await expect(
    page.getByRole("button", { name: "Confirm and send", exact: true }),
  ).toBeDisabled();
  await page.screenshot({
    path: testInfo.outputPath("conversation-question-desktop.png"),
    fullPage: true,
  });
  for (const width of [320, 390, 768, 1470]) {
    await page.setViewportSize({ width, height: 1000 });
    await checkWorkspaceLayout(page, "conversation " + width, width);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".report-conversation").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath("conversation-question-mobile.png"),
    fullPage: false,
  });
  await page
    .getByRole("button", { name: "Switch to Hindi", exact: true })
    .click();
  await page
    .getByRole("button", { name: "गहरी थीम पर जाएँ", exact: true })
    .click();
  await page.locator(".report-conversation").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath("conversation-hindi-dark-mobile.png"),
    fullPage: false,
  });
  await page
    .getByRole("button", { name: "Switch to English", exact: true })
    .click();
  await page.getByRole("button", { name: "Reply", exact: true }).click();
  await page.getByRole("button", { name: /Stop reply/ }).click();
  await expect(
    page.getByText("Ready for your review", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".conversation-summary")).toContainText(
    "Yes, confirmed",
  );
  await page
    .getByLabel("I reviewed this report and any uncertainty is stated clearly.")
    .check();
  await page
    .getByRole("button", { name: "Confirm and send", exact: true })
    .click();
  await expect(page).toHaveURL(/\/workspace\/reports\//);
  const receivedId = page.url().split("/").at(-1)!;
  await expect(
    page.getByText("Questions and worker answers", { exact: true }),
  ).toBeVisible();

  await login(page, "worker", "QA-01");
  await page.goto(`/workspace/reports/${seed.sourceReportId}`);
  await page.getByRole("button", { name: "Respond", exact: true }).click();
  await page.getByRole("button", { name: "Type answer", exact: true }).click();
  await page.getByLabel("Your answer", { exact: true }).fill("yes");
  await page
    .getByRole("button", { name: "Check my answer", exact: true })
    .click();
  await page.getByLabel("I reviewed my answer.").check();
  await page
    .getByRole("button", { name: "Confirm and send answer", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Respond", exact: true }),
  ).toHaveCount(0);

  await login(page, "supervisor");
  const state = await page.context().request.get(`${API}/conflicts`);
  const conflicts = await state.json();
  expect(conflicts).toHaveLength(1);
  await page.goto(`/workspace/conflicts/${conflicts[0].id}`);
  await expect(
    page.getByText("Transfer difference", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Record supervisor resolution" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("textbox", { name: "Resolution", exact: true })
    .fill(
      "Counted the transfer and checked both workers’ original observations; 15 pieces remain at production.",
    );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(
    page.getByRole("button", { name: "Record supervisor resolution" }),
  ).toHaveCount(0);
  const preserved = await (
    await page.context().request.get(`${API}/reports/${receivedId}`)
  ).json();
  expect(preserved.versions[0].fields.quantity).toBe(85);
  expect(errors).toEqual([]);
});

test("an edited update invalidates voice results and microphone denial leaves typing available", async ({
  page,
}) => {
  await login(page, "worker", "QA-02");
  await page.goto("/workspace/record");
  const text = page.getByLabel("Type or edit your update");
  await text.fill("I received 85 pieces for Batch B12, transfer MOVE-1.");
  await page.getByRole("button", { name: "Check update", exact: true }).click();
  await expect(page.locator(".conversation-question")).toContainText("100");
  await page.evaluate(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      configurable: true,
      value: async () => {
        throw new DOMException("Denied", "NotAllowedError");
      },
    });
  });
  await page
    .getByLabel("I consent to recording my answer for authorized review.")
    .check();
  await page.getByRole("button", { name: "Reply", exact: true }).click();
  await expect(
    page.getByText("Microphone permission was denied. Type your answer below."),
  ).toBeVisible();
  await page
    .getByLabel("Your answer", { exact: true })
    .fill("Correction, I received 100.");
  await page
    .getByRole("button", { name: "Check my answer", exact: true })
    .click();
  // The preceding scenario also left this worker's original 85-count report.
  await expect(page.locator(".conversation-question")).toContainText("100");
  await page.getByRole("button", { name: "Type answer", exact: true }).click();
  await page.getByLabel("Your answer", { exact: true }).fill("yes");
  await page
    .getByRole("button", { name: "Check my answer", exact: true })
    .click();
  await expect(
    page.getByText("Ready for your review", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("I reviewed this report and any uncertainty is stated clearly.")
    .check();
  await text.fill("Changed again: received 80 pieces.");
  await expect(
    page.getByRole("button", { name: "Confirm and send", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText(
      "Your update changed. Check the updated words before sending.",
    ),
  ).toBeVisible();
});

test("late processing never overwrites a worker correction", async ({
  page,
}) => {
  await login(page, "worker", "QA-02");
  let release = false;
  let readySeen = false;
  await page.route("**/api/v1/report-conversations/*", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const result = await response.json();
    if (
      result.revision > 0 &&
      ["awaiting_answer", "ready"].includes(result.status)
    ) {
      readySeen = true;
      if (!release) result.status = "processing";
    }
    await route.fulfill({ response, json: result });
  });
  await page.goto("/workspace/record");
  const words = page.getByLabel("Type or edit your update");
  await words.fill("I received 85 pieces for Batch B12, transfer MOVE-1.");
  await page.getByRole("button", { name: "Check update", exact: true }).click();
  await expect.poll(() => readySeen).toBe(true);
  await words.fill("Correction: I counted 100 pieces.");
  release = true;
  await expect(
    page.getByText(
      "Your update changed. Check the updated words before sending.",
    ),
  ).toBeVisible();
  await expect(words).toHaveValue("Correction: I counted 100 pieces.");
  await expect(
    page.getByRole("button", { name: "Confirm and send", exact: true }),
  ).toBeDisabled();
});

test("offline typed answers survive reopening an encrypted local draft", async ({
  page,
}) => {
  await login(page, "worker", "QA-02");
  await page.goto("/workspace/record");
  await page
    .getByLabel("Type or edit your update")
    .fill("I received 85 pieces for Batch B12, transfer MOVE-1.");
  await page.getByRole("button", { name: "Check update", exact: true }).click();
  await expect(page.locator(".conversation-question")).toContainText("100");
  await page.getByRole("button", { name: "Type answer", exact: true }).click();
  await page.context().setOffline(true);
  await page
    .getByLabel("Your answer", { exact: true })
    .fill("The remaining 15 are still in manufacturing.");
  await expect(
    page.getByRole("button", { name: "Check my answer", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Draft saved on this device.", { exact: true }),
  ).toBeVisible();
  await page.context().setOffline(false);
  await page.goto("/workspace/drafts");
  await page.getByRole("link", { name: "Continue", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(
    "The remaining 15 are still in manufacturing.",
  );
  await expect(
    page.getByRole("button", { name: "Confirm and send", exact: true }),
  ).toBeDisabled();
});

test("product counts ask about scope before sending a 75 versus 80 difference for review", async ({
  page,
}, testInfo) => {
  await login(page, "worker", "QA-01");
  await send(page.context().request, "/reports", {
    client_request_id: crypto.randomUUID(),
    department_id: seed.departmentId,
    shift_id: seed.shiftId,
    occurred_at: new Date().toISOString(),
    confirmed: true,
    text: "75 kitchen products packed and ready for dispatch.",
    fields: {
      category: "progress",
      product: "kitchen products",
      quantity: 75,
      unit: "items",
      quantity_stage: "packed",
      quantity_basis: "total",
      dispatch_status: "pending",
    },
  });
  await login(page, "worker", "QA-03");
  await page.goto("/workspace/record");
  await page
    .getByRole("combobox", { name: /Speech language/ })
    .selectOption("en-IN");
  await expect(
    page.getByText("Only submitted reports are compared.", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Type or edit your update")
    .fill("80 kitchen products packed and ready for dispatch.");
  await page.getByRole("button", { name: "Check update", exact: true }).click();
  await expect(page.locator(".conversation-question")).toContainText("75");
  await expect(page.locator(".conversation-question")).toContainText("80");
  await expect(page.locator(".conversation-question")).toContainText(
    "same work and reporting period",
  );
  await page.screenshot({
    path: testInfo.outputPath("product-count-question-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await checkWorkspaceLayout(page, "product count question", 390);
  await page.locator(".report-conversation").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath("product-count-question-mobile.png"),
    fullPage: false,
  });
  await page.getByRole("button", { name: "Type answer", exact: true }).click();
  await page.getByLabel("Your answer", { exact: true }).fill("yes");
  await page
    .getByRole("button", { name: "Check my answer", exact: true })
    .click();
  await expect(page.locator(".conversation-summary")).toContainText("80 items");
  await expect(page.locator(".conversation-summary")).toContainText("Packed");
  await expect(page.locator(".conversation-summary")).not.toContainText(
    "Manufactured",
  );
  await page
    .getByLabel("I reviewed this report and any uncertainty is stated clearly.")
    .check();
  await page
    .getByRole("button", { name: "Confirm and send", exact: true })
    .click();
  await expect(page).toHaveURL(/\/workspace\/reports\//);
  await login(page, "supervisor");
  const conflicts = await (
    await page.context().request.get(`${API}/conflicts`)
  ).json();
  const conflict = conflicts.find(
    (value: { title: string }) => value.title === "Possible count difference",
  );
  expect(conflict).toBeTruthy();
  await page.goto(`/workspace/conflicts/${conflict.id}`);
  await expect(
    page.getByText("Possible count difference", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".workspace-content")).toContainText("75");
  await expect(page.locator(".workspace-content")).toContainText("80");
});

test("handover listening recovers a missing generated file instead of repeating the failed download", async ({
  page,
}, testInfo) => {
  await login(page, "supervisor");
  const handover = await send(page.context().request, "/handovers", {
    department_id: seed.departmentId,
    shift_id: seed.shiftId,
    shift_date: new Date().toISOString().slice(0, 10),
  });
  await send(page.context().request, `/handovers/${handover.id}/publish`, {
    version: handover.version,
    notes: "Inspection remains pending. Do not release the batch.",
    changes: "Test handover",
  });
  let removed = false;
  await page.route("**/api/v1/files/*", async (route) => {
    if (!removed && route.request().method() === "GET") {
      const assetId = new URL(route.request().url()).pathname
        .split("/")
        .at(-1)!;
      // Remove only this generated fixture from the isolated browser database.
      execFileSync(path.resolve("backend/.venv/bin/python"), [
        "-c",
        `
import os,sqlite3,sys
from pathlib import Path
from urllib.parse import urlsplit
root=Path('/tmp/shiftproof-dialogue-qa')
uri=os.environ.get('SHIFTPROOF_BROWSER_DATABASE_URL', '')
if uri:
    import certifi
    from pymongo import MongoClient
    assert urlsplit(uri).path.startswith('/shiftproof_test_browser_')
    with MongoClient(uri, tlsCAFile=certifi.where()) as client:
        asset=client.get_default_database().file_assets.find_one({'_id': sys.argv[1]})
        row=(asset['storage_key'], asset['name']) if asset else None
else:
    with sqlite3.connect(root/'browser-tests.db') as db:
        row=db.execute('SELECT storage_key, name FROM file_assets WHERE id=?',(sys.argv[1],)).fetchone()
assert row and row[1]=='handover.wav'
file=(root/'evidence'/row[0]).resolve()
assert file.is_relative_to((root/'evidence').resolve())
file.unlink()
`,
        assetId,
      ]);
      removed = true;
    }
    await route.continue();
  });
  await page.goto(`/workspace/handovers/${handover.id}`);
  await page
    .getByRole("button", { name: "Listen to this version", exact: true })
    .click();
  await expect(
    page.getByText(
      "Evidence storage is temporarily unavailable. Try again later.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Try listening again", exact: true })
    .click();
  await expect(page.locator(".voice-playback audio")).toBeVisible();
  await expect(
    page.getByText(
      "Evidence storage is temporarily unavailable. Try again later.",
      { exact: true },
    ),
  ).toHaveCount(0);
  await expect
    .poll(() =>
      page
        .locator(".voice-playback audio")
        .evaluate((element) => (element as HTMLAudioElement).duration),
    )
    .toBeGreaterThan(0);
  await page.screenshot({
    path: testInfo.outputPath("handover-playback-recovered-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".voice-playback").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath("handover-playback-recovered-mobile.png"),
    fullPage: false,
  });
});
