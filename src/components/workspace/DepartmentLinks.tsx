import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "../../lib/api";
import { usePreferences } from "../../lib/preferences";
import { useSession } from "../../lib/session";
import { useCatalog } from "./Workspace";
import { ActionButton, ErrorNotice, Panel } from "./UI";

type DepartmentLink = {
  id: string;
  source_department_id: string;
  receiving_department_id: string;
  source_name: string;
  receiving_name: string;
  active: boolean;
};

export function DepartmentLinks() {
  const { t } = usePreferences();
  const { departments } = useCatalog();
  const owner = useSession(
    (state) => state.session?.user.role === "organization",
  );
  const [source, setSource] = useState("");
  const [receiving, setReceiving] = useState("");
  const links = useQuery({
    queryKey: ["department-links"],
    enabled: owner,
    queryFn: () => api<DepartmentLink[]>("/department-links"),
  });
  if (!owner) return null;
  return (
    <Panel
      title={t("Linked department transfers", "जुड़े विभागों के ट्रांसफ़र")}
    >
      <p className="work-note">
        {t(
          "Compare matching batch, order and transfer counts between these departments. The receiving department supervises verification. Only relevant comparison facts are shared.",
          "इन विभागों में समान बैच, ऑर्डर और ट्रांसफ़र की गिनती मिलाएँ। प्राप्त करने वाला विभाग जाँच का ज़िम्मेदार होगा। केवल संबंधित तथ्य साझा होते हैं।",
        )}
      </p>
      <div className="work-form-grid">
        <label className="form-field">
          {t("From department", "भेजने वाला विभाग")}
          <select
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            <option value="">{t("Choose department", "विभाग चुनें")}</option>
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
          {t("Receiving department", "प्राप्त करने वाला विभाग")}
          <select
            value={receiving}
            onChange={(event) => setReceiving(event.target.value)}
          >
            <option value="">{t("Choose department", "विभाग चुनें")}</option>
            {departments.data
              ?.filter((d) => d.active && d.id !== source)
              .map((d) => (
                <option value={d.id} key={d.id}>
                  {d.name}
                </option>
              ))}
          </select>
        </label>
      </div>
      <fieldset
        disabled={!source || !receiving || source === receiving}
        style={{ border: 0, padding: 0 }}
      >
        <ActionButton
          action={async () => {
            await post("/department-links", {
              source_department_id: source,
              receiving_department_id: receiving,
              active: true,
            });
            await links.refetch();
            setSource("");
            setReceiving("");
          }}
        >
          {t("Link departments", "विभाग जोड़ें")}
        </ActionButton>
      </fieldset>
      {links.error && <ErrorNotice error={links.error} />}
      {links.data?.map((link) => (
        <div className="work-list-row" key={link.id}>
          <p>
            {link.source_name} → {link.receiving_name}
          </p>
          <ActionButton
            action={async () => {
              await post("/department-links", {
                source_department_id: link.source_department_id,
                receiving_department_id: link.receiving_department_id,
                active: !link.active,
              });
              await links.refetch();
            }}
          >
            {link.active
              ? t("Disable link", "लिंक बंद करें")
              : t("Enable link", "लिंक चालू करें")}
          </ActionButton>
        </div>
      ))}
    </Panel>
  );
}
