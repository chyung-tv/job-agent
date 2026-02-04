import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type CvFile = { url: string; name: string };

/**
 * Onboarding state interface.
 *
 * Stores user information collected during the onboarding flow:
 * - Identity: name, email, location
 * - Cultural Persona: basic_info (from Vibe Check)
 * - CV files: cv_files (url + name from UploadThing for display and submission)
 */
interface OnboardingState {
  name: string | null;
  email: string | null;
  location: string | null;
  basic_info: string | null; // Cultural Persona from Vibe Check
  cv_files: CvFile[]; // url + name from UploadThing (name for UI, url for submission)

  // Actions
  setName: (name: string) => void;
  setEmail: (email: string) => void;
  setLocation: (location: string) => void;
  setBasicInfo: (basic_info: string) => void;
  addCvFile: (file: CvFile) => void;
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
      cv_files: [],

      // Actions
      setName: (name: string) => set({ name }),
      setEmail: (email: string) => set({ email }),
      setLocation: (location: string) => set({ location }),
      setBasicInfo: (basic_info: string) =>
        set({ basic_info }),
      addCvFile: (file: CvFile) =>
        set((state) => ({
          cv_files: [...state.cv_files, file],
        })),
      reset: () =>
        set({
          name: null,
          email: null,
          location: null,
          basic_info: null,
          cv_files: [],
        }),
    }),
    {
      name: "onboarding-storage",
      storage: createJSONStorage(() => sessionStorageImpl),
      migrate: (persistedState, version) => {
        const s = persistedState as Record<string, unknown> & { cv_urls?: string[]; cv_files?: CvFile[] };
        if (s?.cv_urls?.length && !s?.cv_files?.length) {
          return {
            ...s,
            cv_files: s.cv_urls.map((url, i) => ({
              url,
              name: url.split("/").pop() || `File ${i + 1}`,
            })),
            cv_urls: undefined,
          };
        }
        return persistedState as OnboardingState;
      },
    }
  )
);
