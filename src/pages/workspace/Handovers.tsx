import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, Plus, ShieldAlert } from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import { VoicePlayback } from "../../components/workspace/VoicePlayback";
import {
  ActionButton,
  Empty,
  FieldsForm,
  Modal,
  PageTitle,
  Panel,
  Status,
  When,
  formatDate,
  nullable,
  options,
  useWords,
} from "../../components/workspace/UI";
import { api, post, put } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type { Handover } from "../../lib/types";

export function HandoversPage() {
  const { id } = useParams();
  const session = useSession((state) => state.session)!;
  const management = session.user.role !== "worker";
  const { departments, shifts, workers, supervisors } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [versionNumber, setVersionNumber] = useState<number | null>(null);
  const data = useQuery<Handover | Handover[]>({
    queryKey: ["handovers", id],
    queryFn: () =>
      id ? api<Handover>(`/handovers/${id}`) : api<Handover[]>("/handovers"),
  });
  const item = id ? (data.data as Handover | undefined) : undefined;
  const version =
    item?.versions?.find((v) => v.number === versionNumber) ||
    item?.versions?.[0];
  const previousVersion = item?.versions?.find(
    (v) => v.number === (version?.number || 0) - 1,
  );
  const differences: { title: string; change: string }[] = [];
  if (version && previousVersion) {
    const key = (entry: { source_type: string; source_id: string }) =>
      `${entry.source_type}:${entry.source_id}`;
    for (const entry of version.items) {
      const old = previousVersion.items.find(
        (other) => key(other) === key(entry),
      );
      if (!old)
        differences.push({
          title: entry.title,
          change: t("Added", "जोड़ा गया"),
        });
      else if (
        old.title !== entry.title ||
        old.critical !== entry.critical ||
        JSON.stringify(old.detail) !== JSON.stringify(entry.detail)
      )
        differences.push({
          title: entry.title,
          change: t("Updated", "बदला गया"),
        });
    }
    for (const old of previousVersion.items)
      if (!version.items.some((entry) => key(entry) === key(old)))
        differences.push({
          title: old.title,
          change: t(
            "Not included in this version; see previous snapshot",
            "इस संस्करण में शामिल नहीं; पिछला संस्करण देखें",
          ),
        });
    if (previousVersion.snapshot.notes !== version.snapshot.notes)
      differences.push({
        title: t("Shift notes", "शिफ्ट टिप्पणियाँ"),
        change: t("Updated", "बदला गया"),
      });
  }
  const receipt = version?.recipients.find(
    (r) => r.user_id === session.user.id,
  );
  const people = [...(workers.data?.items || []), ...(supervisors.data || [])];
  return (
    <>
      <PageTitle
        title="Handovers"
        description={t(
          "The work continues. Keep the next shift’s context complete.",
          "काम जारी रहता है। अगली शिफ्ट के लिए पूरा संदर्भ रखें।",
        )}
      >
        {management && !id && (
          <button
            className="button button-primary"
            onClick={() => setCreating(true)}
          >
            <Plus size={17} />
            {w("Create handover")}
          </button>
        )}
        {management && item && (
          <button
            className="button button-outline"
            onClick={() => setEditing(true)}
          >
            {t("Save draft notes", "ड्राफ्ट टिप्पणियाँ सहेजें")}
          </button>
        )}
        {management && item && (
          <button
            className="button button-primary"
            onClick={() => setPublishing(true)}
          >
            {w("Publish version")}
          </button>
        )}
      </PageTitle>
      <When loading={data.isLoading} error={data.error}>
        {item ? (
          <>
            <Panel>
              <div className="work-tags section-actions">
                <Status value={item.status} />
                <span>
                  {
                    departments.data?.find((d) => d.id === item.department_id)
                      ?.name
                  }
                </span>
                <span>
                  {
                    shifts.data?.find((shift) => shift.id === item.shift_id)
                      ?.name
                  }
                </span>
                <span>{item.shift_date}</span>
              </div>
              {version ? (
                <>
                  <label className="version-selector">
                    {t("Published version", "प्रकाशित संस्करण")}
                    <select
                      value={version.number}
                      onChange={(event) => {
                        setVersionNumber(Number(event.target.value));
                      }}
                    >
                      {item.versions?.map((v) => (
                        <option key={v.id} value={v.number}>
                          {v.number}{" "}
                          {v.number === item.latest_version
                            ? t("· latest", "· नवीनतम")
                            : ""}{" "}
                          ·{" "}
                          {formatDate(
                            v.created_at,
                            session.organization.timezone,
                          )}
                        </option>
                      ))}
                    </select>
                  </label>
                  {version.provisional && (
                    <div className="provisional-banner">
                      <ShieldAlert />
                      <div>
                        <strong>
                          {t(
                            "Pending Supervisor Review",
                            "पर्यवेक्षक की समीक्षा लंबित",
                          )}
                        </strong>
                        <p>
                          {t(
                            "Generated at shift end. This version has not been verified by a supervisor.",
                            "शिफ्ट समाप्त होने पर बनाया गया। इस संस्करण को पर्यवेक्षक ने सत्यापित नहीं किया है।",
                          )}
                        </p>
                      </div>
                    </div>
                  )}
                  <h2>{t("What changed", "क्या बदला")}</h2>
                  <p className="work-copy">{version.changes}</p>
                  {previousVersion && (
                    <details className="work-details">
                      <summary>
                        {t("Compare with version", "संस्करण से तुलना")}{" "}
                        {previousVersion.number}
                      </summary>
                      {differences.length ? (
                        differences.map((diff, index) => (
                          <p key={index}>
                            <strong>{diff.change}:</strong> {diff.title}
                          </p>
                        ))
                      ) : (
                        <p>
                          {t(
                            "No operational items or notes changed.",
                            "कार्य विवरण या टिप्पणियाँ नहीं बदली हैं।",
                          )}
                        </p>
                      )}
                    </details>
                  )}
                  <h2>{t("Shift notes", "शिफ्ट टिप्पणियाँ")}</h2>
                  <p className="work-copy">
                    {version.snapshot.notes ||
                      t(
                        "No additional notes.",
                        "अतिरिक्त टिप्पणियाँ नहीं हैं।",
                      )}
                  </p>
                  <div className="work-actions">
                    {receipt &&
                      (receipt.acknowledged_at ? (
                        <span className="work-success">
                          <CheckCircle2 size={18} />
                          {t("Receipt confirmed", "प्राप्ति की पुष्टि")} ·{" "}
                          {formatDate(
                            receipt.acknowledged_at,
                            session.organization.timezone,
                          )}
                        </span>
                      ) : (
                        <ActionButton
                          className="button button-primary"
                          action={() =>
                            post(`/handovers/${item.id}/acknowledge`, {
                              version_id: version.id,
                            })
                          }
                        >
                          {w("Confirm receipt")}
                        </ActionButton>
                      ))}
                    <VoicePlayback
                      key={`${version.id}:${session.user.preferences.speech_language}`}
                      endpoint={`/handover-audio/${version.id}`}
                      body={{
                        language:
                          session.user.preferences.speech_language === "en-IN"
                            ? "en-IN"
                            : "auto",
                      }}
                      label={t("Listen to this version", "यह संस्करण सुनें")}
                    />
                  </div>
                </>
              ) : (
                <>
                  <h2>
                    {t("Draft awaiting review", "समीक्षा के लिए ड्राफ्ट")}
                  </h2>
                  <p className="work-copy">{item.draft?.notes}</p>
                  <p>
                    {t(
                      "Review the sources below and publish when ready. Unresolved issues can remain open in the handover.",
                      "नीचे स्रोत जाँचें और तैयार होने पर प्रकाशित करें। अनसुलझे विषय हैंडओवर में खुले रह सकते हैं।",
                    )}
                  </p>
                </>
              )}
            </Panel>
            <Panel title={t("Work carried forward", "आगे सौंपा काम")}>
              <p className="work-note">
                {t(
                  "Acknowledgement means receipt. It does not resolve an issue, complete a task, or acknowledge other versions.",
                  "प्राप्ति की पुष्टि से समस्या हल या कार्य पूरा नहीं होता, और दूसरे संस्करणों की पुष्टि नहीं होती।",
                )}
              </p>
              {!(version?.items || item.draft?.items)?.length ? (
                <Empty />
              ) : (
                (version?.items || item.draft?.items || []).map(
                  (source, index) => {
                    const received = source.acknowledgements?.some(
                      (ack) => ack.user_id === session.user.id,
                    );
                    const route = {
                      task: "tasks",
                      report: "reports",
                      alert: "alerts",
                      conflict: "conflicts",
                    }[source.source_type as "task"];
                    return (
                      <article
                        key={
                          source.id ||
                          `${source.source_type}-${source.source_id}-${index}`
                        }
                        className={`handover-item ${source.critical ? "critical-item" : ""}`}
                      >
                        <div className="work-list-row">
                          <div>
                            <div className="work-tags">
                              {source.critical && <Status value="critical" />}
                              <Status
                                value={String(
                                  source.detail.status || "Pending",
                                )}
                              />
                            </div>
                            <h3>{source.title}</h3>
                            {source.detail.unresolved === true && (
                              <p className="work-warning">
                                {t("Still unresolved", "अभी अनसुलझा")}
                              </p>
                            )}
                            {!!source.detail.blocked_reason && (
                              <p>{String(source.detail.blocked_reason)}</p>
                            )}
                          </div>
                          {route && (
                            <Link
                              className="text-link"
                              to={`/workspace/${route}/${source.source_id}`}
                            >
                              {w("View source")} →
                            </Link>
                          )}
                        </div>
                        {version &&
                          receipt &&
                          source.critical &&
                          (received ? (
                            <p className="work-success">
                              {t(
                                "You acknowledged this critical item in this version.",
                                "आपने इस संस्करण के गंभीर विषय की प्राप्ति की पुष्टि की है।",
                              )}
                            </p>
                          ) : (
                            <ActionButton
                              action={() =>
                                post(`/handovers/${item.id}/acknowledge`, {
                                  version_id: version.id,
                                  item_id: source.id,
                                })
                              }
                            >
                              {w("Acknowledge this item")}
                            </ActionButton>
                          ))}
                      </article>
                    );
                  },
                )
              )}
            </Panel>
            {version && (
              <Panel title={t("Version recipients", "संस्करण पाने वाले")}>
                {version.recipients.map((recipient, index) => (
                  <div className="work-list-row" key={recipient.id}>
                    <strong>
                      {recipient.user_id === session.user.id
                        ? t("You", "आप")
                        : people.find((p) => p.id === recipient.user_id)
                            ?.name ||
                          `${t("Recipient", "प्राप्तकर्ता")} ${index + 1}`}
                    </strong>
                    {recipient.acknowledged_at ? (
                      <span>
                        {formatDate(
                          recipient.acknowledged_at,
                          session.organization.timezone,
                        )}
                      </span>
                    ) : (
                      <Status value="Pending" />
                    )}
                  </div>
                ))}
              </Panel>
            )}
            {editing && (
              <Modal
                title={t("Draft notes", "ड्राफ्ट टिप्पणियाँ")}
                onClose={() => setEditing(false)}
              >
                <FieldsForm
                  fields={[
                    {
                      name: "notes",
                      label: "Notes",
                      type: "textarea",
                      defaultValue: item.draft?.notes || "",
                    },
                  ]}
                  onSubmit={(values) =>
                    put(`/handovers/${item.id}/draft`, {
                      ...values,
                      version: item.version,
                    })
                  }
                  onSuccess={() => setEditing(false)}
                >
                  <p className="work-note">
                    {t(
                      "Saving a draft does not change any published version or notify recipients.",
                      "ड्राफ्ट सहेजने से प्रकाशित संस्करण नहीं बदलता और प्राप्तकर्ताओं को सूचना नहीं जाती।",
                    )}
                  </p>
                </FieldsForm>
              </Modal>
            )}
            {publishing && (
              <Modal
                title="Publish version"
                onClose={() => setPublishing(false)}
              >
                <FieldsForm
                  fields={[
                    {
                      name: "notes",
                      label: "Notes",
                      type: "textarea",
                      defaultValue:
                        item.draft?.notes || version?.snapshot.notes || "",
                    },
                    {
                      name: "changes",
                      label: "What changed?",
                      type: "textarea",
                      required: true,
                      defaultValue: item.latest_version
                        ? ""
                        : t("Initial publication", "पहला प्रकाशन"),
                    },
                  ]}
                  onSubmit={(values) =>
                    post(`/handovers/${item.id}/publish`, {
                      ...values,
                      version: item.version,
                    })
                  }
                  onSuccess={() => {
                    setVersionNumber(null);
                    setPublishing(false);
                  }}
                >
                  <p className="work-note">
                    {t(
                      "Publication creates an immutable version and notifies the incoming recipients. Current unresolved sources are compiled again.",
                      "प्रकाशन एक स्थायी संस्करण बनाता है और प्राप्तकर्ताओं को सूचित करता है। अनसुलझे स्रोत फिर संकलित किए जाते हैं।",
                    )}
                  </p>
                </FieldsForm>
              </Modal>
            )}
          </>
        ) : (
          <Panel>
            {!(data.data as Handover[] | undefined)?.length ? (
              <Empty>
                {t(
                  "Create a draft for a department and shift.",
                  "विभाग और शिफ्ट के लिए ड्राफ्ट बनाएँ।",
                )}
              </Empty>
            ) : (
              (data.data as Handover[]).map((handover) => (
                <Link
                  className="work-list-row"
                  key={handover.id}
                  to={`/workspace/handovers/${handover.id}`}
                >
                  <div>
                    <strong>
                      {
                        departments.data?.find(
                          (d) => d.id === handover.department_id,
                        )?.name
                      }
                    </strong>
                    <p>
                      {
                        shifts.data?.find((s) => s.id === handover.shift_id)
                          ?.name
                      }{" "}
                      · {handover.shift_date}
                    </p>
                    <small>
                      {t("Latest version", "नवीनतम संस्करण")}:{" "}
                      {handover.latest_version || "—"}
                    </small>
                  </div>
                  <Status value={handover.status} />
                </Link>
              ))
            )}
          </Panel>
        )}
      </When>
      {creating && (
        <Modal title="Create handover" onClose={() => setCreating(false)}>
          <FieldsForm
            fields={[
              {
                name: "department_id",
                label: "Department",
                type: "select",
                required: true,
                options: options(departments.data?.filter((d) => d.active)),
              },
              {
                name: "shift_id",
                label: "Shift",
                type: "select",
                required: true,
                options: options(shifts.data?.filter((s) => s.active)),
              },
              {
                name: "incoming_shift_id",
                label: "Incoming shift",
                type: "select",
                options: options(shifts.data?.filter((s) => s.active)),
              },
              {
                name: "shift_date",
                label: "Shift date",
                type: "date",
                required: true,
                defaultValue: new Intl.DateTimeFormat("en-CA", {
                  timeZone: session.organization.timezone,
                }).format(new Date()),
              },
              { name: "notes", label: "Notes", type: "textarea" },
            ]}
            onSubmit={(values) =>
              post("/handovers", {
                ...values,
                incoming_shift_id: nullable(values.incoming_shift_id),
              })
            }
            onSuccess={() => setCreating(false)}
          />
        </Modal>
      )}
    </>
  );
}
