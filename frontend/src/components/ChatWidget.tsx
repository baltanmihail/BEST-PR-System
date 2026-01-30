import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Loader2, Bell, AlertCircle } from 'lucide-react'
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
  const [activeTab, setActiveTab] = useState<TabType>('notifications') 
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
  const { data: notificationsData, refetch: refetchNotifications } = useQuery({
    queryKey: ['notifications', 'widget'],
    queryFn: () => notificationsApi.getNotifications({ limit: 20 }),
    enabled: !!user && !!user.is_active,
    // Polling каждые 30 секунд для проверки новых уведомлений
    refetchInterval: 30000 
  })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (isOpen) {
      scrollToBottom()
      if (activeTab === 'chat') {
        setTimeout(() => inputRef.current?.focus(), 100)
      }
    }
  }, [isOpen, activeTab])

  // Эффект скролла при добавлении сообщений
  useEffect(() => {
    if (isOpen && activeTab === 'chat') {
      scrollToBottom()
    }
  }, [messages])

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
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: 'Произошла ошибка при отправке. Попробуйте позже. ❌',
          isBot: true,
          timestamp: new Date(),
        },
      ])
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

  // Анимация появления
  const widgetClasses = isOpen 
    ? 'opacity-100 translate-y-0 scale-100 pointer-events-auto visible'
    : 'opacity-0 translate-y-4 scale-95 pointer-events-none invisible'

  return (
    <>
      {/* Кнопка открытия (FAB) */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-20 md:bottom-6 right-4 md:right-6 w-14 h-14 rounded-full shadow-xl transition-all flex items-center justify-center z-[9999] touch-manipulation hover:scale-105 active:scale-95 ${
          isOpen ? 'bg-red-500 rotate-90' : 'bg-best-primary rotate-0'
        }`}
        aria-label={isOpen ? "Закрыть чат" : "Открыть чат"}
      >
        {isOpen ? (
          <X className="h-6 w-6 text-white" />
        ) : (
          <div className="relative">
            <MessageSquare className="h-6 w-6 text-white" />
            {unreadCount > 0 && (
              <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center border-2 border-[#0f0f1a]">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </div>
        )}
      </button>

      {/* Окно виджета */}
      <div
        className={`fixed bottom-36 md:bottom-24 right-4 md:right-6 w-[calc(100vw-2rem)] md:w-96 h-[500px] max-h-[70vh] flex flex-col glass-enhanced ${theme} rounded-2xl shadow-2xl z-[9999] border border-white/20 transition-all duration-300 origin-bottom-right overflow-hidden ${widgetClasses}`}
      >
        {/* Хедер */}
        <div className="flex items-center justify-between p-3 border-b border-white/10 bg-white/5">
          <div className="flex bg-black/20 p-1 rounded-lg">
            <button
              onClick={() => setActiveTab('notifications')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
                activeTab === 'notifications' 
                  ? 'bg-best-primary text-white shadow-md' 
                  : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <Bell className="h-4 w-4" />
              <span>Инфо</span>
              {unreadCount > 0 && (
                <span className="bg-red-500 text-white text-[10px] px-1.5 rounded-full">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
                activeTab === 'chat' 
                  ? 'bg-best-primary text-white shadow-md' 
                  : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <MessageSquare className="h-4 w-4" />
              <span>Чат</span>
            </button>
          </div>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-hidden relative bg-black/20">
          {activeTab === 'chat' ? (
            <div className="absolute inset-0 flex flex-col">
              {/* Сообщения */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.isBot ? 'justify-start' : 'justify-end'}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                        msg.isBot
                          ? 'bg-white/10 text-white rounded-tl-none'
                          : 'bg-best-primary text-white rounded-tr-none'
                      }`}
                    >
                      <p>{msg.text}</p>
                      <p className="text-[10px] opacity-50 mt-1 text-right">
                        {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                ))}
                {mutation.isPending && (
                  <div className="flex justify-start">
                    <div className="bg-white/10 rounded-2xl px-4 py-2 rounded-tl-none">
                      <Loader2 className="h-4 w-4 animate-spin text-white/70" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Ввод */}
              <div className="p-3 bg-white/5 border-t border-white/10">
                <div className="flex gap-2 items-end">
                  <textarea
                    ref={inputRef}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ваш вопрос..."
                    className="flex-1 bg-black/20 text-white placeholder-white/40 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-best-primary border border-white/10 min-h-[44px] max-h-[100px]"
                    rows={1}
                  />
                  <button
                    onClick={handleSend}
                    disabled={!message.trim() || mutation.isPending}
                    className="p-3 bg-best-primary text-white rounded-xl hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:scale-95 active:scale-95"
                  >
                    <Send className="h-5 w-5" />
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="absolute inset-0 overflow-y-auto p-2">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center p-6 opacity-50">
                  <Bell className="h-12 w-12 mb-2" />
                  <p>Уведомлений нет</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {notifications.map((notification: any) => (
                    <div
                      key={notification.id}
                      className={`p-3 rounded-xl border transition-all ${
                        notification.is_read 
                          ? 'bg-white/5 border-white/5 text-white/60' 
                          : 'bg-best-primary/10 border-best-primary/30 text-white shadow-sm'
                      }`}
                    >
                      <div className="flex justify-between items-start gap-2">
                        <h4 className="font-medium text-sm leading-tight">
                          {notification.title}
                        </h4>
                        {!notification.is_read && (
                          <span className="w-2 h-2 rounded-full bg-best-primary mt-1 shrink-0" />
                        )}
                      </div>
                      <p className="text-xs mt-1 opacity-80 leading-relaxed">
                        {notification.message}
                      </p>
                      <p className="text-[10px] mt-2 opacity-40">
                        {new Date(notification.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
