export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  version: string;
  timestamp: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
}

export type ConnectionStatus = "checking" | "connected" | "unavailable";

export interface HealthState {
  status: ConnectionStatus;
  data: HealthResponse | null;
  errorMessage: string | null;
  latencyMs: number | null;
  lastChecked: Date | null;
  databaseStatus: ConnectionStatus;
  databaseMessage: string | null;
}
