import type { Request, Response, Router } from "express";
import { Router as makeRouter } from "express";

import type { AgentCard, Message, Task, TaskStatus } from "./models.js";
import { newId } from "./models.js";
import { AuthError, verifyRequest, type AuthConfig } from "./auth.js";

export type TaskHandler = (message: Message) => Promise<Task>;

export class InMemoryTaskStore {
  private tasks = new Map<string, Task>();

  save(task: Task): void {
    this.tasks.set(task.id, task);
  }

  get(taskId: string): Task | undefined {
    return this.tasks.get(taskId);
  }
}

function jsonRpcError(res: Response, id: unknown, code: number, message: string): void {
  res.status(200).json({ jsonrpc: "2.0", id: id ?? null, error: { code, message } });
}

function jsonRpcResult(res: Response, id: unknown, result: unknown): void {
  res.status(200).json({ jsonrpc: "2.0", id: id ?? null, result });
}

export function buildAgentCardRouter(card: AgentCard): Router {
  const router = makeRouter();
  router.get("/.well-known/agent-card.json", (_req: Request, res: Response) => {
    res.json(card);
  });
  return router;
}

/**
 * JSON-RPC 2.0 endpoint implementing the A2A methods, mirroring
 * agents/*-python/app/a2a/server.py exactly (method names, error codes,
 * response shape) so the Planner's existing A2A client works unchanged
 * against this TypeScript agent.
 */
export function buildJsonRpcRouter(
  handler: TaskHandler,
  taskStore: InMemoryTaskStore,
  authConfig?: AuthConfig,
): Router {
  const router = makeRouter();

  router.post("/a2a", async (req: Request, res: Response) => {
    const body = req.body as { id?: unknown; method?: string; params?: Record<string, unknown> };
    const id = body?.id;
    const method = body?.method;
    const params = body?.params ?? {};

    if (authConfig !== undefined) {
      try {
        verifyRequest(req, authConfig);
      } catch (err) {
        if (err instanceof AuthError) {
          res.status(401).json({ detail: err.message });
          return;
        }
        throw err;
      }
    }

    if (method === "message/send") {
      const message = params.message as Message | undefined;
      if (!message || !Array.isArray(message.parts)) {
        jsonRpcError(res, id, -32602, "Invalid params: missing or malformed 'message'");
        return;
      }
      try {
        const task = await handler(message);
        taskStore.save(task);
        jsonRpcResult(res, id, task);
      } catch (err) {
        jsonRpcError(res, id, -32000, `Agent execution error: ${(err as Error).message}`);
      }
      return;
    }

    if (method === "tasks/get") {
      const taskId = params.id as string | undefined;
      const task = taskId ? taskStore.get(taskId) : undefined;
      if (!task) {
        jsonRpcError(res, id, -32001, `Task '${taskId}' not found`);
        return;
      }
      jsonRpcResult(res, id, task);
      return;
    }

    if (method === "tasks/cancel") {
      const taskId = params.id as string | undefined;
      const task = taskId ? taskStore.get(taskId) : undefined;
      if (!task) {
        jsonRpcError(res, id, -32001, `Task '${taskId}' not found`);
        return;
      }
      const canceled: TaskStatus = { state: "canceled", timestamp: Date.now() / 1000 };
      task.status = canceled;
      taskStore.save(task);
      jsonRpcResult(res, id, task);
      return;
    }

    jsonRpcError(res, id, -32601, `Method '${method}' not found`);
  });

  return router;
}

export function makeTask(contextId: string, status: TaskStatus, history: Message[]): Task {
  return {
    id: newId(),
    context_id: contextId,
    status,
    artifacts: [],
    history,
  };
}
