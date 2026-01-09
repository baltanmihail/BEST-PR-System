import { useState, useEffect, useRef } from 'react'
import { X, ChevronRight, ChevronLeft, MapPin } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'

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
  const [currentStep, setCurrentStep] = useState(0)
  const [isVisible, setIsVisible] = useState(false)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)

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
    const element = document.querySelector(step.target) as HTMLElement
    if (element) {
      // Прокручиваем элемент в центр экрана
      const rect = element.getBoundingClientRect()
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop
      const elementTop = rect.top + scrollTop
      const elementCenter = elementTop + rect.height / 2
      const windowCenter = window.innerHeight / 2
      const targetScroll = elementCenter - windowCenter
      
      window.scrollTo({ top: targetScroll, behavior: 'smooth' })
      
      // Небольшая задержка для завершения прокрутки
      setTimeout(() => {
        updateTooltipPosition(step)
      }, 400)
    } else {
      updateTooltipPosition(step)
    }
  }

  const updateTooltipPosition = (step: TourStep) => {
    const element = document.querySelector(step.target) as HTMLElement
    if (!element || !tooltipRef.current || !highlightRef.current) return

    const rect = element.getBoundingClientRect()
    const tooltip = tooltipRef.current
    const highlight = highlightRef.current

    // Подсвечиваем элемент (рамка вокруг него)
    highlight.style.top = `${rect.top + window.scrollY}px`
    highlight.style.left = `${rect.left + window.scrollX}px`
    highlight.style.width = `${rect.width}px`
    highlight.style.height = `${rect.height}px`

    // Позиционируем tooltip
    const position = step.position || 'bottom'
    let top = 0
    let left = 0
    const spacing = 16

    switch (position) {
      case 'top':
        top = rect.top + window.scrollY - tooltip.offsetHeight - spacing
        left = rect.left + window.scrollX + rect.width / 2 - tooltip.offsetWidth / 2
        break
      case 'bottom':
        top = rect.bottom + window.scrollY + spacing
        left = rect.left + window.scrollX + rect.width / 2 - tooltip.offsetWidth / 2
        break
      case 'left':
        top = rect.top + window.scrollY + rect.height / 2 - tooltip.offsetHeight / 2
        left = rect.left + window.scrollX - tooltip.offsetWidth - spacing
        break
      case 'right':
        top = rect.top + window.scrollY + rect.height / 2 - tooltip.offsetHeight / 2
        left = rect.right + window.scrollX + spacing
        break
    }

    // Проверяем границы экрана и корректируем позицию
    const padding = 20
    if (left < padding) left = padding
    if (left + tooltip.offsetWidth > window.innerWidth - padding) {
      left = window.innerWidth - tooltip.offsetWidth - padding
    }
    if (top < padding) top = padding + window.scrollY
    if (top + tooltip.offsetHeight > window.innerHeight + window.scrollY - padding) {
      top = window.innerHeight + window.scrollY - tooltip.offsetHeight - padding
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
    <div className="fixed inset-0 pointer-events-none z-[9997]" style={{ isolation: 'isolate' }}>
      {/* Подсветка элемента (рамка) */}
      <div
        ref={highlightRef}
        className="absolute pointer-events-none border-4 border-best-primary rounded-lg transition-all duration-300 shadow-[0_0_0_9999px_rgba(0,0,0,0.3)]"
        style={{
          boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.3), 0 0 20px rgba(59, 130, 246, 0.5)',
          zIndex: 9998,
        }}
      />

      {/* Tooltip с информацией */}
      <div
        ref={tooltipRef}
        className={`fixed pointer-events-auto w-80 md:w-96 glass-enhanced ${theme} rounded-xl shadow-2xl border-2 border-best-primary p-6 transition-all duration-300`}
        style={{ zIndex: 9999 }}
      >
        {/* Заголовок */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-2">
            <MapPin className="h-5 w-5 text-best-primary" />
            <h3 className={`text-lg font-bold text-white text-readable ${theme}`}>
              {step.title}
            </h3>
          </div>
          {showSkip && (
            <button
              onClick={handleSkip}
              className="p-1 hover:bg-white/20 rounded transition-colors"
            >
              <X className="h-4 w-4 text-white" />
            </button>
          )}
        </div>

        {/* Содержимое */}
        <p className={`text-sm mb-6 text-white/90 text-readable ${theme}`}>
          {step.content}
        </p>

        {/* Прогресс */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-white/60 mb-2">
            <span>Шаг {currentStep + 1} из {steps.length}</span>
            <span>{Math.round(((currentStep + 1) / steps.length) * 100)}%</span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2">
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
            className="flex items-center space-x-2 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
    </div>
  )
}
