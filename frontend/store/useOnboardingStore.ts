import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * Onboarding state interface.
 * 
 * Stores user information collected during the onboarding flow:
 * - Identity: name, email, location
 * - Cultural Persona: basic_info (from Vibe Check)
 * - CV URLs: cv_urls (from UploadThing)
 */
interface OnboardingState {
  name: string | null;
  email: string | null;
  location: string | null;
  basic_info: string | null; // Cultural Persona from Vibe Check
  cv_urls: string[]; // Array of public URLs from UploadThing

  // Actions
  setName: (name: string) => void;
  setEmail: (email: string) => void;
  setLocation: (location: string) => void;
  setBasicInfo: (basic_info: string) => void;
  addCvUrl: (url: string) => void;
  reset: () => void;
}

/**
 * Custom sessionStorage implementation that handles SSR.
 * 
 * Returns null on server-side to avoid hydration mismatches.
 */
const sessionStorageImpl = {
  getItem: (name: string): string | null => {
    if (typeof window === "undefined") return null;
    try {
      return sessionStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name: string, value: string): void => {
    if (typeof window === "undefined") return;
    try {
      sessionStorage.setItem(name, value);
    } catch {
      // Ignore errors (e.g., quota exceeded)
    }
  },
  removeItem: (name: string): void => {
    if (typeof window === "undefined") return;
    try {
      sessionStorage.removeItem(name);
    } catch {
      // Ignore errors
    }
  },
};

/**
 * Zustand store for onboarding state with sessionStorage persistence.
 * 
 * Persists state across page refreshes so that if the user refreshes
 * during the onboarding flow (e.g., during Vibe Check), their progress
 * is not lost.
 * 
 * @example
 * ```tsx
 * const { name, email, setName, setEmail } = useOnboardingStore();
 * 
 * setName("John Doe");
 * setEmail("john@example.com");
 * ```
 */
export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      // Initial state
      name: null,
      email: null,
      location: null,
      basic_info: null,
      cv_urls: [],

      // Actions
      setName: (name: string) => set({ name }),
      setEmail: (email: string) => set({ email }),
      setLocation: (location: string) => set({ location }),
      setBasicInfo: (basic_info: string) =>
        set({ basic_info }),
      addCvUrl: (url: string) =>
        set((state) => ({
          cv_urls: [...state.cv_urls, url],
        })),
      reset: () =>
        set({
          name: null,
          email: null,
          location: null,
          basic_info: null,
          cv_urls: [],
        }),
    }),
    {
      name: "onboarding-storage",
      storage: createJSONStorage(() => sessionStorageImpl),
    }
  )
);
