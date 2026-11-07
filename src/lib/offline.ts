import { openDB, type DBSchema } from "idb";
import { api, ApiError } from "./api";
import type { Asset, Report, ReportPayload, Session } from "./types";

export type DraftStatus =
  | "Draft"
  | "Saved locally"
  | "Pending sync"
  | "Syncing"
  | "Submitted"
  | "Sync failed";
export type LocalAttachment = {
  name: string;
  mime: string;
  kind: string;
  data: string;
  consent: boolean;
  uploadedId?: string;
};
export type LocalDraft = {
  id: string;
  status: DraftStatus;
  updatedAt: string;
  payload: ReportPayload;
  attachments: LocalAttachment[];
  error?: string;
  reportId?: string;
  pendingAnswer?: string;
  pendingVoiceAnswer?: LocalAttachment;
  clarificationId?: string;
  sourceReportId?: string;
  requiresReview?: boolean;
};
type Envelope = {
  id: string;
  scope: string;
  iv: Uint8Array;
  encrypted: ArrayBuffer;
};
interface DraftDB extends DBSchema {
  drafts: { key: string; value: Envelope; indexes: { scope: string } };
}
const db = () =>
  openDB<DraftDB>("shiftproof-private-drafts", 1, {
    upgrade(database) {
      const drafts = database.createObjectStore("drafts", { keyPath: "id" });
      drafts.createIndex("scope", "scope");
    },
  });
const scope = (session: Session) =>
  `${session.organization.id}:${session.user.id}`;
async function key(session: Session) {
  const raw = Uint8Array.from(session.offlineKey.match(/.{2}/g) || [], (byte) =>
    parseInt(byte, 16),
  );
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, [
    "encrypt",
    "decrypt",
  ]);
}
export async function saveDraft(session: Session, draft: LocalDraft) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv,
      additionalData: new TextEncoder().encode(scope(session)),
    },
    await key(session),
    new TextEncoder().encode(JSON.stringify(draft)),
  );
  await (
    await db()
  ).put("drafts", {
    id: `${scope(session)}:${draft.id}`,
    scope: scope(session),
    iv,
    encrypted,
  });
  window.dispatchEvent(new Event("shiftproof-drafts-updated"));
}
export async function loadDrafts(session: Session): Promise<LocalDraft[]> {
  const entries = await (
    await db()
  ).getAllFromIndex("drafts", "scope", scope(session));
  const result: LocalDraft[] = [];
  for (const entry of entries) {
    const decrypted = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: new Uint8Array(entry.iv),
        additionalData: new TextEncoder().encode(scope(session)),
      },
      await key(session),
      entry.encrypted,
    );
    result.push(JSON.parse(new TextDecoder().decode(decrypted)));
  }
  return result.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}
export async function deleteDraft(session: Session, id: string) {
  await (await db()).delete("drafts", `${scope(session)}:${id}`);
  window.dispatchEvent(new Event("shiftproof-drafts-updated"));
}
export async function fileAttachment(
  file: Blob,
  name: string,
  kind: string,
  consent = false,
): Promise<LocalAttachment> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 8192)
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  return { name, mime: file.type, kind, data: btoa(binary), consent };
}
export function attachmentBlob(file: LocalAttachment) {
  return new Blob(
    [Uint8Array.from(atob(file.data), (char) => char.charCodeAt(0))],
    { type: file.mime },
  );
}
export async function uploadAttachment(
  file: LocalAttachment,
  departmentId: string,
  expectedAccount?: string,
) {
  const body = new FormData();
  body.set("file", attachmentBlob(file), file.name);
  body.set("kind", file.kind);
  body.set("department_id", departmentId);
  body.set("consent", String(file.consent));
  return api<Asset>("/files", {
    method: "POST",
    body,
    headers: expectedAccount ? { "X-Account-ID": expectedAccount } : undefined,
  });
}
let syncing = false;
export async function syncDrafts(session: Session, isCurrent: () => boolean) {
  if (navigator.locks)
    return navigator.locks.request(
      `shiftproof-sync:${scope(session)}`,
      { ifAvailable: true },
      (lock) => (lock ? runSync(session, isCurrent) : Promise.resolve()),
    );
  return runSync(session, isCurrent);
}
async function runSync(session: Session, isCurrent: () => boolean) {
  if (syncing || !navigator.onLine) return;
  syncing = true;
  try {
    for (const draft of await loadDrafts(session)) {
      if (!isCurrent()) break;
      if (draft.clarificationId) continue;
      if (!["Pending sync", "Sync failed", "Syncing"].includes(draft.status))
        continue;
      try {
        draft.status = "Syncing";
        draft.error = "";
        await saveDraft(session, draft);
        for (const attachment of draft.attachments) {
          if (!isCurrent())
            throw new Error(
              "Sign in as the original reporter to finish syncing.",
            );
          if (!attachment.uploadedId) {
            attachment.uploadedId = (
              await uploadAttachment(
                attachment,
                draft.payload.department_id,
                session.user.id,
              )
            ).id;
            await saveDraft(session, draft);
          }
        }
        if (!isCurrent())
          throw new Error(
            "Sign in as the original reporter to finish syncing.",
          );
        draft.payload.evidence_ids = [
          ...new Set([
            ...draft.payload.evidence_ids,
            ...draft.attachments.map((a) => a.uploadedId!).filter(Boolean),
          ]),
        ];
        await saveDraft(session, draft);
        if (!isCurrent())
          throw new Error(
            "Sign in as the original reporter to finish syncing.",
          );
        const result = await api<{ status: string; report: Report }>(
          "/reports",
          {
            method: "POST",
            body: JSON.stringify(draft.payload),
            headers: { "X-Account-ID": session.user.id },
          },
        );
        draft.status = "Submitted";
        draft.reportId = result.report.id;
        // Remove local sensitive content after server confirmation; keep only the receipt.
        draft.attachments = [];
        draft.payload.text = "";
        draft.payload.fields = {
          category: draft.payload.fields.category,
          description: "",
        };
      } catch (error) {
        draft.requiresReview =
          error instanceof ApiError &&
          error.status === 409 &&
          !!draft.payload.conversation_id;
        draft.status = draft.requiresReview ? "Saved locally" : "Sync failed";
        draft.error =
          error instanceof Error
            ? error.message
            : "Synchronization failed. Try again.";
      }
      draft.updatedAt = new Date().toISOString();
      await saveDraft(session, draft);
    }
  } finally {
    syncing = false;
  }
}
