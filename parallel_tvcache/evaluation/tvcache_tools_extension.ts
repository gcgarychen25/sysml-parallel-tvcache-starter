/**
 * Pi extension: route bash/read/edit/write through the host TVCache tool gateway.
 *
 * Docker Desktop cannot use a Mac-host AF_UNIX socket from Linux containers
 * (inode visible, connect ECONNREFUSED). Agents use TCP to host.docker.internal.
 */
import * as net from "node:net";
import * as fs from "node:fs";
import * as os from "node:os";

const GATEWAY_HOST =
  process.env.SYSML_TVCACHE_GATEWAY_HOST || "host.docker.internal";
const GATEWAY_PORT = Number(
  process.env.SYSML_TVCACHE_GATEWAY_PORT || "17878"
);

function readTrim(path: string, fallback: string): string {
  try {
    if (fs.existsSync(path)) {
      const v = fs.readFileSync(path, "utf8").trim();
      if (v) return v;
    }
  } catch {
    // ignore
  }
  return fallback;
}

const TASK_ID = readTrim(
  "/tmp/harbor-pi-agent/tvcache-task-id",
  process.env.SYSML_TVCACHE_TASK_ID || "unknown-task"
);
const ROLLOUT_ID = readTrim(
  "/tmp/harbor-pi-agent/tvcache-rollout-id",
  process.env.SYSML_TVCACHE_ROLLOUT_ID || process.env.HOSTNAME || `rollout-${process.pid}`
);

function rpc(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const client = net.createConnection({
      host: GATEWAY_HOST,
      port: GATEWAY_PORT,
    });
    let buf = "";
    const timer = setTimeout(() => {
      client.destroy();
      reject(new Error("TVCache gateway timeout"));
    }, 600_000);
    client.on("connect", () => {
      client.write(JSON.stringify(payload) + "\n");
    });
    client.on("data", (chunk) => {
      buf += chunk.toString("utf8");
      const nl = buf.indexOf("\n");
      if (nl >= 0) {
        clearTimeout(timer);
        const line = buf.slice(0, nl);
        client.end();
        try {
          resolve(JSON.parse(line));
        } catch (e) {
          reject(e);
        }
      }
    });
    client.on("error", (e) => {
      clearTimeout(timer);
      reject(e);
    });
  });
}

async function gatewayTool(name: string, args: Record<string, unknown>) {
  const resp = await rpc({
    op: "tool",
    task_id: TASK_ID,
    rollout_id: ROLLOUT_ID,
    container_id: os.hostname(),
    name,
    arguments: args,
  });
  if (!resp.ok) {
    return {
      content: [{ type: "text", text: String(resp.output || resp.error || "tool failed") }],
      details: { tvcache: resp },
    };
  }
  return {
    content: [{ type: "text", text: String(resp.output ?? "") }],
    details: { tvcache: { source: resp.source, elapsed_s: resp.elapsed_s } },
  };
}

const TOOLS = [
  {
    name: "bash",
    label: "bash",
    description: "Run a shell command (via TVCache gateway).",
    parameters: {
      type: "object",
      properties: { command: { type: "string" } },
      required: ["command"],
    },
  },
  {
    name: "read",
    label: "read",
    description: "Read a file (via TVCache gateway).",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string" },
        file_path: { type: "string" },
      },
    },
  },
  {
    name: "write",
    label: "write",
    description: "Write a file (via TVCache gateway).",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string" },
        file_path: { type: "string" },
        content: { type: "string" },
        contents: { type: "string" },
      },
    },
  },
  {
    name: "edit",
    label: "edit",
    description: "Edit a file (via TVCache gateway).",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string" },
        file_path: { type: "string" },
        oldText: { type: "string" },
        newText: { type: "string" },
        old_str: { type: "string" },
        new_str: { type: "string" },
      },
    },
  },
] as const;

export default function (pi: any) {
  for (const t of TOOLS) {
    pi.registerTool({
      ...t,
      async execute(_toolCallId: string, params: Record<string, unknown>) {
        return gatewayTool(t.name, params || {});
      },
    });
  }

  pi.on("session_start", async () => {
    // Prefer our replacements when the runtime allows name overlap.
    try {
      const names = TOOLS.map((t) => t.name);
      if (typeof pi.setActiveTools === "function") {
        const current = (pi.getActiveTools?.() || []).map((x: any) =>
          typeof x === "string" ? x : x.name
        );
        const merged = Array.from(new Set([...current, ...names]));
        pi.setActiveTools(merged);
      }
    } catch {
      // best-effort
    }
  });
}
