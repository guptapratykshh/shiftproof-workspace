import { useEffect, useId, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mic, Square, Volume2 } from "lucide-react";
import { api, evidenceUrl, post } from "../../lib/api";
import {
  fileAttachment,
  uploadAttachment,
  type LocalAttachment,
} from "../../lib/offline";
import { usePreferences } from "../../lib/preferences";
import type { Job, ReportPayload } from "../../lib/types";
import { ErrorNotice } from "./UI";
import { useOnline } from "./VoicePlayback";

export type Conversation = {
  id: string;
  revision: number;
  department_id: string;
  status: string;
  state: {
    draft: ReportPayload;
    question: string;
    question_count: number;
    job_id?: string;
    speech_job_id?: string | null;
    check_error?: string;
    answer?: string;
    answer_type?: string;
    unresolved?: boolean;
    findings: {
      key: string;
      source_department: string;
      same_worker: boolean;
      finding: {
        title: string;
        category: string;
        difference?: number;
        difference_unit?: string;
      };
    }[];
  };
  turns: {
    id: string;
    role: string;
    text: string;
    revision: number;
    asset_id?: string;
  }[];
};

function signature(draft: ReportPayload) {
  const fields = {
    ...draft.fields,
    description: draft.fields.description || draft.text,
  };
  return JSON.stringify([
    draft.department_id,
    draft.team_id || null,
    draft.shift_id || null,
    draft.task_id || null,
    draft.text,
    !!draft.immediate_safety,
    Object.entries(fields)
      .filter(
        ([, value]) =>
          value != null &&
          value !== "" &&
          !(Array.isArray(value) && !value.length),
      )
      .sort(([a], [b]) => a.localeCompare(b)),
  ]);
}

export function useReportConversation(options: {
  draft: ReportPayload;
  language: string;
  inputRevision: number;
  initialId?: string | null;
  clarificationId?: string;
  onDraft: (draft: ReportPayload, conversation: Conversation) => void;
  onId: (id: string) => void;
}) {
  const latest = useRef(options);
  latest.current = options;
  const cache = useQueryClient();
  const online = useOnline();
  const [id, setId] = useState(options.initialId || null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const pendingRevision = useRef<number | null>(null);
  const applied = useRef("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (options.initialId && !id) setId(options.initialId);
  }, [options.initialId, id]);
  const query = useQuery({
    queryKey: ["report-conversation", id],
    enabled: !!id && online,
    queryFn: ({ signal }) =>
      api<Conversation>(`/report-conversations/${id}`, { signal }),
    refetchInterval: (query) =>
      query.state.data?.status === "processing" ? 1000 : false,
  });
  const conversation = query.data;
  useEffect(() => {
    if (
      !conversation ||
      !["ready", "awaiting_answer"].includes(conversation.status)
    )
      return;
    const key = `${conversation.id}:${conversation.revision}`;
    if (applied.current === key || pendingRevision.current === null) return;
    applied.current = key;
    if (pendingRevision.current === latest.current.inputRevision)
      latest.current.onDraft(conversation.state.draft, conversation);
  }, [conversation]);
  const dirty =
    !!conversation &&
    signature(options.draft) !== signature(conversation.state.draft);
  async function ensure() {
    const current = id
      ? cache.getQueryData<Conversation>(["report-conversation", id])
      : null;
    if (
      current &&
      current.department_id === latest.current.draft.department_id &&
      current.status !== "submitted"
    )
      return current;
    const created = await post<Conversation>("/report-conversations", {
      client_request_id: crypto.randomUUID(),
      draft: latest.current.draft,
      language: latest.current.language,
      clarification_id: latest.current.clarificationId || null,
    });
    if (mounted.current) {
      cache.setQueryData(["report-conversation", created.id], created);
      setId(created.id);
      latest.current.onId(created.id);
    }
    return created;
  }
  async function send(
    kind: "update" | "reply" | "edit" | "uncertain",
    text = "",
    assetId?: string,
  ) {
    setStarting(true);
    setError(null);
    pendingRevision.current = latest.current.inputRevision;
    const snapshot = latest.current.draft;
    try {
      const current = await ensure();
      const result = await post<Conversation>(
        `/report-conversations/${current.id}/turns`,
        {
          client_turn_id: crypto.randomUUID(),
          revision: current.revision,
          kind,
          text: assetId ? "" : text,
          asset_id: assetId || null,
          draft: kind === "reply" || kind === "uncertain" ? null : snapshot,
        },
      );
      if (mounted.current)
        cache.setQueryData(["report-conversation", result.id], result);
    } catch (cause) {
      if (mounted.current) setError(cause);
      throw cause;
    } finally {
      if (mounted.current) setStarting(false);
    }
  }
  async function open() {
    setStarting(true);
    setError(null);
    try {
      const current = await ensure();
      latest.current.onDraft(current.state.draft, current);
    } catch (cause) {
      setError(cause);
    } finally {
      setStarting(false);
    }
  }
  async function retry() {
    if (!conversation?.state.job_id) return;
    setError(null);
    try {
      await post(`/jobs/${conversation.state.job_id}/retry`);
      await query.refetch();
    } catch (cause) {
      setError(cause);
    }
  }
  return {
    conversation,
    dirty,
    starting,
    online,
    error: error || query.error,
    processing: starting || conversation?.status === "processing",
    send,
    open,
    retry,
    refresh: query.refetch,
  };
}

export type DialogueController = ReturnType<typeof useReportConversation>;

export function ConversationPanel({
  dialogue,
  recordingElsewhere = false,
  consent = false,
  onRecording,
  onSaveAttachment,
  onSaveAnswer,
  savedAnswer = "",
  savedRecording,
  onAnswerSent,
}: {
  dialogue: DialogueController;
  recordingElsewhere?: boolean;
  consent?: boolean;
  onRecording?: (recording: boolean) => void;
  onSaveAttachment: (attachment: LocalAttachment) => Promise<void>;
  onSaveAnswer?: (text: string) => void;
  savedAnswer?: string;
  savedRecording?: LocalAttachment;
  onAnswerSent?: () => void;
}) {
  const { t } = usePreferences();
  const { conversation: c, online, dirty, processing } = dialogue;
  const answerId = useId();
  const [typed, setTyped] = useState(false);
  const [answer, setAnswer] = useState("");
  const [recording, setRecording] = useState(false);
  const [startingMic, setStartingMic] = useState(false);
  const [sendingReply, setSendingReply] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [audio, setAudio] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [audioFailed, setAudioFailed] = useState(false);
  const [audioAttempt, setAudioAttempt] = useState(0);
  const player = useRef<HTMLAudioElement>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const cancelled = useRef(false);
  const mounted = useRef(true);
  const active =
    !!c?.state.question &&
    !dirty &&
    !recordingElsewhere &&
    !startingMic &&
    !recording &&
    !processing &&
    !sendingReply;
  useEffect(() => {
    setAnswer(savedAnswer);
    if (savedAnswer) setTyped(true);
  }, [savedAnswer]);
  const speech = useQuery({
    queryKey: ["conversation-speech", c?.state.speech_job_id],
    queryFn: ({ signal }) =>
      api<Job>(`/jobs/${c!.state.speech_job_id}`, { signal }),
    enabled: active && online && !!c?.state.speech_job_id,
    refetchInterval: (query) =>
      ["succeeded", "failed"].includes(query.state.data?.status || "")
        ? false
        : 1000,
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cancelled.current = true;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((track) => track.stop());
      player.current?.pause();
    };
  }, []);
  useEffect(() => {
    setAudio("");
    setBlocked(false);
    setAudioFailed(false);
    if (!active || !speech.data?.result.asset_id) {
      player.current?.pause();
      return;
    }
    let disposed = false,
      url = "";
    void evidenceUrl(speech.data.result.asset_id)
      .then((value) => {
        url = value;
        if (disposed) URL.revokeObjectURL(value);
        else setAudio(value);
      })
      .catch(() => {
        if (!disposed) setAudioFailed(true);
      });
    return () => {
      disposed = true;
      player.current?.pause();
      if (url) URL.revokeObjectURL(url);
    };
  }, [active, speech.data?.result.asset_id, c?.revision, audioAttempt]);
  useEffect(() => {
    if (audio && active)
      void player.current?.play().catch(() => setBlocked(true));
  }, [audio, active]);
  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(
      () => setElapsed((value) => value + 1),
      1000,
    );
    const stop = window.setTimeout(
      () => recorder.current?.state === "recording" && recorder.current.stop(),
      29000,
    );
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [recording]);
  const sendText = async (uncertain = false) => {
    try {
      await dialogue.send(
        uncertain ? "uncertain" : "reply",
        uncertain ? "I am not sure" : answer,
      );
      setAnswer("");
      setTyped(false);
      onSaveAnswer?.("");
      onAnswerSent?.();
    } catch (cause) {
      setError(cause);
    }
  };
  const sendRecording = async (attachment: LocalAttachment) => {
    setSendingReply(true);
    onRecording?.(true);
    player.current?.pause();
    try {
      const asset = await uploadAttachment(attachment, c!.department_id);
      if (mounted.current) {
        await dialogue.send("reply", "", asset.id);
        onAnswerSent?.();
      }
    } catch (cause) {
      if (mounted.current) setError(cause);
    } finally {
      if (mounted.current) {
        setSendingReply(false);
        onRecording?.(false);
      }
    }
  };
  const start = async () => {
    setError(null);
    player.current?.pause();
    if (!(consent || accepted)) {
      setError(
        t("Confirm recording consent first.", "पहले रिकॉर्डिंग की सहमति दें।"),
      );
      return;
    }
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        t(
          "Recording is unavailable. Type your answer.",
          "रिकॉर्डिंग उपलब्ध नहीं है। उत्तर लिखें।",
        ),
      );
      setTyped(true);
      return;
    }
    setStartingMic(true);
    onRecording?.(true);
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      if (!mounted.current) {
        stream.current.getTracks().forEach((track) => track.stop());
        return;
      }
      cancelled.current = false;
      const chunks: Blob[] = [];
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4"].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      const media = new MediaRecorder(
        stream.current,
        mimeType ? { mimeType } : undefined,
      );
      recorder.current = media;
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      media.onerror = () => {
        cancelled.current = true;
        stream.current?.getTracks().forEach((track) => track.stop());
        setRecording(false);
        onRecording?.(false);
        setError(
          t(
            "Recording failed. Retry or type your answer.",
            "रिकॉर्डिंग नहीं हुई। फिर कोशिश करें या लिखें।",
          ),
        );
      };
      media.onstop = () => {
        stream.current?.getTracks().forEach((track) => track.stop());
        if (!mounted.current) return;
        setRecording(false);
        onRecording?.(false);
        if (cancelled.current) return;
        void (async () => {
          const attachment = await fileAttachment(
            new Blob(chunks, { type: media.mimeType }),
            "clarification.webm",
            "audio",
            true,
          );
          await onSaveAttachment(attachment);
          if (!navigator.onLine) {
            setError(
              t(
                "Answer saved locally. Reconnect to check it.",
                "उत्तर सुरक्षित है। जाँचने के लिए कनेक्ट करें।",
              ),
            );
            return;
          }
          if (mounted.current) await sendRecording(attachment);
        })().catch((cause) => {
          if (mounted.current) setError(cause);
        });
      };
      media.start(250);
      setElapsed(0);
      setRecording(true);
    } catch {
      stream.current?.getTracks().forEach((track) => track.stop());
      onRecording?.(false);
      setError(
        t(
          "Microphone permission was denied. Type your answer below.",
          "माइक्रोफ़ोन की अनुमति नहीं मिली। नीचे उत्तर लिखें।",
        ),
      );
      setTyped(true);
    } finally {
      if (mounted.current) setStartingMic(false);
    }
  };
  if (!c && !dialogue.error && !processing) return null;
  return (
    <section
      className="report-conversation"
      aria-label={t("Report conversation", "रिपोर्ट पर बातचीत")}
    >
      <h3>{t("Let’s check your update", "आपका अपडेट जाँच लें")}</h3>
      {c && (
        <details className="conversation-history">
          <summary>{t("Conversation history", "बातचीत का इतिहास")}</summary>
          {c.turns.map((turn) => (
            <div className={`conversation-turn ${turn.role}`} key={turn.id}>
              <strong>
                {turn.role === "worker"
                  ? t("You", "आप")
                  : t("ShiftProof", "शिफ्टप्रूफ")}
              </strong>
              <p>{turn.text}</p>
            </div>
          ))}
        </details>
      )}
      {(processing || sendingReply) && (
        <p role="status">
          {t(
            "Checking your words against related updates…",
            "आपके शब्द संबंधित अपडेट से जाँचे जा रहे हैं…",
          )}
        </p>
      )}
      {dirty && !processing && (
        <p role="status">
          {t(
            "Your update changed. Check the updated words before sending.",
            "अपडेट बदला है। भेजने से पहले फिर जाँचें।",
          )}
        </p>
      )}
      {c?.state.question && !dirty && !processing && (
        <div className="conversation-question" role="status">
          <p>{c.state.question}</p>
          {audio && <audio ref={player} src={audio} preload="auto" />}
          <div className="work-actions">
            {audio && (
              <button
                type="button"
                className="button button-outline"
                disabled={
                  recording || startingMic || sendingReply || recordingElsewhere
                }
                onClick={() => {
                  if (player.current) {
                    player.current.currentTime = 0;
                    void player.current
                      .play()
                      .then(() => setBlocked(false))
                      .catch(() => setBlocked(true));
                  }
                }}
              >
                <Volume2 size={17} />
                {blocked
                  ? t("Tap to hear the question", "सवाल सुनने के लिए दबाएँ")
                  : t("Repeat question", "सवाल दोहराएँ")}
              </button>
            )}
            {!recording && (
              <button
                type="button"
                className="button button-primary"
                disabled={startingMic || sendingReply || recordingElsewhere}
                onClick={() => void start()}
              >
                <Mic size={18} />
                {t("Reply", "उत्तर बोलें")}
              </button>
            )}
            {recording && (
              <>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={() => recorder.current?.stop()}
                >
                  <Square size={18} />
                  {t("Stop reply", "उत्तर रोकें")} · {elapsed}/29
                </button>
                <button
                  type="button"
                  className="button button-outline"
                  onClick={() => {
                    cancelled.current = true;
                    recorder.current?.stop();
                  }}
                >
                  {t("Cancel", "रद्द करें")}
                </button>
              </>
            )}
            <button
              type="button"
              className="button button-outline"
              disabled={
                recording || startingMic || sendingReply || recordingElsewhere
              }
              onClick={() => setTyped(true)}
            >
              {t("Type answer", "उत्तर लिखें")}
            </button>
            <button
              type="button"
              className="text-button"
              disabled={
                !online ||
                recording ||
                startingMic ||
                sendingReply ||
                recordingElsewhere
              }
              onClick={() => void sendText(true)}
            >
              {t("I’m not sure", "मुझे निश्चित नहीं है")}
            </button>
          </div>
          {savedRecording && (
            <button
              type="button"
              className="button button-outline"
              disabled={!online || recording || sendingReply}
              onClick={() => void sendRecording(savedRecording)}
            >
              {t("Check saved answer", "सुरक्षित उत्तर जाँचें")}
            </button>
          )}
          {!consent && (
            <label className="check-field">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              {t(
                "I consent to recording my answer for authorized review.",
                "मैं अधिकृत समीक्षा के लिए उत्तर रिकॉर्ड करने की सहमति देता/देती हूँ।",
              )}
            </label>
          )}
          {typed && (
            <div className="work-stack">
              <div className="form-field">
                <label htmlFor={answerId}>{t("Your answer", "आपका उत्तर")}</label>
                <textarea
                  id={answerId}
                  rows={3}
                  value={answer}
                  maxLength={5000}
                  onChange={(event) => {
                    setAnswer(event.target.value);
                    onSaveAnswer?.(event.target.value);
                  }}
                />
              </div>
              <button
                type="button"
                className="button button-primary"
                disabled={
                  !answer.trim() ||
                  !online ||
                  sendingReply ||
                  recording ||
                  startingMic ||
                  recordingElsewhere
                }
                onClick={() => void sendText()}
              >
                {t("Check my answer", "मेरा उत्तर जाँचें")}
              </button>
            </div>
          )}
          {audioFailed && (
            <button
              type="button"
              className="button button-outline"
              disabled={!online || recording || sendingReply}
              onClick={() => setAudioAttempt((value) => value + 1)}
            >
              {t("Try question audio again", "सवाल की आवाज़ फिर चलाएँ")}
            </button>
          )}
          {(audioFailed ||
            speech.isError ||
            speech.data?.status === "failed" ||
            !c.state.speech_job_id) && (
            <p className="work-note">
              {t(
                "Spoken playback is unavailable. Read the question and reply here.",
                "आवाज़ में सवाल उपलब्ध नहीं है। पढ़कर यहीं उत्तर दें।",
              )}
            </p>
          )}
        </div>
      )}
      {c?.status === "ready" && !dirty && (
        <div role="status" className="conversation-summary">
          <strong>
            {t("Ready for your review", "आपकी समीक्षा के लिए तैयार")}
          </strong>
          {c.state.draft.fields.quantity != null && (
            <p className="conversation-final-count">
              <strong>
                {t("Final count", "अंतिम गिनती")}:{" "}
                {c.state.draft.fields.quantity}{" "}
                {c.state.draft.fields.unit || ""}
              </strong>
              {c.state.draft.fields.quantity_stage && (
                <>
                  {" "}
                  ·{" "}
                  {c.state.draft.fields.quantity_stage === "received"
                    ? t("Received", "प्राप्त")
                    : c.state.draft.fields.quantity_stage === "manufactured"
                      ? t("Manufactured", "निर्मित")
                      : t("Dispatched", "भेजे गए")}
                </>
              )}
              {c.state.draft.fields.transfer_reference && (
                <> · {c.state.draft.fields.transfer_reference}</>
              )}
            </p>
          )}
          <p>{c.state.draft.text}</p>
          {!!c.state.findings.length && (
            <p>
              {t(
                "The difference is recorded. After you send, the other reporter and supervisors will be asked to verify.",
                "अंतर दर्ज है। भेजने के बाद दूसरे रिपोर्टर और पर्यवेक्षक से जाँच कराई जाएगी।",
              )}
            </p>
          )}
          {c.state.unresolved && (
            <p>
              {t(
                "Some details remain uncertain and will need supervisor review.",
                "कुछ जानकारी अनिश्चित है; पर्यवेक्षक की समीक्षा आवश्यक होगी।",
              )}
            </p>
          )}
        </div>
      )}
      {c?.status === "unavailable" && (
        <div className="work-warning">
          <p>{c.state.check_error}</p>
          <button
            type="button"
            className="button button-outline"
            onClick={() => void dialogue.retry()}
            disabled={!online}
          >
            {t("Retry checking", "फिर जाँचें")}
          </button>
          <p>
            {t(
              "You can also review the fields manually and check the update again.",
              "फ़ील्ड स्वयं जाँचकर अपडेट दोबारा जाँच सकते हैं।",
            )}
          </p>
        </div>
      )}
      {!online && (
        <p role="status">
          {t(
            "Offline: answers stay on this device. Checking needs a connection.",
            "ऑफ़लाइन: उत्तर डिवाइस पर सुरक्षित हैं। जाँच के लिए कनेक्शन चाहिए।",
          )}
        </p>
      )}
      {!!(error || dialogue.error) && (
        <ErrorNotice error={error || dialogue.error} />
      )}
    </section>
  );
}
