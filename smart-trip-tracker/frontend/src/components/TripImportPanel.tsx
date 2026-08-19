import { Braces, ChevronDown, Plus } from "lucide-react";
import { FormEvent } from "react";

interface TripImportPanelProps {
  compact?: boolean;
  error: Error | null;
  isPending: boolean;
  resultJson: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function TripImportPanel({
  compact = false,
  error,
  isPending,
  resultJson,
  onChange,
  onSubmit,
}: TripImportPanelProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  const form = (
    <form className="import-form" onSubmit={handleSubmit}>
      <div className="field-heading">
        <label htmlFor="negotiation-result">Данные найденной поездки</label>
        <span>Формат JSON</span>
      </div>
      <textarea
        id="negotiation-result"
        required
        spellCheck={false}
        value={resultJson}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="import-actions">
        <button className="primary-button" disabled={isPending} type="submit">
          <Plus size={18} aria-hidden="true" />
          {isPending ? "Добавляем поездку…" : "Начать новое отслеживание"}
        </button>
        <p>Стоимость обновится после каждой новой проверки.</p>
      </div>
      {error ? (
        <p className="error-message" role="alert">
          {error.message}
        </p>
      ) : null}
    </form>
  );

  if (compact) {
    return (
      <details className="import-details">
        <summary>
          <span className="summary-icon">
            <Braces size={18} aria-hidden="true" />
          </span>
          <span>
            <strong>Добавить другую поездку</strong>
            <small>Импортировать новый результат поиска</small>
          </span>
          <ChevronDown className="summary-chevron" size={18} aria-hidden="true" />
        </summary>
        {form}
      </details>
    );
  }

  return (
    <section className="import-card" aria-labelledby="import-title">
      <div className="import-copy">
        <span className="import-icon">
          <Braces size={23} aria-hidden="true" />
        </span>
        <div>
          <h2 id="import-title">Добавьте найденную поездку</h2>
          <p>
            Вставьте результат поиска — мы сохраним текущую цену и начнём
            собирать историю.
          </p>
        </div>
      </div>
      {form}
    </section>
  );
}
