import type { ReportFields } from "../../lib/types";
import { usePreferences } from "../../lib/preferences";
import { useWords } from "./UI";

export const claimTextFields = [
  { key: "order", label: "Order ID" },
  { key: "task_reference", label: "Task ID / name" },
  { key: "product", label: "Product" },
  { key: "reference_period", label: "Reporting period" },
  { key: "observation_time", label: "Observation time in source" },
] as const;
export const claimStatusFields = [
  { key: "quantity_basis", label: "Counting basis", values: ["total", "additional"] },
  { key: "quality_status", label: "Quality status", values: ["passed", "rejected", "pending"] },
  { key: "dispatch_status", label: "Dispatch status", values: ["dispatched", "pending"] },
  { key: "machine_status", label: "Machine status", values: ["operational", "maintenance", "stopped", "failed"] },
  { key: "task_status", label: "Task status", values: ["completed", "pending"] },
] as const;

export function ClaimFields({ fields, setField }: {
  fields: ReportFields;
  setField: (key: keyof ReportFields, value: string) => void;
}) {
  const w = useWords();
  const { t } = usePreferences();
  return <>
    {claimTextFields.map(({ key, label }) => <label className="form-field" key={key}>
      {w(label)}
      <input value={fields[key] ?? ""} maxLength={200} onChange={event => setField(key, event.target.value)} />
    </label>)}
    {claimStatusFields.map(({ key, label, values }) => <label className="form-field" key={key}>
      {w(label)}
      <select value={fields[key] ?? ""} onChange={event => setField(key, event.target.value)}>
        <option value="">{t("Not stated / unsure", "नहीं बताया / अनिश्चित")}</option>
        {values.map(value => <option key={value} value={value}>{w(value)}</option>)}
      </select>
    </label>)}
    <p className="work-note">{t(
      "Use the period and time the update describes. Incoming workers can report on an earlier shift. Mark extra production as additional; leave uncertain facts blank.",
      "अपडेट में बताए गए समय और अवधि का उपयोग करें। आने वाले कर्मचारी पिछली शिफ्ट की जानकारी दे सकते हैं। अतिरिक्त उत्पादन को अतिरिक्त चुनें; अनिश्चित जानकारी खाली रखें।",
    )}</p>
  </>;
}
