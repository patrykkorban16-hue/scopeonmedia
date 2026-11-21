import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import { SOCKET_URL } from "./api.js";

const EVENTS = ["alert", "finding_updated", "thresholds", "job", "registry"];

// Jedno połączenie Socket.IO na aplikację; handlery w ref, żeby render nie przełączał połączenia.
export function useSocket(handlers) {
  const [connected, setConnected] = useState(false);
  const ref = useRef(handlers);
  useEffect(() => {
    ref.current = handlers;
  });

  useEffect(() => {
    const socket = io(SOCKET_URL, { transports: ["websocket", "polling"], reconnectionDelayMax: 5000, autoConnect: false });
    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));
    EVENTS.forEach((ev) => socket.on(ev, (data) => ref.current[ev]?.(data)));
    // połączenie po zakończeniu bieżącego cyklu – podwójny montaż w StrictMode nie zrywa handshake'u
    const t = setTimeout(() => socket.connect(), 0);
    return () => {
      clearTimeout(t);
      socket.disconnect();
    };
  }, []);

  return connected;
}
