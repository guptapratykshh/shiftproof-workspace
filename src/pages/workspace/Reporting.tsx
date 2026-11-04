import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  Mic,
  Paperclip,
  Save,
  Send,
  Square,
  TriangleAlert,
  WandSparkles,
} from "lucide-react";
import { useCatalog } from "../../components/workspace/Workspace";
import {
  ActionButton,
  Empty,
  ErrorNotice,
  PageTitle,
  Panel,
  Status,
  formatDate,
  useWords,
} from "../../components/workspace/UI";
import { api, post } from "../../lib/api";
import {
  attachmentBlob,
  deleteDraft,
  fileAttachment,
  loadDrafts,
  saveDraft,
  syncDrafts,
  uploadAttachment,
  type LocalAttachment,
  type LocalDraft,
} from "../../lib/offline";
import { useSession } from "../../lib/session";
import { usePreferences } from "../../lib/preferences";
import type {
  Job,
  Paged,
  ReportFields,
  ReportPayload,
  Task,
} from "../../lib/types";

export const categories = [
  "general",
  "progress",
  "safety",
  "quality",
  "equipment",
  "maintenance",
  "materials",
];
export function ReportComposer() {
  const session = useSession((state) => state.session)!;
  const { departments, teams, shifts } = useCatalog();
  const { t } = usePreferences();
  const w = useWords();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [draftId, setDraftId] = useState(
    () => params.get("draft") || crypto.randomUUID(),
  );
  const [occurredAt, setOccurredAt] = useState(new Date().toISOString());
  const [departmentId, setDepartmentId] = useState(
    params.get("department") ||
      session.memberships.find((m) => m.primary)?.department_id ||
      "",
  );
  const [teamId, setTeamId] = useState("");
  const [shiftId, setShiftId] = useState("");
  const [taskId, setTaskId] = useState(params.get("task") || "");
  const [text, setText] = useState("");
  const [fields, setFields] = useState<ReportFields>({
    category: "general",
    description: "",
  });
  const [transcriptId, setTranscriptId] = useState<string | null>(null);
  const [extractionId, setExtractionId] = useState<string | null>(null);
  const [original, setOriginal] = useState("");
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [immediateAlertId, setImmediateAlertId] = useState<string | null>(null);
  const [status, setStatus] = useState<LocalDraft["status"]>("Draft");
  const [error, setError] = useState<unknown>(null);
  const [hint, setHint] = useState("");
  const [consent, setConsent] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [critical, setCritical] = useState(false);
  const [speechLanguage, setSpeechLanguage] = useState(
    session.user.preferences.speech_language || "hi-IN,en-IN",
  );
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [audioPreview, setAudioPreview] = useState("");
  const [loaded, setLoaded] = useState(!params.get("draft"));
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const handledJobs = useRef(new Set<string>());
  const [associations, setAssociations] = useState<
    { id: string; title: string; basis: string }[]
  >([]);
  const shiftInitialized = useRef(false);
  const context = useQuery({
    queryKey: ["workspace-context"],
    queryFn: () => api<{ shifts: { id: string }[] }>("/workspace/context"),
  });
  useEffect(() => {
    if (!shiftInitialized.current && context.data && !params.get("draft")) {
      shiftInitialized.current = true;
      if (context.data.shifts.length === 1)
        setShiftId(context.data.shifts[0].id);
    }
  }, [context.data]);
  const tasks = useQuery({
    queryKey: ["tasks", "report", departmentId],
    queryFn: () =>
      api<Paged<Task>>(`/tasks?department_id=${departmentId}&limit=200`),
    enabled: !!departmentId,
  });
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) =>
      ["succeeded", "failed"].includes(query.state.data?.status || "")
        ? false
        : 1500,
  });
  const payload = (): ReportPayload => ({
    client_request_id: draftId,
    department_id: departmentId,
    team_id: teamId || null,
    shift_id: shiftId || null,
    occurred_at: occurredAt,
    text,
    fields: { ...fields, description: fields.description || text },
    task_id: taskId || null,
    transcript_id: transcriptId,
    extraction_id: extractionId,
    evidence_ids: attachments.map((a) => a.uploadedId!).filter(Boolean),
    immediate_safety: critical,
    immediate_alert_id: immediateAlertId,
    confirmed: true,
  });
  const draft = (nextStatus: LocalDraft["status"]): LocalDraft => ({
    id: draftId,
    status: nextStatus,
    updatedAt: new Date().toISOString(),
    payload: payload(),
    attachments,
  });
  useEffect(() => {
    if (!params.get("draft")) return;
    void loadDrafts(session)
      .then((entries) => {
        const item = entries.find((entry) => entry.id === params.get("draft"));
        if (!item)
          throw new Error(
            t(
              "This draft is not available to this account.",
              "यह ड्राफ्ट इस खाते के लिए उपलब्ध नहीं है।",
            ),
          );
        if (item.status === "Submitted") {
          navigate(`/workspace/reports/${item.reportId}`);
          return;
        }
        setDraftId(item.id);
        setOccurredAt(item.payload.occurred_at);
        setDepartmentId(item.payload.department_id);
        setTeamId(item.payload.team_id || "");
        setShiftId(item.payload.shift_id || "");
        setTaskId(item.payload.task_id || "");
        setText(item.payload.text);
        setFields(item.payload.fields);
        setTranscriptId(item.payload.transcript_id);
        setExtractionId(item.payload.extraction_id);
        setCritical(item.payload.immediate_safety);
        setImmediateAlertId(item.payload.immediate_alert_id || null);
        setAttachments(item.attachments);
        setStatus(
          ["Pending sync", "Syncing"].includes(item.status)
            ? item.status
            : "Saved locally",
        );
        setLoaded(true);
      })
      .catch(setError);
  }, []);
  useEffect(() => {
    if (
      !loaded ||
      (!text.trim() && !attachments.length && !immediateAlertId) ||
      !["Draft", "Saved locally"].includes(status)
    )
      return;
    const timer = setTimeout(() => {
      void saveDraft(session, draft("Saved locally"))
        .then(() => setStatus("Saved locally"))
        .catch(() =>
          setError(
            t(
              "Local storage is full or unavailable. Keep this page open and submit when connected.",
              "स्थानीय स्टोरेज भरा या अनुपलब्ध है। पेज खुला रखें और कनेक्शन पर जमा करें।",
            ),
          ),
        );
    }, 1200);
    return () => clearTimeout(timer);
  }, [
    loaded,
    text,
    fields,
    attachments,
    departmentId,
    teamId,
    shiftId,
    taskId,
    critical,
    transcriptId,
    extractionId,
    immediateAlertId,
  ]);
  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000);
    const stop = setTimeout(
      () => recorder.current?.state === "recording" && recorder.current.stop(),
      29_000,
    );
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [recording]);
  useEffect(
    () => () => {
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );
  useEffect(() => {
    const audio = attachments.find((item) => item.kind === "audio");
    if (!audio) {
      setAudioPreview("");
      return;
    }
    const url = URL.createObjectURL(attachmentBlob(audio));
    setAudioPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [attachments]);
  useEffect(() => {
    const value = job.data;
    if (
      !value ||
      value.status !== "succeeded" ||
      handledJobs.current.has(value.id)
    )
      return;
    handledJobs.current.add(value.id);
    if (value.result.text) {
      setOriginal(value.result.text);
      setText(value.result.text);
      setTranscriptId(value.result.transcript_id || null);
      setHint(
        t(
          "Review the transcript before requesting suggestions.",
          "सुझाव माँगने से पहले ट्रांसक्रिप्ट की समीक्षा करें।",
        ),
      );
    }
    if (value.result.fields) {
      setFields(value.result.fields);
      setExtractionId(value.result.extraction_id || null);
      setTranscriptId(value.result.transcript_id || transcriptId);
      setHint(
        t(
          "These are AI suggestions. Check and correct every relevant field before confirming.",
          "ये AI सुझाव हैं। पुष्टि से पहले हर आवश्यक फ़ील्ड जाँचें और सुधारें।",
        ),
      );
    }
    setConfirmed(false);
  }, [job.data]);
  const startRecording = async () => {
    setError(null);
    if (!consent || !departmentId) {
      setError(
        t(
          "Choose a department and confirm recording consent first.",
          "पहले विभाग चुनें और रिकॉर्डिंग की सहमति दें।",
        ),
      );
      return;
    }
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        t(
          "Recording is not supported on this browser. Type your update below.",
          "इस ब्राउज़र में रिकॉर्डिंग उपलब्ध नहीं है। नीचे अपडेट लिखें।",
        ),
      );
      return;
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      chunks.current = [];
      setElapsed(0);
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/ogg;codecs=opus",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      const media = new MediaRecorder(
        stream.current,
        mimeType ? { mimeType } : undefined,
      );
      recorder.current = media;
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      media.onerror = () => {
        setError(
          t(
            "Recording stopped unexpectedly. Retry or use text.",
            "रिकॉर्डिंग अचानक रुक गई। फिर कोशिश करें या टेक्स्ट लिखें।",
          ),
        );
        stream.current?.getTracks().forEach((track) => track.stop());
        setRecording(false);
      };
      media.onstop = () => {
        stream.current?.getTracks().forEach((track) => track.stop());
        setRecording(false);
        const audio = new Blob(chunks.current, { type: media.mimeType });
        void fileAttachment(
          audio,
          `update.${media.mimeType.includes("mp4") ? "m4a" : "webm"}`,
          "audio",
          true,
        )
          .then((attachment) => {
            setAttachments((current) => [
              ...current.filter((a) => a.kind !== "audio"),
              attachment,
            ]);
            setHint(
              t(
                "Recording saved in your draft. Transcribe when connected, or type your update.",
                "रिकॉर्डिंग ड्राफ्ट में है। कनेक्शन पर ट्रांसक्रिप्ट बनाएँ या अपडेट लिखें।",
              ),
            );
          })
          .catch(setError);
      };
      media.start(250);
      setRecording(true);
    } catch {
      setError(
        t(
          "Microphone access was denied or no microphone is available. You can still type your update.",
          "माइक्रोफ़ोन की अनुमति नहीं मिली या माइक्रोफ़ोन उपलब्ध नहीं है। आप अपडेट लिख सकते हैं।",
        ),
      );
    }
  };
  const transcribe = async () => {
    const recording = attachments.find((a) => a.kind === "audio");
    if (!recording) return;
    setBusy(true);
    setError(null);
    try {
      const uploadedId =
        recording.uploadedId ||
        (await uploadAttachment(recording, departmentId)).id;
      setAttachments((current) =>
        current.map((a) => (a === recording ? { ...a, uploadedId } : a)),
      );
      const result = await post<Job>("/transcriptions", {
        asset_id: uploadedId,
        language: speechLanguage,
      });
      setJobId(result.id);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  };
  const extract = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await post<Job>("/extractions", {
        text,
        transcript_id: transcriptId,
      });
      setJobId(result.id);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  };
  const submit = async () => {
    if (!text.trim() || !departmentId || !confirmed) {
      setError(
        t(
          "Choose a department, add your update and confirm your review.",
          "विभाग चुनें, अपडेट भरें और समीक्षा की पुष्टि करें।",
        ),
      );
      return;
    }
    setBusy(true);
    setError(null);
    setStatus("Pending sync");
    try {
      await saveDraft(session, draft("Pending sync"));
      await syncDrafts(
        session,
        () => useSession.getState().session?.user.id === session.user.id,
      );
      const saved = (await loadDrafts(session)).find(
        (item) => item.id === draftId,
      );
      if (saved?.status === "Submitted")
        navigate(`/workspace/reports/${saved.reportId}`);
      else {
        setStatus(saved?.status || "Pending sync");
        setHint(
          t(
            "Your report is saved locally. It will show Submitted only after server confirmation.",
            "रिपोर्ट डिवाइस पर सुरक्षित है। सर्वर की पुष्टि के बाद ही जमा की हुई दिखाई देगी।",
          ),
        );
        if (saved?.error) setError(saved.error);
      }
    } catch (cause) {
      setError(cause);
      setStatus("Draft");
    } finally {
      setBusy(false);
    }
  };
  const setField = (key: keyof ReportFields, value: string) => {
    setFields((current) => ({
      ...current,
      [key]:
        key === "quantity"
          ? value === ""
            ? null
            : Number(value)
          : value || null,
    }));
    setConfirmed(false);
  };
  if (["Pending sync", "Syncing", "Submitted"].includes(status))
    return (
      <>
        <PageTitle title="New report">
          <Status value={status} />
        </PageTitle>
        <Panel>
          <p role="status">
            {t(
              "Your reviewed report is saved for synchronization. Open local drafts to follow its progress.",
              "आपकी समीक्षा की हुई रिपोर्ट सिंक के लिए सुरक्षित है। प्रगति देखने के लिए स्थानीय ड्राफ्ट खोलें।",
            )}
          </p>
          <Link className="button button-primary" to="/workspace/drafts">
            {w("Local drafts")}
          </Link>
        </Panel>
      </>
    );
  const processing =
    !!jobId && !["succeeded", "failed"].includes(job.data?.status || "");
  return (
    <>
      <PageTitle
        title="New report"
        description={t(
          "Say what happened. Keep unresolved conditions visible. A task is optional.",
          "बताएँ क्या हुआ। अनसुलझी स्थितियाँ स्पष्ट रखें। कार्य चुनना वैकल्पिक है।",
        )}
      >
        <Link className="button button-outline" to="/workspace/drafts">
          {w("Local drafts")}
        </Link>
        <Link className="button button-outline" to="/workspace/reports">
          {w("Reports")}
        </Link>
        <Status value={status} />
      </PageTitle>
      <div className="report-compose-layout">
        <div className="work-stack">
          <Panel title={t("01 / Capture your update", "01 / अपडेट दर्ज करें")}>
            <div className="work-form-grid">
              <label className="form-field">
                {w("Department")} *
                <select
                  disabled={!!immediateAlertId}
                  value={departmentId}
                  onChange={(event) => {
                    setDepartmentId(event.target.value);
                    setTeamId("");
                    setTaskId("");
                    setConfirmed(false);
                  }}
                >
                  <option value="">{w("Select an option")}</option>
                  {departments.data
                    ?.filter((d) => d.active)
                    .map((d) => (
                      <option value={d.id} key={d.id}>
                        {d.name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="form-field">
                {w("Speech language")}
                <select
                  value={speechLanguage}
                  onChange={(event) => setSpeechLanguage(event.target.value)}
                >
                  <option value="hi-IN,en-IN">हिन्दी / Hinglish</option>
                  <option value="hi-IN">हिन्दी</option>
                  <option value="en-IN">English</option>
                </select>
              </label>
            </div>
            <label className="check-field recording-consent">
              <input
                type="checkbox"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
              />
              {t(
                "I consent to recording and authorized review under my organization’s retention policy.",
                "मैं संगठन की संरक्षण नीति के अनुसार रिकॉर्डिंग और अधिकृत समीक्षा की सहमति देता/देती हूँ।",
              )}
            </label>
            <div
              className={`recording-control ${recording ? "is-recording" : ""}`}
            >
              <button
                className="record-button"
                aria-label={
                  recording
                    ? t("Stop recording", "रिकॉर्डिंग रोकें")
                    : t("Start recording", "रिकॉर्डिंग शुरू करें")
                }
                disabled={busy}
                onClick={
                  recording ? () => recorder.current?.stop() : startRecording
                }
              >
                {recording ? <Square size={28} /> : <Mic size={30} />}
              </button>
              <div>
                <strong>
                  {recording
                    ? t("Recording…", "रिकॉर्डिंग जारी…")
                    : t("Record a short update", "छोटा अपडेट रिकॉर्ड करें")}
                </strong>
                <p>
                  {recording
                    ? `${elapsed} / 29 ${t("seconds", "सेकंड")}`
                    : t(
                        "Up to 29 seconds. Hindi, Hinglish or English.",
                        "अधिकतम 29 सेकंड। हिन्दी, हिंग्लिश या अंग्रेज़ी।",
                      )}
                </p>
              </div>
            </div>
            {audioPreview && (
              <div className="work-stack">
                <audio controls src={audioPreview} />
                <button
                  className="button button-outline"
                  onClick={() => void transcribe()}
                  disabled={busy || processing || !navigator.onLine}
                >
                  {t("Generate transcript", "ट्रांसक्रिप्ट बनाएँ")}
                </button>
              </div>
            )}
            <label className="form-field field-wide report-text">
              {t(
                "Your update — type or correct the transcript",
                "आपका अपडेट — लिखें या ट्रांसक्रिप्ट सुधारें",
              )}
              <textarea
                rows={6}
                maxLength={20000}
                value={text}
                onChange={(event) => {
                  setText(event.target.value);
                  setConfirmed(false);
                }}
                placeholder={t(
                  "For example: packing is complete, but quality inspection is still pending.",
                  "जैसे: पैकिंग पूरी है, लेकिन गुणवत्ता की जाँच अभी बाकी है।",
                )}
              />
            </label>
            {original && (
              <details>
                <summary>
                  {t(
                    "Original speech transcript",
                    "मूल बोले गए अपडेट की ट्रांसक्रिप्ट",
                  )}
                </summary>
                <p className="work-copy">{original}</p>
              </details>
            )}
            <button
              className="button button-outline"
              onClick={() => void extract()}
              disabled={!text.trim() || busy || processing || !navigator.onLine}
            >
              <WandSparkles size={17} />
              {t("Suggest report fields", "रिपोर्ट फ़ील्ड सुझाएँ")}
            </button>
            {(processing || job.data?.status === "failed") && (
              <div className="processing-state">
                <Status value={job.data?.status || "Processing"} />
                <p>
                  {job.data?.error ||
                    t(
                      "Your source is saved while processing continues.",
                      "प्रक्रिया जारी है और मूल अपडेट सुरक्षित है।",
                    )}
                </p>
                {job.data?.status === "failed" && (
                  <ActionButton action={() => post(`/jobs/${jobId}/retry`)}>
                    {w("Try again")}
                  </ActionButton>
                )}
              </div>
            )}
          </Panel>
          <Panel
            title={t("02 / Review the details", "02 / विवरण की समीक्षा करें")}
          >
            <ActionButton
              action={async () => {
                const result = await post<{ items: typeof associations }>(
                  "/task-associations",
                  { text, department_id: departmentId },
                );
                setAssociations(result.items);
              }}
            >
              {t(
                "Find related work from this update",
                "इस अपडेट से संबंधित कार्य खोजें",
              )}
            </ActionButton>
            {associations.map((candidate) => (
              <button
                className="button button-outline"
                key={candidate.id}
                onClick={() => {
                  setTaskId(candidate.id);
                  setConfirmed(false);
                }}
              >
                {t("Use this suggested task", "यह सुझाया कार्य चुनें")}:{" "}
                {candidate.title}
              </button>
            ))}
            {associations.length > 0 && (
              <p className="work-note">
                {t(
                  "Suggestions match your words to work you can access. Select only if the association is correct; no task is required.",
                  "सुझाव आपके शब्दों से आपके कार्य मिलाते हैं। सही होने पर ही चुनें; कार्य चुनना आवश्यक नहीं है।",
                )}
              </p>
            )}

            <p className="work-note">
              {t(
                "Only fill in what applies. AI suggestions are unverified until you check them; leave uncertain facts blank.",
                "केवल लागू जानकारी भरें। AI सुझाव जाँचने तक अपुष्ट हैं; अनिश्चित तथ्य खाली छोड़ें।",
              )}
            </p>
            {fields.uncertainty?.length ? (
              <div className="uncertainty-box">
                <strong>
                  {t("Needs your confirmation", "आपकी पुष्टि आवश्यक है")}
                </strong>
                {fields.uncertainty.map((question, index) => (
                  <p key={index}>{question}</p>
                ))}
              </div>
            ) : null}
            <div className="work-form-grid">
              <label className="form-field">
                {w("Category")}
                <select
                  value={fields.category}
                  onChange={(event) => setField("category", event.target.value)}
                >
                  {categories.map((category) => (
                    <option value={category} key={category}>
                      {w(category)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                {w("Related task")}
                <select
                  value={taskId}
                  onChange={(event) => setTaskId(event.target.value)}
                >
                  <option value="">
                    {t("No task association", "किसी कार्य से नहीं जुड़ा")}
                  </option>
                  {tasks.data?.items.map((task) => (
                    <option value={task.id} key={task.id}>
                      {task.title}
                    </option>
                  ))}
                </select>
              </label>
              {(
                [
                  { key: "machine", label: "Machine / equipment" },
                  { key: "work_area", label: "Work area" },
                  { key: "batch", label: "Batch / order" },
                  { key: "quantity", label: "Quantity" },
                  { key: "unit", label: "Unit" },
                  { key: "operational_status", label: "Operational status" },
                  { key: "action_taken", label: "Action already taken" },
                  { key: "safety_implication", label: "Safety implication" },
                  { key: "quality_implication", label: "Quality implication" },
                ] as const
              ).map((item) => (
                <label className="form-field" key={item.key}>
                  {w(item.label)}
                  <input
                    type={item.key === "quantity" ? "number" : "text"}
                    min={item.key === "quantity" ? 0 : undefined}
                    step={item.key === "quantity" ? "any" : undefined}
                    value={fields[item.key] ?? ""}
                    onChange={(event) => setField(item.key, event.target.value)}
                  />
                </label>
              ))}
              <label className="form-field">
                {w("Team")}
                <select
                  value={teamId}
                  onChange={(event) => setTeamId(event.target.value)}
                >
                  <option value="">{w("None")}</option>
                  {teams.data
                    ?.filter(
                      (team) =>
                        team.department_id === departmentId &&
                        team.active &&
                        (session.user.role !== "worker" ||
                          session.teamMemberships.some(
                            (m) => m.team_id === team.id,
                          )),
                    )
                    .map((team) => (
                      <option key={team.id} value={team.id}>
                        {team.name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="form-field">
                {w("Shift")}
                <select
                  value={shiftId}
                  onChange={(event) => setShiftId(event.target.value)}
                >
                  <option value="">{w("None")}</option>
                  {shifts.data?.map((shift) => (
                    <option key={shift.id} value={shift.id}>
                      {shift.name} · {shift.starts_at}–{shift.ends_at}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </Panel>
          <Panel title="Evidence">
            <label className="file-drop">
              <Paperclip size={22} />
              <span>
                {t(
                  "Attach photos, video or a PDF document",
                  "फ़ोटो, वीडियो या PDF दस्तावेज़ जोड़ें",
                )}
              </span>
              <input
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,application/pdf"
                onChange={async (event) => {
                  const files = [...(event.target.files || [])];
                  setError(null);
                  try {
                    if (
                      files.length + attachments.length > 10 ||
                      files.some((file) => file.size > 25 * 1024 * 1024)
                    )
                      throw new Error(
                        t(
                          "Use up to 10 attachments, each no larger than 25 MB.",
                          "अधिकतम 10 फ़ाइलें, हर फ़ाइल 25 MB से छोटी रखें।",
                        ),
                      );
                    const converted = await Promise.all(
                      files.map((file) =>
                        fileAttachment(
                          file,
                          file.name,
                          file.type.startsWith("image/")
                            ? "photo"
                            : file.type.startsWith("video/")
                              ? "video"
                              : "document",
                        ),
                      ),
                    );
                    setAttachments((current) => [...current, ...converted]);
                  } catch (cause) {
                    setError(cause);
                  }
                }}
              />
            </label>
            {attachments.map((attachment, index) => (
              <div className="work-list-row" key={index}>
                <div>
                  <strong>{attachment.name}</strong>
                  <small>
                    {t(
                      "Stored privately with this report",
                      "इस रिपोर्ट के साथ निजी रूप से सुरक्षित",
                    )}
                  </small>
                </div>
                <button
                  className="text-button"
                  onClick={() =>
                    setAttachments((current) =>
                      current.filter((_, i) => i !== index),
                    )
                  }
                >
                  {t("Remove", "हटाएँ")}
                </button>
              </div>
            ))}
          </Panel>
        </div>
        <aside className="report-submit-panel">
          <Panel title={t("Carry it forward", "आगे पहुँचाएँ")}>
            <p>
              {t(
                "Your original update and confirmed details stay linked. Confirm only what you observed.",
                "मूल अपडेट और पुष्टि किए विवरण जुड़े रहते हैं। केवल अपने अवलोकन की पुष्टि करें।",
              )}
            </p>
            <label className="check-field">
              <input
                type="checkbox"
                checked={critical}
                disabled={!!immediateAlertId}
                onChange={(event) => setCritical(event.target.checked)}
              />
              {t(
                "This is an immediate safety concern",
                "यह तत्काल सुरक्षा का विषय है",
              )}
            </label>
            {critical && (
              <div className="work-warning">
                <p>
                  {t(
                    "Follow your workplace’s emergency procedure. Send an alert now without waiting for transcription or AI.",
                    "कार्यस्थल की आपातकालीन प्रक्रिया अपनाएँ। ट्रांसक्रिप्ट या AI का इंतज़ार किए बिना अलर्ट भेजें।",
                  )}
                </p>
                {immediateAlertId ? (
                  <p role="status">
                    {t(
                      "Supervisor alerted. This report will stay linked to that alert.",
                      "पर्यवेक्षक को अलर्ट भेजा गया। रिपोर्ट उसी अलर्ट से जुड़ेगी।",
                    )}
                  </p>
                ) : (
                  <ActionButton
                    action={async () => {
                      const alert = await post<{ id: string }>(
                        "/alerts/immediate",
                        {
                          department_id: departmentId,
                          title:
                            text.trim().slice(0, 200) ||
                            "Immediate safety concern reported by worker",
                          client_request_id: draftId,
                        },
                      );
                      setImmediateAlertId(alert.id);
                    }}
                  >
                    <TriangleAlert size={17} />
                    {t("Alert supervisor now", "पर्यवेक्षक को अभी अलर्ट करें")}
                  </ActionButton>
                )}
              </div>
            )}
            <label className="check-field">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              {t(
                "I reviewed this report and any uncertainty is stated clearly.",
                "मैंने रिपोर्ट जाँची है और अनिश्चित जानकारी स्पष्ट की है।",
              )}
            </label>
            {hint && (
              <p className="work-note" role="status">
                {hint}
              </p>
            )}
            {!!error && <ErrorNotice error={error} />}
            <button
              className="button button-primary"
              disabled={
                busy ||
                recording ||
                !confirmed ||
                ["Pending sync", "Syncing", "Submitted"].includes(status)
              }
              onClick={() => void submit()}
            >
              <Send size={17} />
              {w(busy ? "Saving…" : "Submit report")}
            </button>
            <button
              className="button button-outline"
              disabled={
                busy ||
                recording ||
                !["Draft", "Saved locally"].includes(status)
              }
              onClick={() => {
                void saveDraft(session, draft("Saved locally"))
                  .then(() => {
                    setStatus("Saved locally");
                    setHint(
                      t(
                        "Draft saved on this device.",
                        "ड्राफ्ट इस डिवाइस पर सुरक्षित है।",
                      ),
                    );
                  })
                  .catch(setError);
              }}
            >
              <Save size={17} />
              {w("Save draft")}
            </button>
            <Link className="text-link" to="/workspace/drafts">
              {w("Local drafts")} →
            </Link>
          </Panel>
        </aside>
      </div>
    </>
  );
}

export function DraftsPage() {
  const session = useSession((state) => state.session)!;
  const { t } = usePreferences();
  const w = useWords();
  const client = useQueryClient();
  const drafts = useQuery({
    queryKey: ["drafts", session.user.id],
    queryFn: () => loadDrafts(session),
    networkMode: "always",
  });
  useEffect(() => {
    const changed = () =>
      void client.invalidateQueries({ queryKey: ["drafts"] });
    addEventListener("shiftproof-drafts-updated", changed);
    return () => removeEventListener("shiftproof-drafts-updated", changed);
  }, [client]);
  return (
    <>
      <PageTitle
        title="Local drafts"
        description={t(
          "Drafts are encrypted on this device and can only be opened after signing in to the original account.",
          "ड्राफ्ट इस डिवाइस पर एन्क्रिप्टेड हैं। केवल मूल खाते से साइन इन करने पर खुलते हैं।",
        )}
      >
        <ActionButton
          action={() =>
            syncDrafts(
              session,
              () => useSession.getState().session?.user.id === session.user.id,
            )
          }
        >
          {w("Retry sync")}
        </ActionButton>
      </PageTitle>
      <Panel>
        {drafts.error && <ErrorNotice error={drafts.error} />}
        {!drafts.data?.length ? (
          <Empty>
            {t(
              "Start a report to save a local draft.",
              "स्थानीय ड्राफ्ट के लिए रिपोर्ट शुरू करें।",
            )}
          </Empty>
        ) : (
          drafts.data.map((draft) => (
            <div className="work-list-row" key={draft.id}>
              <div>
                <Status value={draft.status} />
                <p>
                  {draft.status === "Submitted"
                    ? t(
                        "Server-confirmed report",
                        "सर्वर से पुष्टि की हुई रिपोर्ट",
                      )
                    : draft.payload.text.slice(0, 130) ||
                      t("Audio or evidence draft", "ऑडियो या साक्ष्य ड्राफ्ट")}
                </p>
                <small>
                  {formatDate(draft.updatedAt, session.organization.timezone)}
                </small>
                {draft.error && <p className="field-error">{draft.error}</p>}
              </div>
              <div className="work-actions">
                <Link
                  className="button button-outline"
                  to={
                    draft.status === "Submitted"
                      ? `/workspace/reports/${draft.reportId}`
                      : `/workspace/record?draft=${draft.id}`
                  }
                >
                  {w(draft.status === "Submitted" ? "Read report" : "Continue")}
                </Link>
                {!["Syncing", "Pending sync"].includes(draft.status) && (
                  <ActionButton action={() => deleteDraft(session, draft.id)}>
                    {t("Delete local copy", "स्थानीय प्रति हटाएँ")}
                  </ActionButton>
                )}
              </div>
            </div>
          ))
        )}
      </Panel>
    </>
  );
}
