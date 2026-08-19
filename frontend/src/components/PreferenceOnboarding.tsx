import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Clock3, Sparkles, X } from "lucide-react";
import { useState } from "react";

import {
  completeColdStart,
  getColdStartQuestions,
  getPreferenceProfile,
} from "../api/preferences";
import type { ColdStartChoice, ColdStartOption } from "../api/preferences";

interface PreferenceOnboardingProps {
  isAuthenticated: boolean;
  onClose: () => void;
  onCompleted: (message: string) => void;
  onRequireAuth: () => void;
}

type Stage = "intro" | "questions" | "complete";

export function PreferenceOnboarding({
  isAuthenticated,
  onClose,
  onCompleted,
  onRequireAuth,
}: PreferenceOnboardingProps) {
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("intro");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [choices, setChoices] = useState<ColdStartChoice[]>([]);
  const profileQuery = useQuery({
    queryKey: ["preference-profile"],
    queryFn: getPreferenceProfile,
    enabled: isAuthenticated,
  });
  const questionsQuery = useQuery({
    queryKey: ["cold-start-questions", 4],
    queryFn: getColdStartQuestions,
    enabled: stage === "questions",
    staleTime: Number.POSITIVE_INFINITY,
  });
  const completion = useMutation({
    mutationFn: (answers: ColdStartChoice[]) =>
      completeColdStart(
        answers,
        profileQuery.data?.profile?.cold_start_completed ?? false,
      ),
    onSuccess: (result) => {
      queryClient.setQueryData(["preference-profile"], { profile: result.profile });
      setStage("complete");
      onCompleted("Предпочтения сохранены — Джарвелл учтёт их в следующих вариантах.");
    },
  });

  const questions = questionsQuery.data?.questions ?? [];
  const currentQuestion = questions[questionIndex];
  const isRecalibration = profileQuery.data?.profile?.cold_start_completed ?? false;

  function selectOption(selectedOptionId: string) {
    if (!currentQuestion || completion.isPending) {
      return;
    }
    const nextChoices = [
      ...choices,
      {
        question_id: currentQuestion.id,
        selected_option_id: selectedOptionId,
      },
    ];
    setChoices(nextChoices);
    if (questionIndex + 1 >= questions.length) {
      completion.mutate(nextChoices);
    } else {
      setQuestionIndex((current) => current + 1);
    }
  }

  function previousQuestion() {
    if (questionIndex === 0) {
      setStage("intro");
      return;
    }
    setQuestionIndex((current) => current - 1);
    setChoices((current) => current.slice(0, -1));
  }

  return (
    <div className="modal-backdrop preference-backdrop" role="presentation">
      <section
        className="preference-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="preference-title"
      >
        <header className="preference-modal-header">
          {stage === "questions" ? (
            <button type="button" aria-label="Предыдущий вопрос" onClick={previousQuestion}>
              <ArrowLeft size={20} aria-hidden="true" />
            </button>
          ) : (
            <span />
          )}
          <button type="button" aria-label="Закрыть настройку" onClick={onClose}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        {stage === "intro" ? (
          <div className="preference-intro">
            <span className="preference-spark"><Sparkles size={28} /></span>
            <p className="preference-kicker">Персональный подбор</p>
            <h2 id="preference-title">
              {isRecalibration ? "Обновим поездки под тебя" : "Настроим поездки под тебя"}
            </h2>
            <div className="preference-intro-stats">
              <strong>4 быстрых выбора</strong>
              <span><Clock3 size={17} aria-hidden="true" />≈ 20 секунд</span>
            </div>
            <p>
              Выбери более подходящий вариант в каждой паре. Цену, время,
              пересадки и транспорт посчитает backend — никаких ручных настроек.
            </p>
            {profileQuery.isError ? (
              <p className="preference-error" role="alert">Не удалось проверить текущий профиль.</p>
            ) : null}
            <button
              className="preference-primary"
              type="button"
              disabled={isAuthenticated && profileQuery.isLoading}
              onClick={() => {
                if (!isAuthenticated) {
                  onRequireAuth();
                  return;
                }
                setStage("questions");
              }}
            >
              {isAuthenticated && profileQuery.isLoading ? "Загружаем…" : "Начать"}
            </button>
          </div>
        ) : null}

        {stage === "questions" ? (
          <div className="preference-question-stage">
            <div className="preference-progress" aria-label={`Вопрос ${questionIndex + 1} из 4`}>
              <span style={{ width: `${((questionIndex + 1) / 4) * 100}%` }} />
            </div>
            {questionsQuery.isLoading ? <p role="status">Готовим варианты…</p> : null}
            {questionsQuery.isError ? (
              <div className="preference-error" role="alert">
                <p>{questionsQuery.error.message}</p>
                <button type="button" onClick={() => void questionsQuery.refetch()}>Повторить</button>
              </div>
            ) : null}
            {currentQuestion ? (
              <>
                <p className="preference-step">Выбор {questionIndex + 1} из {questions.length}</p>
                <h2 id="preference-title">{currentQuestion.prompt}</h2>
                <div className="preference-options">
                  <OptionCard option={currentQuestion.left} onSelect={selectOption} />
                  <span className="preference-or">или</span>
                  <OptionCard option={currentQuestion.right} onSelect={selectOption} />
                </div>
              </>
            ) : null}
            {completion.isPending ? <p className="preference-saving" role="status">Собираем профиль…</p> : null}
            {completion.isError ? (
              <div className="preference-error" role="alert">
                <p>{completion.error.message}</p>
                <button type="button" onClick={() => completion.mutate(choices)}>Повторить</button>
              </div>
            ) : null}
          </div>
        ) : null}

        {stage === "complete" ? (
          <div className="preference-complete">
            <span><Check size={32} aria-hidden="true" /></span>
            <p className="preference-kicker">Профиль готов</p>
            <h2 id="preference-title">Теперь варианты будут ранжироваться под тебя</h2>
            <p>Профиль уже привязан к аккаунту и будет применяться в Trip Rescue.</p>
            <button className="preference-primary" type="button" onClick={onClose}>Готово</button>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function OptionCard({
  option,
  onSelect,
}: {
  option: ColdStartOption;
  onSelect: (id: string) => void;
}) {
  return (
    <button
      className="preference-option"
      type="button"
      onClick={() => onSelect(option.id)}
      aria-label={`${option.title}: ${option.subtitle}, ${formatPrice(option.total_price)}`}
    >
      <strong>{option.title}</strong>
      <span>{option.subtitle}</span>
      <small>{transportLabel(option.transport)} · {formatDuration(option.duration_minutes)}</small>
      <b>{formatPrice(option.total_price)}</b>
      <em>{option.transfers === 0 ? "Без пересадок" : `${option.transfers} пересадка`}</em>
    </button>
  );
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat("ru-RU").format(price) + " ₽";
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `${hours ? `${hours}ч ` : ""}${rest ? `${rest}мин` : ""}`.trim();
}

function transportLabel(transport: string): string {
  return ({ bus: "Автобус", train: "Поезд", flight: "Самолёт", suburban_train: "Электричка" } as Record<string, string>)[transport] ?? transport;
}
