import { create } from 'zustand'
import { TourStep } from '../components/TourGuide'

interface TourState {
  isActive: boolean
  steps: TourStep[]
  setIsActive: (isActive: boolean) => void
  setSteps: (steps: TourStep[]) => void
  startTour: (steps: TourStep[]) => void
  stopTour: () => void
}

export const useTourStore = create<TourState>((set) => ({
  isActive: false,
  steps: [],
  setIsActive: (isActive) => set({ isActive }),
  setSteps: (steps) => set({ steps }),
  startTour: (steps) => set({ steps, isActive: true }),
  stopTour: () => set({ isActive: false, steps: [] }),
}))