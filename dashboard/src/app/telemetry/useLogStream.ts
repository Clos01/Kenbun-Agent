import { useEffect, useState, useRef } from "react";

export interface LogRecord {
  id: string;
  message: string;
  timestamp: string;
  type: "info" | "step" | "error" | "success";
}

const parseLogLine = (logLine: string, customTimestamp?: number): LogRecord => {
  let type: "info" | "step" | "error" | "success" = "info";
  let text = logLine;
  let timestamp = customTimestamp;

  // Auto-detect and parse JSON logs from historical text records
  if (typeof logLine === "string" && logLine.trim().startsWith("{") && logLine.trim().endsWith("}")) {
    try {
      const parsed = JSON.parse(logLine);
      if (parsed.message) {
        text = parsed.message;
      }
      if (parsed.type) {
        // Map backend reflection types to standard steps
        type = parsed.type === "reflection" ? "step" : parsed.type;
      }
      if (parsed.timestamp) {
        timestamp = parsed.timestamp;
      }
    } catch {
      // Fallback to raw string parsing on JSON syntax failure
    }
  }

  if (text.includes("[FLASH_STEP]")) {
    type = "step";
    text = text.replace("[FLASH_STEP]", "").trim();
  } else if (text.toLowerCase().includes("error") || text.toLowerCase().includes("failed") || text.toLowerCase().includes("exception")) {
    type = "error";
  } else if (text.toLowerCase().includes("pass") || text.toLowerCase().includes("successful") || text.toLowerCase().includes("stable") || text.toLowerCase().includes("approved")) {
    type = "success";
  }

  // Formatting date string nicely
  let timeStr = "";
  try {
    timeStr = timestamp 
      ? new Date(timestamp * 1000).toLocaleTimeString()
      : new Date().toLocaleTimeString();
  } catch {
    timeStr = new Date().toLocaleTimeString();
  }

  return {
    id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
    message: text,
    timestamp: timeStr,
    type
  };
};

// Strict utility to neutralize malicious HTML / javascript: links in logs
export const sanitizeLogContent = (content: string): string => {
  if (!content) return "";
  // Strip javascript: or data: prefixes to prevent malicious active elements
  return content.replace(/(javascript|data|vbscript):/gi, "[blocked-protocol]:");
};

export const useLogStream = (apiBase: string) => {
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectDelayRef = useRef<number>(1000); // starts at 1s
  const eventSourceRef = useRef<EventSource | null>(null);
  
  // High-frequency throttle buffer
  const logBufferRef = useRef<LogRecord[]>([]);
  const throttleIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // 1. Initial bulk fetch of history logs
    const loadInitialLogs = async () => {
      try {
        const res = await fetch(`${apiBase}/logs`, { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          const parsed = (data.logs || [])
            .slice(-100)
            .map((l: string) => parseLogLine(sanitizeLogContent(l)));
          setLogs(parsed);
        }
      } catch (err) {
        console.warn("Failed to load initial logs:", err);
      }
    };
    loadInitialLogs();

    // 2. Establish connection to real-time SSE stream
    const connectSSE = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const es = new EventSource(`${apiBase}/api/v1/logs/stream`);
      eventSourceRef.current = es;

      es.onopen = () => {
        // Reset exponential backoff on successful link establishment
        reconnectDelayRef.current = 1000;
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.message) {
            const sanitizedMsg = sanitizeLogContent(data.message);
            const newLog = parseLogLine(sanitizedMsg, data.timestamp);
            
            // Append to queue buffer for batch throttling
            logBufferRef.current.push(newLog);
          }
        } catch (e) {
          console.warn("Failed to parse live log event:", e);
        }
      };

      es.onerror = (err) => {
        console.warn(`SSE stream disconnected, scheduling reconnect in ${reconnectDelayRef.current}ms...`, err);
        es.close();
        
        // Exponential backoff capped at 30 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 1.5, 30000);
          connectSSE();
        }, reconnectDelayRef.current);
      };
    };

    connectSSE();

    // 3. Throttle state updates every 100ms to consolidate multi-message events
    throttleIntervalRef.current = setInterval(() => {
      if (logBufferRef.current.length > 0) {
        const bufferedItems = [...logBufferRef.current];
        logBufferRef.current = [];

        setLogs((prev) => {
          // Deduplicate incoming items against prev state to avoid duplicate rendering
          const filteredNew = bufferedItems.filter(
            (newItem) => !prev.some((oldItem) => oldItem.message === newItem.message)
          );
          
          if (filteredNew.length === 0) return prev;
          return [...prev, ...filteredNew].slice(-150); // cap at 150 circular buffer
        });
      }
    }, 100);

    // 4. Clean up connections, timeouts, and intervals on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (throttleIntervalRef.current) {
        clearInterval(throttleIntervalRef.current);
      }
    };
  }, [apiBase]);

  return logs;
};
