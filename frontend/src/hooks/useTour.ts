import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { tourApi } from '../services/tour'
import { useAuthStore } from '../store/authStore'
import { TourStep } from '../components/TourGuide'

export function useTour() {
  const { user } = useAuthStore()
  const location = useLocation()
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

  // Функции создания шагов вынесены вне useCallback для использования в зависимостях
  // Создаём шаги гайда для главной страницы
  const createHomeTourSteps = useCallback((): TourStep[] => {
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
  }, [])

  // Создаём шаги гайда для страницы задач
  const createTasksTourSteps = useCallback((): TourStep[] => {
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
  }, [])

  // Автоматически определяем тип тура по текущей странице
  const getTourTypeFromPath = useCallback((path: string): string => {
    if (path === '/') return 'home'
    if (path === '/tasks') return 'tasks'
    if (path === '/calendar') return 'calendar'
    if (path === '/gallery') return 'gallery'
    if (path === '/equipment') return 'equipment'
    if (path === '/settings') return 'settings'
    if (path === '/users') return 'users'
    if (path === '/support') return 'support'
    return 'home'
  }, [])

  // Создаём шаги гайда для календаря
  const createCalendarTourSteps = useCallback((): TourStep[] => {
    return [
      {
        id: 'calendar-header',
        target: '[data-tour="calendar-header"]',
        title: 'Календарь',
        content: 'Здесь вы можете увидеть все задачи и события на выбранный период. Используйте навигацию для перемещения по датам.',
        position: 'bottom',
      },
      {
        id: 'calendar-views',
        target: '[data-tour="calendar-views"]',
        title: 'Представления',
        content: 'Выберите удобное представление: Месяц, Неделя, Таймлайн, График работ или Доски (Kanban). Каждое представление покажет данные по-разному.',
        position: 'bottom',
      },
      {
        id: 'calendar-filters',
        target: '[data-tour="calendar-filters"]',
        title: 'Фильтры',
        content: 'Фильтруйте задачи по типу (SMM, Design, Channel, PR-FR) и настраивайте уровень детализации отображения.',
        position: 'bottom',
      },
      {
        id: 'calendar-sync',
        target: '[data-tour="calendar-sync"]',
        title: 'Синхронизация',
        content: 'Координаторы могут синхронизировать календарь с Google Sheets для создания отчётов и таблиц.',
        position: 'top',
      },
    ]
  }, [])

  // Создаём шаги гайда для галереи
  const createGalleryTourSteps = useCallback((): TourStep[] => {
    return [
      {
        id: 'gallery-header',
        target: '[data-tour="gallery-header"]',
        title: 'Галерея проектов',
        content: 'Здесь собраны все завершённые проекты PR-отдела. Вы можете просматривать работы участников, изучать примеры и вдохновляться!',
        position: 'bottom',
      },
      {
        id: 'gallery-filters',
        target: '[data-tour="gallery-filters"]',
        title: 'Фильтры',
        content: 'Фильтруйте проекты по категориям: фото, видео, финальные работы или работы в процессе. Используйте теги для поиска.',
        position: 'bottom',
      },
      {
        id: 'gallery-item',
        target: '[data-tour="gallery-item"]',
        title: 'Карточка проекта',
        content: 'Нажмите на карточку проекта, чтобы увидеть подробную информацию, метрики (просмотры, лайки) и связанные файлы.',
        position: 'top',
      },
    ]
  }, [])

  // Создаём шаги гайда для оборудования
  const createEquipmentTourSteps = useCallback((): TourStep[] => {
    return [
      {
        id: 'equipment-header',
        target: '[data-tour="equipment-header"]',
        title: 'Оборудование',
        content: 'Здесь вы можете просмотреть доступное оборудование для съёмок и подать заявку на аренду.',
        position: 'bottom',
      },
      {
        id: 'equipment-list',
        target: '[data-tour="equipment-list"]',
        title: 'Список оборудования',
        content: 'Посмотрите доступные камеры, объективы, световое оборудование и другие инструменты. Координаторы могут добавлять новое оборудование.',
        position: 'bottom',
      },
      {
        id: 'equipment-request',
        target: '[data-tour="equipment-request"]',
        title: 'Заявка на аренду',
        content: 'Выберите оборудование и даты аренды. После подачи заявки координатор рассмотрит её и уведомит вас о решении.',
        position: 'top',
      },
    ]
  }, [])

  // Создаём шаги гайда для настроек
  const createSettingsTourSteps = useCallback((): TourStep[] => {
    return [
      {
        id: 'settings-profile',
        target: '[data-tour="settings-profile"]',
        title: 'Профиль',
        content: 'Здесь вы можете редактировать свой профиль: добавить фото, описание, контакты, навыки и портфолио работ.',
        position: 'bottom',
      },
      {
        id: 'settings-theme',
        target: '[data-tour="settings-theme"]',
        title: 'Настройки',
        content: 'Переключайте тему оформления (светлая/тёмная) для комфортной работы в любое время суток.',
        position: 'top',
      },
    ]
  }, [])

  // Создаём шаги гайда для мониторинга (координаторы)
  const createUsersTourSteps = useCallback((): TourStep[] => {
    return [
      {
        id: 'users-header',
        target: '[data-tour="users-header"]',
        title: 'Мониторинг пользователей',
        content: 'Этот раздел доступен только координаторам. Здесь вы можете управлять пользователями системы.',
        position: 'bottom',
      },
      {
        id: 'users-search',
        target: '[data-tour="users-search"]',
        title: 'Поиск',
        content: 'Ищите пользователей по имени, username или email. Используйте фильтры для быстрого поиска.',
        position: 'bottom',
      },
      {
        id: 'users-actions',
        target: '[data-tour="users-actions"]',
        title: 'Действия',
        content: 'Вы можете блокировать/разблокировать пользователей, изменять баллы, просматривать статистику и экспортировать данные.',
        position: 'top',
      },
    ]
  }, [])

  // Создаём шаги гайда для страницы поддержки
  const createSupportTourSteps = useCallback((): TourStep[] => {
    return [
      {
        id: 'support-header',
        target: '[data-tour="support-header"]',
        title: 'Поддержка',
        content: 'Здесь вы можете задать вопрос или отправить предложение. Выберите тип обращения и заполните форму.',
        position: 'bottom',
      },
      {
        id: 'support-link',
        target: '[data-tour="support-link"]',
        title: 'Ссылка в меню',
        content: 'Ссылка на страницу поддержки всегда доступна в боковом меню для быстрого доступа.',
        position: 'top',
      },
    ]
  }, [])

  const startTour = useCallback((tourType?: string) => {
    console.log('startTour called with:', tourType)
    // Если тип не указан, определяем автоматически по текущему пути
    const type = tourType || getTourTypeFromPath(location.pathname)
    console.log('Tour type determined:', type)
    let tourSteps: TourStep[] = []
    
    if (type === 'home') {
      tourSteps = createHomeTourSteps()
    } else if (type === 'tasks') {
      tourSteps = createTasksTourSteps()
    } else if (type === 'calendar') {
      tourSteps = createCalendarTourSteps()
    } else if (type === 'gallery') {
      tourSteps = createGalleryTourSteps()
    } else if (type === 'equipment') {
      tourSteps = createEquipmentTourSteps()
    } else if (type === 'settings') {
      tourSteps = createSettingsTourSteps()
    } else if (type === 'users') {
      tourSteps = createUsersTourSteps()
    } else if (type === 'support') {
      tourSteps = createSupportTourSteps()
    } else {
      tourSteps = createHomeTourSteps()
    }

    console.log('Tour steps created:', tourSteps.length, tourSteps.map(s => s.target))

    // Небольшая задержка для гарантии, что DOM элементы загружены
    setTimeout(() => {
      // В режиме отладки или при ручном запуске всегда показываем шаги, даже если элементы не найдены
      // (Joyride сам обработает отсутствующие элементы, показав tooltip по центру или пропустив шаг)
      console.log('Starting tour forced:', type)
      setSteps(tourSteps)
      setIsActive(true)
    }, 100)
  }, [location.pathname, getTourTypeFromPath, createHomeTourSteps, createTasksTourSteps, createCalendarTourSteps, createGalleryTourSteps, createEquipmentTourSteps, createSettingsTourSteps, createUsersTourSteps, createSupportTourSteps])

  // Автоматически запускаем гайд только при первом посещении главной страницы (не навязчиво)
  useEffect(() => {
    // Запускаем гайд только если:
    // 1. Пользователь зарегистрирован (активен или неактивен - разрешаем всем)
    // 2. Гайд ещё не был пройден (или статус ещё не загружен)
    // 3. Гайд не активен сейчас
    // 4. Мы на главной странице (для первого знакомства)
    if (
      user && 
      (tourStatus === undefined || !tourStatus.tour_completed) && 
      !isActive && 
      location.pathname === '/'
    ) {
      // Небольшая задержка для загрузки элементов на странице
      const timer = setTimeout(() => {
        startTour('home')
      }, 2000) // Увеличена задержка для гарантированной загрузки всех элементов
      return () => clearTimeout(timer)
    }
  }, [location.pathname, user, tourStatus, isActive, startTour])

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
