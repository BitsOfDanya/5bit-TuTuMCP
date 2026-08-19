import { useMutation } from "@tanstack/react-query";
import { Users, X } from "lucide-react";
import { FormEvent, useState } from "react";

import { buildGroupProfile } from "../api/preferences";

interface GroupPreferencesProps {
  onClose: () => void;
}

export function GroupPreferences({ onClose }: GroupPreferencesProps) {
  const [groupId, setGroupId] = useState("");
  const [participantIds, setParticipantIds] = useState("");
  const group = useMutation({
    mutationFn: () =>
      buildGroupProfile(
        groupId.trim(),
        participantIds.split(/[\s,]+/).map((value) => value.trim()).filter(Boolean),
      ),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    group.mutate();
  }

  const summary = group.data?.result;
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="group-modal" role="dialog" aria-modal="true" aria-labelledby="group-title">
        <header>
          <span><Users size={22} aria-hidden="true" /></span>
          <button type="button" aria-label="Закрыть групповую поездку" onClick={onClose}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        <h2 id="group-title">Групповая поездка</h2>
        <p>Добавьте ID профилей участников. Ваш профиль включится автоматически.</p>
        <form onSubmit={submit}>
          <label htmlFor="group-name">Название группы</label>
          <input
            id="group-name"
            value={groupId}
            onChange={(event) => setGroupId(event.target.value)}
            placeholder="Казань с друзьями"
            required
          />
          <label htmlFor="participant-ids">ID участников через запятую</label>
          <textarea
            id="participant-ids"
            value={participantIds}
            onChange={(event) => setParticipantIds(event.target.value)}
            placeholder="profile-id-2, profile-id-3"
            required
          />
          <button type="submit" disabled={group.isPending}>
            {group.isPending ? "Ищем компромисс…" : "Собрать групповой профиль"}
          </button>
        </form>
        {group.isError ? <p className="preference-error" role="alert">{group.error.message}</p> : null}
        {summary ? (
          <div className="group-result" aria-live="polite">
            <strong>Consensus {Math.round(summary.consensus_score * 100)}%</strong>
            <span>{summary.member_count} участника</span>
            {summary.highlights.map((highlight) => <p key={highlight}>{highlight}</p>)}
            {summary.conflicts.length ? <h3>Где мнения расходятся</h3> : null}
            {summary.conflicts.map((conflict) => (
              <p key={`${conflict.dimension}-${conflict.description}`}>{conflict.description}</p>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
