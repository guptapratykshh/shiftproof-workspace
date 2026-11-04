import { forwardRef, useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import { usePreferences } from "../lib/preferences";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
  wide?: boolean;
};

export const FormField = forwardRef<HTMLInputElement, Props>(function FormField(
  { label, error, hint, wide, type, id, ...props },
  ref,
) {
  const { t } = usePreferences();
  const [visible, setVisible] = useState(false);
  const secret = type === "password";
  return (
    <div className={`form-field${wide ? " field-wide" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <div className="input-wrap">
        <input
          {...props}
          id={id}
          ref={ref}
          type={secret && visible ? "text" : type}
          aria-invalid={!!error}
          aria-describedby={
            error ? `${id}-error` : hint ? `${id}-hint` : undefined
          }
          className={secret ? "secret-input" : undefined}
        />
        {secret && (
          <button
            type="button"
            className="password-toggle"
            aria-label={
              visible ? t("Hide secret", "छिपाएँ") : t("Show secret", "दिखाएँ")
            }
            aria-pressed={visible}
            onClick={() => setVisible(!visible)}
          >
            {visible ? <EyeOff size={19} /> : <Eye size={19} />}
          </button>
        )}
      </div>
      {error ? (
        <p id={`${id}-error`} className="field-error">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="field-hint">
          {hint}
        </p>
      ) : null}
    </div>
  );
});
