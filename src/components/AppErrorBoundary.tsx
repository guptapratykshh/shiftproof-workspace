import { Component, type ReactNode } from "react";
import { usePreferences } from "../lib/preferences";

function RecoveryMessage() {
  const { t } = usePreferences();
  return (
    <main className="login-main" role="alert">
      <h1>{t("This page could not be opened.", "यह पेज नहीं खुल सका।")}</h1>
      <p className="work-note">
        {t(
          "Your saved drafts are still on this device. Check your connection, then try opening the page again.",
          "आपके सहेजे गए ड्राफ्ट इस डिवाइस पर हैं। कनेक्शन जाँचें, फिर पेज दोबारा खोलें।",
        )}
      </p>
      <button
        className="button button-primary"
        onClick={() => window.location.reload()}
      >
        {t("Try again", "दोबारा कोशिश करें")}
      </button>{" "}
      <a className="button button-secondary" href="/workspace/drafts">
        {t("Open saved drafts", "सहेजे गए ड्राफ्ट खोलें")}
      </a>
    </main>
  );
}

export class AppErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <RecoveryMessage /> : this.props.children;
  }
}
