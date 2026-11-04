import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { FileText, Plus } from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import {
  Empty,
  ErrorNotice,
  FieldsForm,
  Modal,
  PageTitle,
  Panel,
  Status,
  When,
  formatDate,
  options,
  useWords,
} from "../../components/workspace/UI";
import { api, evidenceUrl, post, search } from "../../lib/api";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type {
  Asset,
  Clarification,
  Conflict,
  Department,
  Paged,
  Report,
  ReportFields,
  Task,
} from "../../lib/types";
import { categories } from "./Reporting";
import { TaskForm } from "./Tasks";

export function ReportsPage() {
  const session = useSession((state) => state.session)!;
  const management = session.user.role !== "worker";
  const { departments } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [tab, setTab] = useState("all");
  const [department, setDepartment] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const reports = useQuery({
    queryKey: ["reports", tab, department, category, page],
    queryFn: () =>
      api<Paged<Report>>(
        `/reports${search({ department_id: department, category, needs_attention: tab === "attention" ? true : tab === "recent" ? false : null, page, limit: 25 })}`,
      ),
  });
  return (
    <>
      <PageTitle
        title="Reports"
        description={t(
          "Original updates, unresolved conditions, and traceable decisions.",
          "मूल अपडेट, अनसुलझी स्थितियाँ और दर्ज किए गए निर्णय।",
        )}
      >
        <Link className="button button-primary" to="/workspace/record">
          <Plus size={17} />
          {w("New report")}
        </Link>
      </PageTitle>
      <div className="work-filters">
        {management && (
          <div
            className="segmented"
            role="group"
            aria-label={t("Report views", "रिपोर्ट दृश्य")}
          >
            {[
              { value: "all", label: t("All reports", "सभी रिपोर्ट") },
              {
                value: "attention",
                label: t("Needs attention", "ध्यान आवश्यक"),
              },
              {
                value: "recent",
                label: t("Recent activity", "हाल की गतिविधि"),
              },
            ].map((item) => (
              <button
                aria-pressed={tab === item.value}
                key={item.value}
                onClick={() => {
                  setTab(item.value);
                  setPage(1);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
        <label>
          {w("Department")}
          <select
            value={department}
            onChange={(event) => {
              setDepartment(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{w("All")}</option>
            {departments.data?.map((d) => (
              <option value={d.id} key={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {w("Category")}
          <select
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setPage(1);
            }}
          >
            <option value="">{w("All")}</option>
            {categories.map((category) => (
              <option value={category} key={category}>
                {w(category)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {session.user.role === "organization" && (
        <p className="work-note">
          {t(
            "Report contents follow organization privacy policy. Sensitive access needs a purpose and, where required, an explicit temporary takeover.",
            "रिपोर्ट की सामग्री संगठन की गोपनीयता नीति के अनुसार उपलब्ध है। संवेदनशील पहुँच के लिए उद्देश्य और आवश्यक होने पर अस्थायी जिम्मेदारी चाहिए।",
          )}
        </p>
      )}
      <Panel>
        <When loading={reports.isLoading} error={reports.error}>
          {!reports.data?.items.length ? (
            <Empty>
              {t(
                "Submitted reports appear here after server confirmation.",
                "सर्वर की पुष्टि के बाद जमा रिपोर्ट यहाँ दिखती हैं।",
              )}
            </Empty>
          ) : (
            reports.data.items.map((report) => (
              <Link
                className="work-list-row"
                to={`/workspace/reports/${report.id}`}
                key={report.id}
              >
                <span className="list-icon">
                  <FileText size={21} />
                </span>
                <div className="row-grow">
                  <strong>
                    {w(report.category)} ·{" "}
                    {
                      departments.data?.find(
                        (d) => d.id === report.department_id,
                      )?.name
                    }
                  </strong>
                  <p>
                    {formatDate(
                      report.occurred_at,
                      session.organization.timezone,
                    )}
                  </p>
                  <div className="work-tags">
                    <Status value={report.status} />
                    {report.needs_attention && (
                      <Status value="Pending review" />
                    )}
                    {report.immediate_safety && <Status value="critical" />}
                    {report.resolved_at && <Status value="resolved" />}
                  </div>
                </div>
                <span className="text-link">{w("View details")} →</span>
              </Link>
            ))
          )}
        </When>
      </Panel>
      <div className="pagination">
        <button
          className="button button-outline"
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
        >
          {w("Previous page")}
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil((reports.data?.total || 0) / 25))}
        </span>
        <button
          className="button button-outline"
          disabled={page * 25 >= (reports.data?.total || 0)}
          onClick={() => setPage(page + 1)}
        >
          {w("Next page")}
        </button>
      </div>
    </>
  );
}

export function Evidence({
  asset,
  purpose = "",
}: {
  asset: Asset;
  purpose?: string;
}) {
  const { t } = usePreferences();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  return (
    <div className="evidence-card">
      <strong>{asset.name}</strong>
      <small>
        {asset.kind} · {Math.round(asset.byte_size / 1024)} KB
      </small>
      {asset.deleted_at ? (
        <p>{t("Retention period ended.", "संरक्षण अवधि समाप्त हो गई।")}</p>
      ) : !url ? (
        <button
          className="button button-outline"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            setError(null);
            void evidenceUrl(asset.id, purpose)
              .then(setUrl)
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          {t("Open private evidence", "निजी साक्ष्य खोलें")}
        </button>
      ) : asset.mime_type.startsWith("audio/") ? (
        <audio controls src={url} />
      ) : asset.mime_type.startsWith("video/") ? (
        <video controls src={url} />
      ) : asset.mime_type.startsWith("image/") ? (
        <img src={url} alt={asset.name} />
      ) : (
        <a className="text-link" href={url} download={asset.name}>
          {t("Download document", "दस्तावेज़ डाउनलोड करें")}
        </a>
      )}
      {!!error && <ErrorNotice error={error} />}
    </div>
  );
}

function Facts({ fields }: { fields: ReportFields }) {
  const w = useWords();
  const labels: Record<string, string> = {
    category: "Category",
    description: "Description",
    machine: "Machine / equipment",
    work_area: "Work area",
    batch: "Batch / order",
    quantity: "Quantity",
    unit: "Unit",
    operational_status: "Operational status",
    action_taken: "Action already taken",
    safety_implication: "Safety implication",
    quality_implication: "Quality implication",
  };
  return (
    <dl className="work-definition">
      {Object.entries(fields)
        .filter(([key, value]) => labels[key] && value !== null && value !== "")
        .map(([key, value]) => (
          <div key={key}>
            <dt>{w(labels[key])}</dt>
            <dd>{key === "category" ? w(String(value)) : String(value)}</dd>
          </div>
        ))}
    </dl>
  );
}

function ClarificationCard({
  item,
  own,
}: {
  item: Clarification;
  own: boolean;
}) {
  const { t } = usePreferences();
  const [responding, setResponding] = useState(false);
  return (
    <div className="clarification-card">
      <p>
        <strong>{item.question}</strong>
      </p>
      {item.response ? (
        <>
          <Status value={item.response_type || "responded"} />
          <p>{item.response}</p>
          <small>{formatDate(item.responded_at)}</small>
        </>
      ) : own ? (
        <>
          <button
            className="button button-outline"
            onClick={() => setResponding(true)}
          >
            {t("Respond", "उत्तर दें")}
          </button>
          {responding && (
            <Modal title="Response" onClose={() => setResponding(false)}>
              <FieldsForm
                fields={[
                  {
                    name: "response_type",
                    label: "Response type",
                    type: "select",
                    required: true,
                    options: [
                      {
                        value: "confirm",
                        label: t(
                          "Confirm my observation",
                          "अपना अवलोकन पुष्टि करें",
                        ),
                      },
                      {
                        value: "correct",
                        label: t("Explain a correction", "सुधार समझाएँ"),
                      },
                      {
                        value: "context",
                        label: t("Add context", "संदर्भ जोड़ें"),
                      },
                      {
                        value: "uncertain",
                        label: t("I am unsure", "मुझे निश्चित नहीं है"),
                      },
                    ],
                  },
                  {
                    name: "response",
                    label: "Response",
                    type: "textarea",
                    required: true,
                  },
                ]}
                onSubmit={(values) =>
                  post(`/clarifications/${item.id}/response`, values)
                }
                onSuccess={() => setResponding(false)}
              />
              <p className="work-note">
                {t(
                  "A response is added to history. Use Correct report to change the confirmed report fields.",
                  "उत्तर इतिहास में जुड़ता है। पुष्टि किए फ़ील्ड बदलने के लिए रिपोर्ट सुधारें।",
                )}
              </p>
            </Modal>
          )}
        </>
      ) : (
        <Status value="Pending" />
      )}
    </div>
  );
}

export function ReportDetailPage() {
  const { id } = useParams();
  const session = useSession((state) => state.session)!;
  const worker = session.user.role === "worker";
  const { workers, departments } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [purpose, setPurpose] = useState("");
  const [modal, setModal] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const report = useQuery({
    queryKey: ["report", id, purpose],
    queryFn: () => api<Report>(`/reports/${id}${search({ purpose })}`),
    retry: false,
    enabled: session.user.role !== "organization" || !!purpose,
  });
  const destinations = useQuery({
    queryKey: ["routing-departments"],
    queryFn: () => api<Department[]>("/routing-departments"),
    enabled: !worker,
  });
  const existingTasks = useQuery({
    queryKey: ["report-task-options", report.data?.department_id],
    queryFn: () =>
      api<Paged<Task>>(
        `/tasks${search({ department_id: report.data?.department_id, limit: 200 })}`,
      ),
    enabled: modal === "link" && !!report.data,
  });
  const item = report.data;
  const version =
    item?.versions?.find((v) => v.number === selectedVersion) ||
    item?.versions?.[0];
  const latest = item?.versions?.[0];
  const actions = [
    { value: "review", label: t("Mark reviewed", "समीक्षा दर्ज करें") },
    { value: "verify", label: "Verify" },
    { value: "clarify", label: "Request clarification" },
    { value: "escalate", label: "Escalate" },
    { value: "resolve", label: "Resolve issue" },
  ];
  return (
    <>
      <PageTitle
        title="Review report"
        description={t(
          "Verification confirms accuracy. Resolution requires a separate decision after actions are complete.",
          "सत्यापन जानकारी की शुद्धता की पुष्टि है। कार्य पूरे होने पर समस्या समाधान का अलग निर्णय आवश्यक है।",
        )}
      />
      {session.user.role === "organization" && !purpose && (
        <Panel title="Purpose of access">
          <FieldsForm
            fields={[
              {
                name: "purpose",
                label: "Purpose of access",
                type: "textarea",
                required: true,
              },
            ]}
            onSubmit={async (values) => {
              setPurpose(String(values.purpose));
            }}
          />
          <Link className="text-link" to="/workspace/policies">
            {t(
              "Review privacy policy or start a takeover",
              "गोपनीयता नीति देखें या अस्थायी जिम्मेदारी लें",
            )}{" "}
            →
          </Link>
        </Panel>
      )}
      <When loading={report.isFetching && !item} error={report.error}>
        {item && version && (
          <>
            <Panel>
              <div className="work-tags section-actions">
                <Status value={item.status} />
                {item.immediate_safety && <Status value="critical" />}
                {item.resolved_at && <Status value="resolved" />}
                <span>
                  {
                    departments.data?.find((d) => d.id === item.department_id)
                      ?.name
                  }
                </span>
                <span>
                  {workers.data?.items.find((p) => p.id === item.author_id)
                    ?.name || t("Original reporter", "मूल रिपोर्टर")}
                </span>
                <span>
                  {formatDate(item.occurred_at, session.organization.timezone)}
                </span>
              </div>
              <label className="version-selector">
                {t("Report version", "रिपोर्ट संस्करण")}
                <select
                  value={version.number}
                  onChange={(event) =>
                    setSelectedVersion(Number(event.target.value))
                  }
                >
                  {item.versions?.map((v) => (
                    <option key={v.id} value={v.number}>
                      {v.number}{" "}
                      {v.number === item.latest_version
                        ? t("· latest", "· नवीनतम")
                        : ""}{" "}
                      ·{" "}
                      {formatDate(v.created_at, session.organization.timezone)}
                    </option>
                  ))}
                </select>
              </label>
              <h2>
                {t(
                  "Human-confirmed update",
                  "व्यक्ति द्वारा पुष्टि किया अपडेट",
                )}
              </h2>
              <p className="report-original">{version.text}</p>
              {version.correction_reason && (
                <p className="work-note">
                  {t("Correction reason", "सुधार का कारण")}:{" "}
                  {version.correction_reason}
                </p>
              )}
              <Facts fields={version.fields} />
              {version.fields.uncertainty?.length ? (
                <div className="uncertainty-box">
                  <strong>
                    {t("Uncertainty retained", "अनिश्चितता सुरक्षित है")}
                  </strong>
                  {version.fields.uncertainty.map((value, index) => (
                    <p key={index}>{value}</p>
                  ))}
                </div>
              ) : null}
              <div className="work-actions">
                {!worker &&
                  actions.map((action) => (
                    <button
                      key={action.value}
                      className="button button-outline"
                      onClick={() => setModal(action.value)}
                    >
                      {w(action.label)}
                    </button>
                  ))}
                {item.author_id === session.user.id && (
                  <button
                    className="button button-outline"
                    onClick={() => setModal("correct")}
                  >
                    {w("Correct report")}
                  </button>
                )}
                {!worker && (
                  <>
                    <button
                      className="button button-primary"
                      onClick={() => setModal("task")}
                    >
                      {w("Create task")}
                    </button>
                    <button
                      className="button button-outline"
                      onClick={() => setModal("link")}
                    >
                      {t("Link existing task", "मौजूदा कार्य जोड़ें")}
                    </button>
                    <button
                      className="button button-outline"
                      onClick={() => setModal("route")}
                    >
                      {w("Follow-ups")}
                    </button>
                  </>
                )}
              </div>
            </Panel>
            <div className="work-two-column">
              <Panel title={t("Original transcript", "मूल ट्रांसक्रिप्ट")}>
                {version.transcript ? (
                  <>
                    <p className="work-copy">{version.transcript.original}</p>
                    <small>
                      {version.transcript.provider} · {version.transcript.model}
                    </small>
                    {version.transcript.asset_id && (
                      <AudioSource
                        assetId={version.transcript.asset_id}
                        purpose={purpose}
                      />
                    )}
                  </>
                ) : (
                  <p className="work-note">
                    {t(
                      "This update was entered as text.",
                      "यह अपडेट टेक्स्ट से दर्ज किया गया था।",
                    )}
                  </p>
                )}
              </Panel>
              <Panel
                title={t("AI suggestions — unverified", "AI सुझाव — अपुष्ट")}
              >
                {version.extraction ? (
                  <>
                    <Facts fields={version.extraction.output} />
                    <small>
                      {version.extraction.provider} · {version.extraction.model}
                    </small>
                  </>
                ) : (
                  <p className="work-note">
                    {t(
                      "No AI extraction was used for this version.",
                      "इस संस्करण में AI निष्कर्षण का उपयोग नहीं हुआ।",
                    )}
                  </p>
                )}
              </Panel>
            </div>
            <Panel title="Evidence">
              {version.evidence.length ? (
                <div className="evidence-grid">
                  {version.evidence.map((asset) => (
                    <Evidence key={asset.id} asset={asset} purpose={purpose} />
                  ))}
                </div>
              ) : (
                <Empty>
                  {t(
                    "No evidence attached to this version.",
                    "इस संस्करण में साक्ष्य नहीं जुड़ा है।",
                  )}
                </Empty>
              )}
            </Panel>
            <Panel title={t("Clarification", "स्पष्टीकरण")}>
              {item.clarifications?.length ? (
                item.clarifications.map((question) => (
                  <ClarificationCard
                    key={question.id}
                    item={question}
                    own={question.recipient_id === session.user.id}
                  />
                ))
              ) : (
                <Empty />
              )}
            </Panel>
            <Panel
              title={t("Linked work and conflicts", "जुड़े कार्य और विरोधाभास")}
            >
              <div className="work-actions">
                {item.task_links?.map((link) => (
                  <Link
                    className="button button-outline"
                    key={link.task_id}
                    to={`/workspace/tasks/${link.task_id}`}
                  >
                    {link.follow_up ? w("Follow-ups") : w("Related task")} →
                  </Link>
                ))}
                {!worker &&
                  item.conflict_ids?.map((conflictId) => (
                    <Link
                      className="button button-outline"
                      key={conflictId}
                      to={`/workspace/conflicts/${conflictId}`}
                    >
                      {w("Conflicts")} →
                    </Link>
                  ))}
              </div>
            </Panel>
            <Panel title="History">
              {!item.reviews?.length ? (
                <Empty />
              ) : (
                <ol className="work-timeline">
                  {item.reviews.map((review) => (
                    <li key={review.id}>
                      <span className="timeline-dot" />
                      <div>
                        <strong>
                          {w(review.action)} · {t("version", "संस्करण")}{" "}
                          {review.version_number}
                        </strong>
                        <p>{review.note}</p>
                        <small>
                          {formatDate(
                            review.created_at,
                            session.organization.timezone,
                          )}
                        </small>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
            {modal && (
              <Modal
                title={
                  actions.find((action) => action.value === modal)?.label ||
                  (modal === "link"
                    ? t("Link existing task", "मौजूदा कार्य जोड़ें")
                    : modal === "correct"
                      ? "Correct report"
                      : modal === "task"
                        ? "Create task"
                        : "Follow-ups")
                }
                onClose={() => setModal(null)}
              >
                {modal === "link" ? (
                  <When
                    loading={existingTasks.isPending}
                    error={existingTasks.error}
                  >
                    <FieldsForm
                      fields={[
                        {
                          name: "task_id",
                          label: "Related task",
                          type: "select",
                          required: true,
                          options: options(existingTasks.data?.items),
                        },
                        {
                          name: "note",
                          label: "Reason",
                          type: "textarea",
                          required: true,
                          hint: t(
                            "Explain why this task belongs with this report (at least 10 characters).",
                            "इस कार्य और रिपोर्ट का संबंध बताएँ (कम से कम 10 अक्षर)।",
                          ),
                        },
                      ]}
                      onSubmit={(values) =>
                        post(`/reports/${item.id}/tasks`, {
                          ...values,
                          version: item.version,
                        })
                      }
                      onSuccess={() => setModal(null)}
                    />
                  </When>
                ) : modal === "task" ? (
                  <TaskForm
                    sourceReportId={item.id}
                    departmentId={item.department_id}
                    onSaved={() => setModal(null)}
                  />
                ) : modal === "route" ? (
                  <FieldsForm
                    fields={[
                      {
                        name: "receiving_department_id",
                        label: "Receiving department",
                        type: "select",
                        required: true,
                        options: options(
                          destinations.data?.filter(
                            (d) => d.id !== item.department_id,
                          ),
                        ),
                      },
                      {
                        name: "note",
                        label: "Note",
                        type: "textarea",
                        required: true,
                        hint: t(
                          "Share only the context the receiving department needs.",
                          "केवल प्राप्त करने वाले विभाग के लिए आवश्यक संदर्भ साझा करें।",
                        ),
                      },
                    ]}
                    onSubmit={(values) =>
                      post("/follow-ups", { ...values, report_id: item.id })
                    }
                    onSuccess={() => setModal(null)}
                  />
                ) : modal === "correct" && latest ? (
                  <FieldsForm
                    fields={[
                      {
                        name: "text",
                        label: t("Corrected update", "सुधारा हुआ अपडेट"),
                        type: "textarea",
                        required: true,
                        defaultValue: latest.text,
                      },
                      {
                        name: "category",
                        label: "Category",
                        type: "select",
                        required: true,
                        defaultValue: latest.fields.category,
                        options: categories.map((value) => ({
                          value,
                          label: value,
                        })),
                      },
                      {
                        name: "quantity",
                        label: "Quantity",
                        type: "number",
                        min: 0,
                        defaultValue: latest.fields.quantity ?? "",
                      },
                      {
                        name: "operational_status",
                        label: "Operational status",
                        defaultValue: latest.fields.operational_status || "",
                      },
                      ...(
                        [
                          "machine",
                          "work_area",
                          "batch",
                          "unit",
                          "action_taken",
                          "safety_implication",
                          "quality_implication",
                        ] as const
                      ).map((key) => ({
                        name: key,
                        label: key.replaceAll("_", " "),
                        defaultValue: latest.fields[key] || "",
                      })),
                      {
                        name: "reason",
                        label: "Reason",
                        type: "textarea",
                        required: true,
                      },
                    ]}
                    onSubmit={(values) =>
                      post(`/reports/${id}/corrections`, {
                        version: item.version,
                        reason: values.reason,
                        report: {
                          client_request_id: crypto.randomUUID(),
                          department_id: item.department_id,
                          team_id: item.team_id,
                          shift_id: item.shift_id,
                          occurred_at: item.occurred_at,
                          text: values.text,
                          fields: {
                            ...latest.fields,
                            description: values.text,
                            category: values.category,
                            quantity:
                              values.quantity === ""
                                ? null
                                : Number(values.quantity),
                            operational_status:
                              values.operational_status || null,
                            ...Object.fromEntries(
                              [
                                "machine",
                                "work_area",
                                "batch",
                                "unit",
                                "action_taken",
                                "safety_implication",
                                "quality_implication",
                              ].map((key) => [key, values[key] || null]),
                            ),
                          },
                          transcript_id: latest.transcript?.id || null,
                          extraction_id: latest.extraction?.id || null,
                          task_id: null,
                          evidence_ids: latest.evidence
                            .filter(
                              (asset) =>
                                !asset.deleted_at &&
                                (!asset.retention_until ||
                                  Date.parse(asset.retention_until) >
                                    Date.now()),
                            )
                            .map((asset) => asset.id),
                          immediate_safety: item.immediate_safety,
                          confirmed: true,
                        },
                      })
                    }
                    onSuccess={() => {
                      setSelectedVersion(null);
                      setModal(null);
                    }}
                  />
                ) : (
                  <FieldsForm
                    fields={[
                      {
                        name: "note",
                        label:
                          modal === "clarify"
                            ? t(
                                "Short, neutral question",
                                "छोटा, निष्पक्ष प्रश्न",
                              )
                            : "Note",
                        type: "textarea",
                        required: true,
                      },
                    ]}
                    onSubmit={(values) =>
                      post(`/reports/${id}/review`, {
                        ...values,
                        action: modal,
                        version: item.version,
                      })
                    }
                    onSuccess={() => setModal(null)}
                  />
                )}
              </Modal>
            )}
          </>
        )}
      </When>
    </>
  );
}

function AudioSource({
  assetId,
  purpose,
}: {
  assetId: string;
  purpose: string;
}) {
  const { t } = usePreferences();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  return (
    <div className="work-stack">
      {url ? (
        <audio controls src={url} />
      ) : (
        <button
          className="button button-outline"
          onClick={() =>
            void evidenceUrl(assetId, purpose).then(setUrl).catch(setError)
          }
        >
          {t("Listen to original audio", "मूल ऑडियो सुनें")}
        </button>
      )}
      {!!error && <ErrorNotice error={error} />}
    </div>
  );
}

export function ConflictsPage() {
  const { id } = useParams();
  const { t } = usePreferences();
  const w = useWords();
  const [purpose, setPurpose] = useState("");
  const session = useSession((state) => state.session)!;
  const [resolve, setResolve] = useState(false);
  const data = useQuery<Conflict | Conflict[]>({
    queryKey: ["conflicts", id, purpose],
    queryFn: () =>
      id
        ? api<Conflict>(`/conflicts/${id}${search({ purpose })}`)
        : api<Conflict[]>("/conflicts"),
    retry: false,
    enabled: !id || session.user.role !== "organization" || !!purpose,
  });
  const detail = id ? (data.data as Conflict | undefined) : undefined;
  return (
    <>
      <PageTitle
        title="Conflicts"
        description={t(
          "Compare sources and clarify differences. Both original reports remain unchanged.",
          "मूल स्रोत की तुलना करें और अंतर स्पष्ट करें। दोनों मूल रिपोर्ट सुरक्षित रहती हैं।",
        )}
      />
      {id && session.user.role === "organization" && !purpose && (
        <Panel>
          <FieldsForm
            fields={[
              {
                name: "purpose",
                label: "Purpose of access",
                required: true,
                type: "textarea",
              },
            ]}
            onSubmit={async (values) => setPurpose(String(values.purpose))}
          />
        </Panel>
      )}
      <When loading={data.isFetching && !data.data} error={data.error}>
        {detail ? (
          <>
            <Panel>
              <Status value={detail.status} />
              <h2>{detail.title}</h2>
              <p className="work-copy">{detail.discrepancy}</p>
              {detail.resolution && (
                <p className="instruction-box">{detail.resolution}</p>
              )}
              {detail.status !== "resolved" && (
                <button
                  className="button button-primary"
                  onClick={() => setResolve(true)}
                >
                  {t(
                    "Record supervisor resolution",
                    "पर्यवेक्षक का समाधान दर्ज करें",
                  )}
                </button>
              )}
            </Panel>
            <div className="work-two-column">
              {detail.reports?.map((report) => {
                const source = report.versions?.find(
                  (v) => v.number === report.linked_version,
                );
                return (
                  <Panel
                    key={report.id}
                    title={`${t("Source version", "मूल संस्करण")} ${report.linked_version}`}
                  >
                    <p className="report-original">{source?.text}</p>
                    {source && <Facts fields={source.fields} />}
                    <small>
                      {formatDate(
                        report.occurred_at,
                        session.organization.timezone,
                      )}
                    </small>
                    {report.clarifications?.map((item) => (
                      <ClarificationCard
                        key={item.id}
                        item={item}
                        own={false}
                      />
                    ))}
                    <Link
                      className="text-link"
                      to={`/workspace/reports/${report.id}`}
                    >
                      {w("View source")} →
                    </Link>
                  </Panel>
                );
              })}
            </div>
            {resolve && (
              <Modal title="Resolution" onClose={() => setResolve(false)}>
                <FieldsForm
                  fields={[
                    {
                      name: "resolution",
                      label: "Resolution",
                      type: "textarea",
                      required: true,
                    },
                  ]}
                  onSubmit={(values) =>
                    post(`/conflicts/${detail.id}/resolve`, {
                      ...values,
                      version: detail.version,
                    })
                  }
                  onSuccess={() => setResolve(false)}
                />
              </Modal>
            )}
          </>
        ) : (
          <Panel>
            {!(data.data as Conflict[] | undefined)?.length ? (
              <Empty />
            ) : (
              (data.data as Conflict[]).map((conflict) => (
                <Link
                  className="work-list-row"
                  key={conflict.id}
                  to={`/workspace/conflicts/${conflict.id}`}
                >
                  <div>
                    <strong>{conflict.title}</strong>
                    <p>{conflict.discrepancy}</p>
                  </div>
                  <Status value={conflict.status} />
                </Link>
              ))
            )}
          </Panel>
        )}
      </When>
    </>
  );
}

type FollowUp = {
  id: string;
  report_id: string;
  originating_department_id: string;
  receiving_department_id: string;
  task_id: string | null;
  note: string;
  status: string;
  task_status: string | null;
};
export function FollowUpsPage() {
  const { t } = usePreferences();
  const w = useWords();
  const session = useSession((state) => state.session)!;
  const { departments } = useCatalog();
  const [assigning, setAssigning] = useState<FollowUp | null>(null);
  const followups = useQuery({
    queryKey: ["follow-ups"],
    queryFn: () => api<FollowUp[]>("/follow-ups"),
  });
  return (
    <>
      <PageTitle
        title="Follow-ups"
        description={t(
          "Connected work across departments. The original report and owner remain intact.",
          "विभागों के बीच जुड़े कार्य। मूल रिपोर्ट और जिम्मेदार व्यक्ति सुरक्षित रहते हैं।",
        )}
      />
      <Panel>
        <When loading={followups.isLoading} error={followups.error}>
          {!followups.data?.length ? (
            <Empty>
              {t(
                "Route a reviewed report to another department to request follow-up.",
                "अनुवर्ती कार्य के लिए समीक्षा की हुई रिपोर्ट दूसरे विभाग भेजें।",
              )}
            </Empty>
          ) : (
            followups.data.map((item) => (
              <div className="work-list-row" key={item.id}>
                <div>
                  <strong>
                    {departments.data?.find(
                      (d) => d.id === item.receiving_department_id,
                    )?.name ||
                      t("Receiving department", "प्राप्त करने वाला विभाग")}
                  </strong>
                  <p>{item.note}</p>
                  <div className="work-tags">
                    <Status value={item.status} />
                    {item.task_status && <Status value={item.task_status} />}
                  </div>
                </div>
                <div className="work-actions">
                  {departments.data?.some(
                    (d) => d.id === item.originating_department_id,
                  ) && (
                    <Link
                      className="button button-outline"
                      to={`/workspace/reports/${item.report_id}`}
                    >
                      {w("View source")}
                    </Link>
                  )}
                  {item.task_id &&
                  departments.data?.some(
                    (d) => d.id === item.receiving_department_id,
                  ) ? (
                    <Link
                      className="button button-outline"
                      to={`/workspace/tasks/${item.task_id}`}
                    >
                      {w("Tasks")}
                    </Link>
                  ) : !item.task_id &&
                    (session.user.role === "organization" ||
                      session.memberships.some(
                        (m) =>
                          m.department_id === item.receiving_department_id &&
                          m.permissions.includes("manage"),
                      )) ? (
                    <button
                      className="button button-primary"
                      onClick={() => setAssigning(item)}
                    >
                      {w("Create task")}
                    </button>
                  ) : null}
                </div>
              </div>
            ))
          )}
        </When>
      </Panel>
      {assigning && (
        <Modal title="Create task" onClose={() => setAssigning(null)}>
          <TaskForm
            endpoint={`/follow-ups/${assigning.id}/assign`}
            departmentId={assigning.receiving_department_id}
            onSaved={() => setAssigning(null)}
          />
        </Modal>
      )}
    </>
  );
}
