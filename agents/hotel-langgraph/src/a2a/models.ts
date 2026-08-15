/**
 * Minimal A2A protocol data model — TypeScript mirror of the Python
 * adapter in agents/*-python/app/a2a/models.py. Wire-compatible: field
 * names and JSON shapes match exactly (snake_case), so the Planner talks
 * to this Node.js agent with the same client it uses for the Python
 * agents. See docs/adr/ADR-008-custom-a2a-adapter.md for the rationale
 * (no official a2a-sdk pinned yet).
 *
 * Reference: https://a2a-protocol.org/latest/topics/key-concepts/
 */

export type TaskState =
  | "submitted"
  | "working"
  | "input-required"
  | "completed"
  | "failed"
  | "canceled";

export interface TextPart {
  kind: "text";
  text: string;
}

export interface DataPart {
  kind: "data";
  data: Record<string, unknown>;
}

export type Part = TextPart | DataPart;

export interface Message {
  role: "user" | "agent";
  parts: Part[];
  message_id: string;
  context_id?: string | null;
  task_id?: string | null;
}

export interface TaskStatus {
  state: TaskState;
  message?: Message | null;
  timestamp: number;
}

export interface Artifact {
  artifact_id: string;
  name: string;
  parts: Part[];
}

export interface Task {
  id: string;
  context_id: string;
  status: TaskStatus;
  artifacts: Artifact[];
  history: Message[];
}

export interface AgentSkill {
  id: string;
  name: string;
  description: string;
  tags?: string[];
}

export interface AgentCapabilities {
  streaming: boolean;
  push_notifications: boolean;
}

export interface AgentCard {
  name: string;
  description: string;
  version: string;
  url: string;
  protocol_version: string;
  capabilities: AgentCapabilities;
  skills: AgentSkill[];
  default_input_modes: string[];
  default_output_modes: string[];
}

let uuidCounter = 0;
export function newId(): string {
  // crypto.randomUUID is available in Node >=14.17; kept as a thin
  // wrapper so tests can stub it deterministically if ever needed.
  uuidCounter += 1;
  return globalThis.crypto?.randomUUID?.() ?? `id-${Date.now()}-${uuidCounter}`;
}

export function textMessage(role: "user" | "agent", text: string, contextId?: string | null): Message {
  return {
    role,
    parts: [{ kind: "text", text }],
    message_id: newId(),
    context_id: contextId ?? null,
    task_id: null,
  };
}
