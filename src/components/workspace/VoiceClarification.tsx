import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { post } from "../../lib/api";
import {
  deleteDraft,
  loadDrafts,
  saveDraft,
  type LocalAttachment,
} from "../../lib/offline";
import { usePreferences } from "../../lib/preferences";
import { useSession } from "../../lib/session";
import type { Clarification, Report, ReportPayload } from "../../lib/types";
import { ConversationPanel, useReportConversation } from "./ReportConversation";
import { ErrorNotice } from "./UI";

export function VoiceClarification({
  item,
  report,
}: {
  item: Clarification;
  report: Report;
}) {
  const session = useSession((state) => state.session)!;
  const { t } = usePreferences();
  const cache = useQueryClient();
  const version = report.versions!.find(
    (value) => value.number === report.latest_version,
  )!;
  const localId = `clarification-${item.id}`;
  const [conversationId, setId] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [attachment, setAttachment] = useState<LocalAttachment | undefined>();
  const [confirmed, setConfirmed] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [draft, setDraft] = useState<ReportPayload>(() => ({
    client_request_id: crypto.randomUUID(),
    department_id: report.department_id,
    team_id: report.team_id,
    shift_id: report.shift_id,
    occurred_at: report.occurred_at,
    text: version.text,
    fields: version.fields,
    task_id: null,
    transcript_id: null,
    extraction_id: null,
    evidence_ids: [],
    immediate_safety: false,
    confirmed: true,
  }));
  const dialogue = useReportConversation({
    draft,
    language: session.user.preferences.speech_language || "hi-IN,en-IN",
    inputRevision: 0,
    initialId: conversationId,
    clarificationId: item.id,
    onId: setId,
    onDraft: (value, conversation) => {
      setDraft({
        ...value,
        conversation_id: conversation.id,
        conversation_revision: conversation.revision,
      });
      setConfirmed(false);
    },
  });
  const save = (text = answer, recording = attachment) =>
    saveDraft(session, {
      id: localId,
      status: "Saved locally",
      updatedAt: new Date().toISOString(),
      clarificationId: item.id,
      sourceReportId: report.id,
      payload: { ...draft, conversation_id: conversationId },
      pendingAnswer: text,
      pendingVoiceAnswer: recording,
      attachments: recording ? [recording] : [],
    });
  useEffect(() => {
    let cancelled = false;
    void loadDrafts(session)
      .then((entries) => {
        const saved = entries.find((value) => value.id === localId);
        if (saved && !cancelled) {
          setDraft(saved.payload);
          setId(saved.payload.conversation_id || null);
          setAnswer(saved.pendingAnswer || "");
          setAttachment(saved.pendingVoiceAnswer);
        }
      })
      .catch(setError);
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    if (!conversationId) return;
    const timeout = setTimeout(() => {
      void save().catch(setError);
    }, 500);
    return () => clearTimeout(timeout);
  }, [draft, conversationId, answer, attachment]);
  const finish = async () => {
    if (!confirmed || !dialogue.conversation) return;
    setSending(true);
    setError(null);
    try {
      await post(`/clarifications/${item.id}/response`, {
        response_type: dialogue.conversation.state.answer_type || "uncertain",
        response: dialogue.conversation.state.answer || "I am not sure",
        conversation_id: dialogue.conversation.id,
        conversation_revision: dialogue.conversation.revision,
      });
      await deleteDraft(session, localId);
      await cache.invalidateQueries({ queryKey: ["report"] });
      await cache.invalidateQueries({ queryKey: ["conflicts"] });
    } catch (cause) {
      setError(cause);
    } finally {
      setSending(false);
    }
  };
  return (
    <div className="work-stack">
      {!dialogue.conversation && (
        <button
          type="button"
          className="button button-outline"
          disabled={!dialogue.online || dialogue.starting}
          onClick={() => void dialogue.open()}
        >
          {t("Respond", "उत्तर दें")}
        </button>
      )}
      <ConversationPanel
        dialogue={dialogue}
        savedAnswer={answer}
        savedRecording={attachment}
        onSaveAnswer={setAnswer}
        onSaveAttachment={async (value) => {
          setAttachment(value);
          await save(answer, value);
        }}
        onAnswerSent={() => {
          setAnswer("");
          setAttachment(undefined);
        }}
      />
      {dialogue.conversation?.status === "ready" && !dialogue.dirty && (
        <>
          <p className="work-note">
            {t(
              "This answer is added to the review history. Your original submitted report stays unchanged.",
              "यह उत्तर समीक्षा के इतिहास में जुड़ेगा। मूल जमा रिपोर्ट नहीं बदलेगी।",
            )}
          </p>
          <label className="check-field">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            {t("I reviewed my answer.", "मैंने अपना उत्तर जाँच लिया है।")}
          </label>
          <button
            type="button"
            className="button button-primary"
            disabled={!confirmed || !dialogue.online || sending}
            onClick={() => void finish()}
          >
            {t("Confirm and send answer", "पुष्टि करके उत्तर भेजें")}
          </button>
        </>
      )}
      {!!error && <ErrorNotice error={error} />}
    </div>
  );
}
