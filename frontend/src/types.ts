export interface User {
  id: string;
  login: string;
  display_name: string;
}

export interface AuthSession {
  user: User | null;
}

export interface CodeRequested {
  challenge_id: string;
  expires_in: number;
  debug_code: string | null;
}
