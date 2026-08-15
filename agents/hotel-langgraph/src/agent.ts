import { makeTask } from "./a2a/server.js";
import type { Message, Task } from "./a2a/models.js";
import { textMessage } from "./a2a/models.js";
import { runHotelSearch } from "./graph.js";

/**
 * A2A message handler: unwraps the incoming TravelRequest-shaped JSON
 * text, runs the LangGraph state machine, and wraps the resulting
 * HotelResult as the agent's reply Message/Task — mirroring the Python
 * agents' handle_message() contract exactly.
 */
export async function handleMessage(message: Message): Promise<Task> {
  const text = message.parts
    .filter((p): p is { kind: "text"; text: string } => p.kind === "text")
    .map((p) => p.text)
    .join(" ");

  const result = await runHotelSearch(text);
  const reply = textMessage("agent", JSON.stringify(result), message.context_id);
  return makeTask(
    message.context_id ?? "unknown",
    { state: "completed", message: reply, timestamp: Date.now() / 1000 },
    [message, reply],
  );
}
