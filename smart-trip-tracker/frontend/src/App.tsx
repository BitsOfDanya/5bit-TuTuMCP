import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createTracking,
  listTrackings,
  recordNegotiation,
  refreshTracking,
  stopTracking,
} from "./api";
import { TrackerHeader } from "./components/TrackerHeader";
import { TrackingDashboard } from "./components/TrackingDashboard";
import { TripImportPanel } from "./components/TripImportPanel";
import { initialNegotiationJson, parseNegotiationResult } from "./negotiation";
import type { TrackingList, TripTracking } from "./types";

export function App() {
  const queryClient = useQueryClient();
  const [resultJson, setResultJson] = useState(initialNegotiationJson);
  const trackingsQuery = useQuery({ queryKey: ["trackings"], queryFn: listTrackings });
  const tracking = trackingsQuery.data?.items[0] ?? null;

  function saveTracking(updated: TripTracking) {
    queryClient.setQueryData<TrackingList>(["trackings"], (current) => ({
      items: [updated, ...(current?.items.filter((item) => item.id !== updated.id) ?? [])],
    }));
  }

  const createMutation = useMutation({
    mutationFn: (raw: string) => createTracking(parseNegotiationResult(raw)),
    onSuccess: saveTracking,
  });
  const observationMutation = useMutation({
    mutationFn: ({ id, raw }: { id: string; raw: string }) =>
      recordNegotiation({ id, result: parseNegotiationResult(raw) }),
    onSuccess: saveTracking,
  });
  const refreshMutation = useMutation({ mutationFn: refreshTracking, onSuccess: saveTracking });
  const stopMutation = useMutation({ mutationFn: stopTracking, onSuccess: saveTracking });
  const searchError = createMutation.error ?? trackingsQuery.error;
  const actionError = refreshMutation.error ?? observationMutation.error ?? stopMutation.error;

  return (
    <div className="app-shell">
      <TrackerHeader />
      <main className="page-content">
        {trackingsQuery.isPending ? (
          <LoadingState />
        ) : tracking ? (
          <>
            <TrackingDashboard
              tracking={tracking}
              actionError={actionError}
              isRefreshing={refreshMutation.isPending}
              isRecording={observationMutation.isPending}
              isStopping={stopMutation.isPending}
              onRefresh={() => refreshMutation.mutate(tracking.id)}
              onRecord={() => observationMutation.mutate({ id: tracking.id, raw: resultJson })}
              onStop={() => stopMutation.mutate(tracking.id)}
            />
            <TripImportPanel
              compact
              error={searchError}
              isPending={createMutation.isPending}
              resultJson={resultJson}
              onChange={setResultJson}
              onSubmit={() => createMutation.mutate(resultJson)}
            />
          </>
        ) : (
          <EmptyState>
            <TripImportPanel
              error={searchError}
              isPending={createMutation.isPending}
              resultJson={resultJson}
              onChange={setResultJson}
              onSubmit={() => createMutation.mutate(resultJson)}
            />
          </EmptyState>
        )}
      </main>
    </div>
  );
}

function LoadingState() {
  return (
    <section className="loading-state" aria-live="polite" aria-busy="true">
      <span className="loading-bar" />
      <span className="loading-bar loading-bar-short" />
      <span className="loading-card" />
      <span className="sr-only">Загружаем поездки…</span>
    </section>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <>
      <section className="empty-hero">
        <p className="breadcrumb">Мои поездки</p>
        <h1>Следите за ценой поездки</h1>
        <p>
          Сохраним стоимость маршрута, покажем динамику и подскажем подходящий
          момент для покупки.
        </p>
        <div className="benefit-list" aria-label="Возможности отслеживания">
          <span>Вся поездка одной ценой</span>
          <span>История изменений</span>
          <span>Подсказка о покупке</span>
        </div>
      </section>
      {children}
    </>
  );
}
