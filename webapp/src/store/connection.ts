import { create } from "zustand";

export const useConnection = create<{ state: "connecting"|"connected"|"offline"|"error"; lastError: string | null }>(() => ({
  state: "connecting",
  lastError: null,
}));
