import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Loader2, Bell } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { supportApi } from '../services/support'
import { notificationsApi } from '../services/notifications'
import { useMutation, useQuery } from '@tanstack/react-query'

interface Message {
  id: string
  text: string
  isBot: boolean
  timestamp: Date
}

type TabType = 'chat' | 'notifications'

export default function ChatWidget() {
  const { user } = useAuthStore()
  const { theme } = useThemeStore()
  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>('notifications') // Начинаем с уведомлений
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Привет! 👋 Чем могу помочь?',
      isBot: true,
      timestamp: new Date(),
    },
  ])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Загружаем уведомления
  const { data: notificationsData } = useQuery({
    queryKey: ['notifications', 'widget'],
    queryFn: () => notificationsApi.getNotifications({ limit: 20 }),
    enabled: isOpen && activeTab === 'notifications' && !!user && !!(user && user.is_active),
  })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (isOpen) {
      scrollToBottom()
      if (activeTab === 'chat') {
        inputRef.current?.focus()
      }
    }
  }, [isOpen, messages, activeTab])

  const mutation = useMutation({
    mutationFn: supportApi.createRequest,
    onSuccess: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: 'Спасибо за ваше сообщение! Мы свяжемся с вами в ближайшее время. ✅',
          isBot: true,
          timestamp: new Date(),
        },
      ])
      setMessage('')
      scrollToBottom()
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: 'Произошла ошибка при отправке сообщения. Попробуйте позже или обратитесь в поддержку через раздел "Поддержка". ❌',
          isBot: true,
          timestamp: new Date(),
        },
      ])
      scrollToBottom()
    },
  })

  const handleSend = async () => {
    if (!message.trim() || mutation.isPending) return

    const userMessage: Message = {
      id: Date.now().toString(),
      text: message.trim(),
      isBot: false,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setMessage('')

    // Отправляем в поддержку
    mutation.mutate({
      message: userMessage.text,
      category: 'question',
      contact: user?.telegram_username || user?.username || user?.email || undefined,
    })
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const notifications = notificationsData?.items || []
  const unreadCount = notifications.filter((n: any) => !n.is_read).length

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 w-14 h-14 bg-best-primary rounded-full shadow-lg hover:bg-best-primary/80 transition-all flex items-center justify-center z-50`}
        aria-label="Открыть чат"
      >
        <MessageSquare className="h-6 w-6 text-white" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
    )
  }

  return (
    <>
      {/* Чат виджет - справа снизу, поверх интерфейса, не влияет на layout */}
      <div
        className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 w-[calc(100vw-2rem)] md:w-96 max-w-md h-[calc(100vh-8rem)] md:h-[600px] max-h-[90vh] flex flex-col glass-enhanced ${theme} rounded-2xl shadow-2xl z-[9999] border border-white/30 transition-all duration-300`}
        style={{ 
          pointerEvents: isOpen ? 'auto' : 'none', 
          opacity: isOpen ? 1 : 0,
          transform: isOpen ? 'translateY(0) scale(1)' : 'translateY(20px) scale(0.95)',
          visibility: isOpen ? 'visible' : 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Заголовок с переключателем */}
        <div className="flex items-center justify-between p-4 border-b border-white/20">
          <div className="flex items-center space-x-2 flex-1">
            {/* Переключатель Уведомления/Чат (сначала уведомления) */}
            <div className="flex items-center space-x-1 bg-white/10 rounded-lg p-1">
              {user?.is_active && (
                <button
                  onClick={() => setActiveTab('notifications')}
                  className={`px-3 py-1.5 rounded text-sm transition-all flex items-center space-x-1 relative ${
                    activeTab === 'notifications'
                      ? 'bg-best-primary text-white'
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  <Bell className="h-4 w-4" />
                  <span>Уведомления</span>
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>
              )}
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-3 py-1.5 rounded text-sm transition-all flex items-center space-x-1 ${
                  activeTab === 'chat'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <MessageSquare className="h-4 w-4" />
                <span>Чат</span>
              </button>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1 hover:bg-white/20 rounded-lg transition-all ml-2"
            aria-label="Закрыть"
          >
            <X className="h-4 w-4 text-white" />
          </button>
        </div>

        {/* Контент в зависимости от активной вкладки */}
        {activeTab === 'chat' ? (
          <>
            {/* История сообщений */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.isBot ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      msg.isBot
                        ? 'bg-white/10 text-white'
                        : 'bg-best-primary text-white'
                    }`}
                  >
                    <p className={`text-sm text-readable ${theme}`}>{msg.text}</p>
                    <p className={`text-xs mt-1 opacity-60`}>
                      {msg.timestamp.toLocaleTimeString('ru-RU', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </p>
                  </div>
                </div>
              ))}
              {mutation.isPending && (
                <div className="flex justify-start">
                  <div className="bg-white/10 text-white rounded-lg p-3">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Поле ввода */}
            <div className="p-4 border-t border-white/20">
              <div className="flex space-x-2">
                <textarea
                  ref={inputRef}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Напишите сообщение..."
                  className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-best-primary border border-white/20 text-readable ${theme}`}
                  rows={1}
                  disabled={mutation.isPending}
                  style={{
                    minHeight: '40px',
                    maxHeight: '120px',
                  }}
                  onInput={(e) => {
                    const target = e.target as HTMLTextAreaElement
                    target.style.height = 'auto'
                    target.style.height = `${Math.min(target.scrollHeight, 120)}px`
                  }}
                />
                <button
                  onClick={handleSend}
                  disabled={!message.trim() || mutation.isPending}
                  className={`p-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center`}
                  aria-label="Отправить сообщение"
                >
                  {mutation.isPending ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Send className="h-5 w-5" />
                  )}
                </button>
              </div>
              <p className={`text-xs text-white/50 mt-2 text-readable ${theme}`}>
                Нажмите Enter для отправки, Shift+Enter для новой строки
              </p>
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto p-4">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Bell className="h-12 w-12 text-white/30 mb-4" />
                <p className={`text-white/60 text-readable ${theme}`}>Нет уведомлений</p>
              </div>
            ) : (
              <div className="space-y-2">
                {notifications.map((notification: any) => (
                  <div
                    key={notification.id}
                    className={`glass-enhanced ${theme} rounded-lg p-3 border ${
                      notification.is_read 
                        ? 'border-white/10 bg-white/5' 
                        : 'border-best-primary/50 bg-best-primary/10'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className={`text-white font-medium text-sm text-readable ${theme}`}>
                          {notification.title}
                        </h4>
                        <p className={`text-white/70 text-xs mt-1 text-readable ${theme}`}>
                          {notification.message}
                        </p>
                        <p className={`text-white/50 text-xs mt-2 text-readable ${theme}`}>
                          {new Date(notification.created_at).toLocaleDateString('ru-RU', {
                            day: 'numeric',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                      {!notification.is_read && (
                        <div className="w-2 h-2 bg-best-primary rounded-full ml-2 mt-1 flex-shrink-0" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
