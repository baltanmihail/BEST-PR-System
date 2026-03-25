import { useState, useEffect } from 'react'
import { MessageSquare, X } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { isCoordinatorOrAbove } from '../types/user'

const messages = {
  unregistered: [
    "Привет! 👋 Хочешь присоединиться к команде PR-отдела?",
    "У нас интересные задачи и дружная команда! 🚀",
    "Зарегистрируйся, чтобы начать брать задачи и зарабатывать баллы!",
  ],
  registered: [
    "Привет! Как дела? 😊",
    "О, пока тебя не было, появились новые задачи!",
    "Не забудь проверить уведомления! 🔔",
  ],
  coordinator: [
    "Добро пожаловать, координатор! 👨‍💼",
    "У тебя есть новые заявки на модерацию.",
    "Проверь задачи, которые требуют внимания.",
  ],
}

export default function MotivationalChat() {
  const { user } = useAuthStore()
  const { theme } = useThemeStore()
  const [isOpen, setIsOpen] = useState(false)
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0)

  const userRole = user?.role || 'unregistered'
  const isCoordinator = isCoordinatorOrAbove(userRole)
  const isRegistered = user && user.is_active

  const chatMessages = isCoordinator
    ? messages.coordinator
    : isRegistered
    ? messages.registered
    : messages.unregistered

  useEffect(() => {
    if (isOpen) {
      const interval = setInterval(() => {
        setCurrentMessageIndex((prev) => (prev + 1) % chatMessages.length)
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [isOpen, chatMessages.length])

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 w-14 h-14 bg-best-primary rounded-full shadow-lg hover:bg-best-primary/80 transition-all flex items-center justify-center z-50`}
        aria-label="Открыть чат"
      >
        <MessageSquare className="h-6 w-6 text-white" />
        <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full"></span>
      </button>
    )
  }

  return (
    <div
      className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 w-[calc(100vw-2rem)] md:w-80 max-w-sm glass-enhanced ${theme} rounded-2xl p-4 shadow-2xl z-50 border border-white/30`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <MessageSquare className="h-5 w-5 text-best-primary" />
          <h3 className={`text-white font-semibold text-readable ${theme}`}>Чат</h3>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 hover:bg-white/20 rounded-lg transition-all"
        >
          <X className="h-4 w-4 text-white" />
        </button>
      </div>
      <div className={`p-3 bg-white/10 rounded-lg mb-3 min-h-[60px] flex items-center`}>
        <p className={`text-white text-sm text-readable ${theme}`}>
          {chatMessages[currentMessageIndex]}
        </p>
      </div>
      <div className="flex space-x-2">
        {chatMessages.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentMessageIndex(index)}
            className={`h-2 rounded-full transition-all ${
              index === currentMessageIndex ? 'bg-best-primary flex-1' : 'bg-white/20 w-2'
            }`}
          />
        ))}
      </div>
    </div>
  )
}
