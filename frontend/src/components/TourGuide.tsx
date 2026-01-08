import { useState, useEffect, useRef } from 'react'
import { X, ChevronRight, ChevronLeft, MapPin } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'

export type TourStep = {
  id: string
  target: string // CSS selector
  title: string
  content: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  action?: () => void // Действие перед показом шага (например, прокрутка)
}

type TourGuideProps = {
  steps: TourStep[]
  onComplete?: () => void
  onSkip?: () => void
  showSkip?: boolean
}

export default function TourGuide({ steps, onComplete, onSkip, showSkip = true }: TourGuideProps) {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const [currentStep, setCurrentStep] = useState(0)
  const [isVisible, setIsVisible] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (steps.length > 0) {
      setIsVisible(true)
      // Небольшая задержка для анимации
      setTimeout(() => {
        scrollToStep(0)
      }, 100)
    }
  }, [steps])

  const scrollToStep = (stepIndex: number) => {
    const step = steps[stepIndex]
    if (!step) return

    // Выполняем действие перед показом шага
    if (step.action) {
      step.action()
    }

    // Находим элемент
    const element = document.querySelector(step.target)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      
      // Небольшая задержка для завершения прокрутки
      setTimeout(() => {
        updateTooltipPosition(step)
      }, 300)
    } else {
      updateTooltipPosition(step)
    }
  }

  const updateTooltipPosition = (step: TourStep) => {
    const element = document.querySelector(step.target)
    if (!element || !tooltipRef.current || !overlayRef.current) return

    const rect = element.getBoundingClientRect()
    const tooltip = tooltipRef.current
    const overlay = overlayRef.current

    // Позиционируем overlay (затемнение)
    overlay.style.clipPath = `polygon(
      0% 0%,
      0% 100%,
      ${rect.left}px 100%,
      ${rect.left}px ${rect.top}px,
      ${rect.right}px ${rect.top}px,
      ${rect.right}px ${rect.bottom}px,
      ${rect.left}px ${rect.bottom}px,
      ${rect.left}px 100%,
      100% 100%,
      100% 0%
    )`

    // Позиционируем tooltip
    const position = step.position || 'bottom'
    let top = 0
    let left = 0

    switch (position) {
      case 'top':
        top = rect.top - tooltip.offsetHeight - 20
        left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2
        break
      case 'bottom':
        top = rect.bottom + 20
        left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2
        break
      case 'left':
        top = rect.top + rect.height / 2 - tooltip.offsetHeight / 2
        left = rect.left - tooltip.offsetWidth - 20
        break
      case 'right':
        top = rect.top + rect.height / 2 - tooltip.offsetHeight / 2
        left = rect.right + 20
        break
    }

    // Проверяем границы экрана
    const padding = 20
    if (left < padding) left = padding
    if (left + tooltip.offsetWidth > window.innerWidth - padding) {
      left = window.innerWidth - tooltip.offsetWidth - padding
    }
    if (top < padding) top = padding
    if (top + tooltip.offsetHeight > window.innerHeight - padding) {
      top = window.innerHeight - tooltip.offsetHeight - padding
    }

    tooltip.style.top = `${top}px`
    tooltip.style.left = `${left}px`
  }

  useEffect(() => {
    if (isVisible && steps.length > 0) {
      scrollToStep(currentStep)
      
      // Обновляем позицию при изменении размера окна
      const handleResize = () => {
        scrollToStep(currentStep)
      }
      window.addEventListener('resize', handleResize)
      return () => window.removeEventListener('resize', handleResize)
    }
  }, [currentStep, isVisible])

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      handleComplete()
    }
  }

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleComplete = () => {
    setIsVisible(false)
    if (onComplete) {
      onComplete()
    }
  }

  const handleSkip = () => {
    setIsVisible(false)
    if (onSkip) {
      onSkip()
    }
  }

  if (!isVisible || steps.length === 0) return null

  const step = steps[currentStep]
  if (!step) return null

  return (
    <>
      {/* Overlay с затемнением */}
      <div
        ref={overlayRef}
        className="fixed inset-0 bg-black/70 z-[9998] transition-opacity duration-300"
        onClick={handleSkip}
      />

      {/* Tooltip с информацией */}
      <div
        ref={tooltipRef}
        className={`fixed z-[9999] w-80 md:w-96 ${theme === 'dark' ? 'bg-gray-900' : 'bg-white'} rounded-xl shadow-2xl border-2 border-best-primary p-6 transition-all duration-300`}
        style={{ top: 0, left: 0 }}
      >
        {/* Заголовок */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-2">
            <MapPin className="h-5 w-5 text-best-primary" />
            <h3 className={`text-lg font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              {step.title}
            </h3>
          </div>
          {showSkip && (
            <button
              onClick={handleSkip}
              className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
            >
              <X className="h-4 w-4 text-gray-500" />
            </button>
          )}
        </div>

        {/* Содержимое */}
        <p className={`text-sm mb-6 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>
          {step.content}
        </p>

        {/* Прогресс */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
            <span>Шаг {currentStep + 1} из {steps.length}</span>
            <span>{Math.round(((currentStep + 1) / steps.length) * 100)}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className="bg-best-primary h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Кнопки навигации */}
        <div className="flex items-center justify-between">
          <button
            onClick={handlePrev}
            disabled={currentStep === 0}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="h-4 w-4" />
            <span>Назад</span>
          </button>

          <button
            onClick={handleNext}
            className="flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-colors"
          >
            <span>{currentStep === steps.length - 1 ? 'Завершить' : 'Далее'}</span>
            {currentStep < steps.length - 1 && <ChevronRight className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </>
  )
}
