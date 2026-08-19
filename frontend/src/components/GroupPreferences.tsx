import { useMutation } from "@tanstack/react-query";
import { Users, X } from "lucide-react";
import { FormEvent, useState } from "react";

import type { SearchOption } from "../api/chat";
import {
  buildGroupProfile,
  rerankGroupCandidates,
  type GroupPreferenceSummary,
  type GroupRerankItem,
} from "../api/preferences";

type GroupResult = GroupPreferenceSummary | {
  group: GroupPreferenceSummary;
  items: GroupRerankItem[];
};

interface GroupPreferencesProps {
  embedded?: boolean;
  candidates?: SearchOption[];
  onClose: () => void;
}

export function GroupPreferences({
  embedded = false,
  candidates = [],
  onClose,
}: GroupPreferencesProps) {
  const [groupId, setGroupId] = useState("");
  const [participantIds, setParticipantIds] = useState("");
  const group = useMutation<{ result: GroupResult }>({
    mutationFn: () => {
      const ids = participantIds.split(/[\s,]+/).map((value) => value.trim()).filter(Boolean);
      const usableCandidates = candidates.filter((candidate) => candidate.outbound && candidate.inbound);
      return usableCandidates.length
        ? rerankGroupCandidates(groupId.trim(), ids, usableCandidates)
        : buildGroupProfile(groupId.trim(), ids);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    group.mutate();
  }

  const result = group.data?.result;
  const summary = result && "group" in result ? result.group : result;
  const ranking = result && "items" in result ? result.items : [];
  const candidateById = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  return (
    <div className={embedded ? "group-embedded-host" : "modal-backdrop"} role={embedded ? undefined : "presentation"}>
      <section
        className={`group-modal${embedded ? " group-modal-embedded" : ""}`}
        role={embedded ? "region" : "dialog"}
        aria-modal={embedded ? undefined : true}
        aria-labelledby="group-title"
      >
        <header>
          <span><Users size={22} aria-hidden="true" /></span>
          <button type="button" aria-label="Закрыть групповую поездку" onClick={onClose}>
            {embedded ? <span>Вернуться в чат</span> : <X size={20} aria-hidden="true" />}
          </button>
        </header>
        <h2 id="group-title">Групповая поездка</h2>
        <p>
          Добавьте ID профилей участников. Ваш профиль включится автоматически.
          {candidates.length ? " Найденные варианты сразу получат групповой рейтинг." : ""}
        </p>
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
            {group.isPending
              ? "Ищем компромисс…"
              : candidates.length
                ? "Ранжировать для группы"
                : "Собрать групповой профиль"}
          </button>
        </form>
        {group.isError ? <p className="preference-error" role="alert">{group.error.message}</p> : null}
        {summary ? (
          <div className="group-result" aria-live="polite">
            <strong>Лучший баланс для группы</strong>
            <span>{consensusLabel(summary.consensus_score)} · {memberLabel(summary.member_count)}</span>
            {summary.highlights.map((highlight) => <p key={highlight}>{highlight}</p>)}
            {summary.conflicts.length ? <h3>Где мнения расходятся</h3> : null}
            {summary.conflicts.map((conflict) => (
              <p key={`${conflict.dimension}-${conflict.description}`}>{conflict.description}</p>
            ))}
            {ranking.length ? <h3>Общий рейтинг</h3> : null}
            {ranking
              .slice()
              .sort((left, right) => left.rank_after - right.rank_after)
              .map((item) => (
                <article className="group-ranking-item" key={item.candidate_id}>
                  <strong>№ {item.rank_after}</strong>
                  <span>
                    {candidateById.get(item.candidate_id)?.title ?? "Подходящий вариант"}
                  </span>
                  <small>{fitLabel(item.preference_score)}</small>
                  {item.reasons.slice(0, 2).map((reason) => <p key={reason}>{reason}</p>)}
                </article>
              ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function consensusLabel(score: number): string {
  if (score >= 0.75) return "Высокая согласованность";
  if (score >= 0.5) return "Средняя согласованность";
  return "Низкая согласованность";
}

function fitLabel(score: number): string {
  if (score >= 0.75) return "Отлично подходит группе";
  if (score >= 0.5) return "Хорошо подходит группе";
  return "Компромиссный вариант";
}

function memberLabel(count: number): string {
  const suffix = count % 10 === 1 && count % 100 !== 11
    ? "участник"
    : count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)
      ? "участника"
      : "участников";
  return `${count} ${suffix}`;
}
