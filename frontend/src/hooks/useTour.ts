import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tourApi } from '../services/tour'
import { useAuthStore } from '../store/authStore'
import { TourStep } from '../components/TourGuide'

export function useTour() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [steps, setSteps] = useState<TourStep[]>([])
  const [isActive, setIsActive] = useState(false)

  // Получаем статус прохождения гайда
  const { data: tourStatus } = useQuery({
    queryKey: ['tour', 'status'],
    queryFn: tourApi.getStatus,
    enabled: !!user,
  })

  // Мутация для завершения гайда
  const completeMutation = useMutation({
    mutationFn: tourApi.complete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tour', 'status'] })
      setIsActive(false)
    },
  })

  // Мутация для сброса гайда
  const resetMutation = useMutation({
    mutationFn: tourApi.reset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tour', 'status'] })
    },
  })

  // Создаём шаги гайда для главной страницы
  const createHomeTourSteps = (): TourStep[] => {
    return [
      {
        id: 'hero',
        target: '[data-tour="hero"]',
        title: 'Добро пожаловать!',
        content: 'Это главная страница BEST PR System. Здесь вы можете увидеть общую информацию о системе, доступные задачи и статистику.',
        position: 'bottom',
      },
      {
        id: 'tasks',
        target: '[data-tour="tasks-link"]',
        title: 'Задачи',
        content: 'Перейдите в раздел задач, чтобы посмотреть доступные задания, взять их в работу или отслеживать свой прогресс.',
        position: 'bottom',
        action: () => {
          // Прокручиваем к ссылке на задачи
          const element = document.querySelector('[data-tour="tasks-link"]')
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }
        },
      },
      {
        id: 'stats',
        target: '[data-tour="stats-card"]',
        title: 'Статистика',
        content: 'Здесь отображается количество активных задач, выполненных заданий и другая полезная информация.',
        position: 'top',
      },
      {
        id: 'leaderboard',
        target: '[data-tour="leaderboard-link"]',
        title: 'Рейтинг',
        content: 'Посмотрите рейтинг участников PR-отдела. Зарабатывайте баллы, выполняйте задачи и поднимайтесь в топе!',
        position: 'bottom',
      },
      {
        id: 'support',
        target: '[data-tour="support-link"]',
        title: 'Поддержка',
        content: 'Если у вас есть вопросы или предложения, вы всегда можете обратиться в поддержку. Мы всегда готовы помочь!',
        position: 'top',
      },
    ]
  }

  // Создаём шаги гайда для страницы задач
  const createTasksTourSteps = (): TourStep[] => {
    return [
      {
        id: 'tasks-header',
        target: '[data-tour="tasks-header"]',
        title: 'Раздел задач',
        content: 'Здесь вы можете просматривать все доступные задачи, фильтровать их по типу и статусу, а также брать задачи в работу.',
        position: 'bottom',
      },
      {
        id: 'task-filters',
        target: '[data-tour="task-filters"]',
        title: 'Фильтры',
        content: 'Используйте фильтры для поиска задач по типу (SMM, дизайн, видео), приоритету или статусу.',
        position: 'bottom',
      },
      {
        id: 'task-card',
        target: '[data-tour="task-card"]',
        title: 'Карточка задачи',
        content: 'Каждая карточка содержит информацию о задаче: название, тип, дедлайн, количество участников. Нажмите на карточку для подробностей.',
        position: 'top',
      },
    ]
  }

  const startTour = (tourType: 'home' | 'tasks' = 'home') => {
    let tourSteps: TourStep[] = []
    
    if (tourType === 'home') {
      tourSteps = createHomeTourSteps()
    } else if (tourType === 'tasks') {
      tourSteps = createTasksTourSteps()
    }

    // Проверяем, что все элементы существуют
    const validSteps = tourSteps.filter(step => {
      const element = document.querySelector(step.target)
      return element !== null
    })

    if (validSteps.length > 0) {
      setSteps(validSteps)
      setIsActive(true)
    } else {
      console.warn('Tour elements not found on page')
    }
  }

  const stopTour = () => {
    setIsActive(false)
    setSteps([])
  }

  const completeTour = () => {
    completeMutation.mutate()
  }

  const resetTour = () => {
    resetMutation.mutate()
  }

  return {
    steps,
    isActive,
    tourCompleted: tourStatus?.tour_completed || false,
    startTour,
    stopTour,
    completeTour,
    resetTour,
    isLoading: completeMutation.isPending || resetMutation.isPending,
  }
}
