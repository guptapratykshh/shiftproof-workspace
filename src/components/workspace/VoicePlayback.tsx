import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Headphones } from "lucide-react";
import { api, evidenceUrl, post } from "../../lib/api";
import { usePreferences } from "../../lib/preferences";
import type { Job } from "../../lib/types";
import { ErrorNotice } from "./UI";

export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

// The parent keys this component by the exact input/version. An edit unmounts
// obsolete audio and prevents a late response from being played as current.
export function VoicePlayback({
  endpoint,
  body,
  label,
  disabled = false,
}: {
  endpoint: string;
  body: unknown;
  label: string;
  disabled?: boolean;
}) {
  const { t } = usePreferences();
  const online = useOnline();
  const [jobId, setJobId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [audio, setAudio] = useState("");
  const [downloadAttempt, setDownloadAttempt] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const mounted = useRef(true);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
    };
  }, []);
  const job = useQuery({
    queryKey: ["voice-playback", jobId],
    queryFn: ({ signal }) => api<Job>(`/jobs/${jobId}`, { signal }),
    enabled: !!jobId && online,
    refetchInterval: (query) =>
      ["succeeded", "failed"].includes(query.state.data?.status || "")
        ? false
        : 1500,
    retry: 1,
  });
  useEffect(() => {
    const assetId = job.data?.result.asset_id;
    if (!assetId) return;
    let cancelled = false;
    let url = "";
    setDownloading(true);
    void evidenceUrl(assetId)
      .then((value) => {
        url = value;
        if (cancelled) URL.revokeObjectURL(value);
        else setAudio(value);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause);
      })
      .finally(() => {
        if (!cancelled) setDownloading(false);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [job.data?.result.asset_id, downloadAttempt]);
  const pending =
    !!jobId && !["succeeded", "failed"].includes(job.data?.status || "");
  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      if (job.data?.status === "succeeded" && job.data.result.asset_id) {
        // Retry the private download without paying to synthesize it again.
        setDownloadAttempt((value) => value + 1);
      } else if (job.data?.status === "failed") {
        await post(`/jobs/${jobId}/retry`);
        await job.refetch();
      } else {
        request.current = new AbortController();
        const value = await api<Job>(endpoint, {
          method: "POST",
          body: JSON.stringify(body),
          signal: request.current.signal,
        });
        if (mounted.current) setJobId(value.id);
      }
    } catch (cause) {
      if (mounted.current) setError(cause);
    } finally {
      if (mounted.current) setStarting(false);
    }
  };
  return (
    <div className="voice-playback">
      {!audio && (
        <button
          type="button"
          className="button button-outline"
          disabled={
            disabled ||
            !online ||
            starting ||
            downloading ||
            (pending && !job.isError)
          }
          onClick={() => void (job.isError ? job.refetch() : start())}
        >
          <Headphones size={18} />
          {starting || downloading || (pending && !job.isError)
            ? t("Preparing audio…", "ऑडियो तैयार हो रहा है…")
            : error || job.data?.status === "failed" || job.isError
              ? t("Try listening again", "दोबारा सुनें")
              : label}
        </button>
      )}
      {!online && (
        <p className="work-note">
          {t(
            "Listening needs a connection. You can still read and review.",
            "सुनने के लिए कनेक्शन चाहिए। आप पढ़कर जाँच सकते हैं।",
          )}
        </p>
      )}
      {(starting || downloading || pending) && !job.isError && (
        <p className="work-note" role="status">
          {t(
            "Preparing spoken playback. You can keep reading while you wait.",
            "सुनने के लिए ऑडियो बन रहा है। तब तक आप पढ़ सकते हैं।",
          )}
        </p>
      )}
      {!!(error || job.error || job.data?.error) && (
        <ErrorNotice error={error || job.error || job.data?.error} />
      )}
      {audio && (
        <>
          <audio controls preload="metadata" src={audio} aria-label={label} />
          <p className="work-note">
            {t(
              "Press play to listen. Editing the update clears this audio.",
              "सुनने के लिए प्ले दबाएँ। अपडेट बदलने पर यह ऑडियो हट जाएगा।",
            )}
          </p>
          {job.data?.result.script && (
            <details>
              <summary>{t("Words in this audio", "इस ऑडियो के शब्द")}</summary>
              <p className="voice-script">{job.data.result.script}</p>
            </details>
          )}
        </>
      )}
    </div>
  );
}
