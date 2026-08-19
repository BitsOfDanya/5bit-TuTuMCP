import { apiRequest } from "./auth";

export interface ColdStartOption {
  id: string;
  title: string;
  subtitle: string;
  total_price: number;
  duration_minutes: number;
  transfers: number;
  transport: string;
  hotel_rating: number | null;
}

export interface ColdStartQuestion {
  id: string;
  prompt: string;
  left: ColdStartOption;
  right: ColdStartOption;
  targets: string[];
}

export interface ColdStartQuestions {
  total: number;
  minimum_choices: number;
  questions: ColdStartQuestion[];
}

export interface PreferenceProfile {
  profile_id: string;
  interactions: number;
  cold_start_completed: boolean;
  cold_start_answers: number;
  cold_start_confidence: number;
}

export interface ColdStartCompletion {
  profile: PreferenceProfile;
  cold_start: {
    questions_answered: number;
    completed: boolean;
    confidence: number;
  };
  learned_signals: string[];
}

export interface ColdStartChoice {
  question_id: string;
  selected_option_id: string;
}

export function getPreferenceProfile(): Promise<{ profile: PreferenceProfile | null }> {
  return apiRequest("/api/v1/preferences/me");
}

export function getColdStartQuestions(): Promise<ColdStartQuestions> {
  return apiRequest("/api/v1/preferences/cold-start/questions?limit=4");
}

export function completeColdStart(
  choices: ColdStartChoice[],
  replace: boolean,
): Promise<ColdStartCompletion> {
  return apiRequest("/api/v1/preferences/cold-start/complete", {
    method: "POST",
    body: JSON.stringify({ choices, replace }),
  });
}

export interface GroupPreferenceSummary {
  group_id: string;
  member_count: number;
  consensus_score: number;
  conflicts: Array<{ dimension: string; severity: string; description: string }>;
  highlights: string[];
}

export function buildGroupProfile(
  groupId: string,
  participantProfileIds: string[],
): Promise<{ result: GroupPreferenceSummary }> {
  return apiRequest("/api/v1/preferences/group/profile", {
    method: "POST",
    body: JSON.stringify({
      group_id: groupId,
      participant_profile_ids: participantProfileIds,
    }),
  });
}
