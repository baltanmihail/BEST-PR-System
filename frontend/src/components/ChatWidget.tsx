import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Loader2, Bell, ChevronDown } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { supportApi } from '../services/support'
import { notificationsApi } from '../services/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

interface Message {
  id: string
  text: string
  isBot: boolean
  timestamp: Date
}

type TabType = 'chat' | 'notifications'

export default function ChatWidget() {
  const { user } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>('notifications')
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      text: 'Привет! 👋 Я бот BEST PR System. Если у тебя есть вопрос или предложение, напиши его здесь, и мы передадим его команде.',
      isBot: true,
      timestamp: new Date(),
    },
  ])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()

  // Загружаем уведомления (только если открыт виджет и вкладка уведомлений)
  const { data: notificationsData } = useQuery({
    queryKey: ['notifications', 'widget'],
    queryFn: () => notificationsApi.getNotifications({ limit: 20 }),
    enabled: isOpen && activeTab === 'notifications' && !!user,
    refetchInterval: isOpen ? 10000 : false, // Обновляем каждые 10 сек, если открыто
  })

  const notifications = notificationsData?.items || []
  const unreadCount = notifications.filter((n: any) => !n.is_read).length

  // Авто-скролл к последнему сообщению
  useEffect(() => {
    if (activeTab === 'chat' && isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, activeTab, isOpen])

  // Авто-фокус на поле ввода
  useEffect(() => {
    if (activeTab === 'chat' && isOpen) {
      textareaRef.current?.focus()
    }
  }, [activeTab, isOpen])

  // Маркировка уведомлений как прочитанных
  const markAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    }
  })

  // Отправка сообщения в поддержку
  const sendMessageMutation = useMutation({
    mutationFn: supportApi.createRequest,
    onSuccess: () => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          text: 'Сообщение отправлено! Мы ответим вам в ближайшее время.',
          isBot: true,
          timestamp: new Date(),
        }
      ])
      setMessage('')
    },
    onError: () => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          text: 'Ошибка отправки. Попробуйте позже.',
          isBot: true,
          timestamp: new Date(),
        }
      ])
    }
  })

  const handleSendMessage = () => {
    if (!message.trim() || sendMessageMutation.isPending) return

    const userMsg: Message = {
      id: Date.now().toString(),
      text: message.trim(),
      isBot: false,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMsg])
    
    sendMessageMutation.mutate({
      message: message.trim(),
      category: 'question',
      contact: user?.telegram_username || user?.email,
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Если пользователь не авторизован, виджет можно скрыть или показывать заглушку
  if (!user) return null

  return (
    <>
      {/* Кнопка открытия (Floating Action Button) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-[9999] w-14 h-14 rounded-full bg-best-primary text-white shadow-2xl flex items-center justify-center hover:bg-best-primary/90 transition-all hover:scale-110 active:scale-95 animate-in fade-in zoom-in duration-300"
        >
          <MessageSquare className="w-6 h-6" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-[10px] font-bold flex items-center justify-center border-2 border-[#0f0f1a]">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      )}

      {/* Окно виджета */}
      {isOpen && (
        <div
          className={`fixed bottom-20 md:bottom-6 right-4 md:right-6 z-[10000] w-[calc(100vw-2rem)] md:w-[400px] h-[500px] max-h-[80vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden border border-white/10 backdrop-blur-xl bg-[#1a1a2e]/95 animate-in slide-in-from-bottom-10 fade-in duration-300`}
        >
          {/* Хедер */}
          <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/10">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="font-bold text-white text-sm">BEST Assistant</span>
            </div>
            <button 
              onClick={() => setIsOpen(false)}
              className="p-1 hover:bg-white/10 rounded-full transition-colors"
            >
              <ChevronDown className="w-5 h-5 text-white/70" />
            </button>
          </div>

          {/* Табы */}
          <div className="flex p-1 bg-black/20 m-2 rounded-lg">
            <button
              onClick={() => setActiveTab('notifications')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-bold rounded-md transition-all ${
                activeTab === 'notifications' 
                  ? 'bg-white/10 text-white shadow-sm' 
                  : 'text-white/50 hover:text-white/70'
              }`}
            >
              <Bell className="w-3 h-3" />
              Уведомления
              {unreadCount > 0 && (
                <span className="bg-red-500 text-white text-[9px] px-1.5 rounded-full">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-bold rounded-md transition-all ${
                activeTab === 'chat' 
                  ? 'bg-white/10 text-white shadow-sm' 
                  : 'text-white/50 hover:text-white/70'
              }`}
            >
              <MessageSquare className="w-3 h-3" />
              Чат поддержки
            </button>
          </div>

          {/* Контент */}
          <div className="flex-1 overflow-hidden relative">
            
            {/* Уведомления */}
            {activeTab === 'notifications' && (
              <div className="absolute inset-0 overflow-y-auto p-2 space-y-2 animate-in fade-in slide-in-from-left-4 duration-300">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-white/30 gap-2">
                    <Bell className="w-8 h-8" />
                    <span className="text-sm">Нет новых уведомлений</span>
                  </div>
                ) : (
                  <>
                    <div className="flex justify-end px-2">
                      <button 
                        onClick={() => markAsReadMutation.mutate()}
                        className="text-[10px] text-best-primary hover:underline"
                      >
                        Прочитать все
                      </button>
                    </div>
                    {notifications.map((n: any) => (
                      <div 
                        key={n.id} 
                        className={`p-3 rounded-xl border transition-all hover:scale-[1.02] ${
                          n.is_read ? 'bg-white/5 border-white/5' : 'bg-best-primary/10 border-best-primary/30'
                        }`}
                      >
                        <h4 className="text-white text-sm font-bold mb-1">{n.title}</h4>
                        <p className="text-white/70 text-xs leading-relaxed">{n.message}</p>
                        <span className="text-white/30 text-[10px] mt-2 block">
                          {new Date(n.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {/* Чат */}
            {activeTab === 'chat' && (
              <div className="absolute inset-0 flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((msg) => (
                    <div 
                      key={msg.id} 
                      className={`flex ${msg.isBot ? 'justify-start' : 'justify-end'} animate-in zoom-in-95 duration-200`}
                    >
                      <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed ${
                        msg.isBot 
                          ? 'bg-white/10 text-white rounded-tl-sm' 
                          : 'bg-best-primary text-white rounded-tr-sm'
                      }`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                  {sendMessageMutation.isPending && (
                    <div className="flex justify-start">
                      <div className="bg-white/10 p-3 rounded-2xl rounded-tl-sm">
                        <Loader2 className="w-4 h-4 animate-spin text-white/50" />
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <div className="p-3 bg-black/20 border-t border-white/10">
                  <div className="relative">
                    <textarea
                      ref={textareaRef}
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Напишите сообщение..."
                      className="w-full bg-white/5 text-white text-sm rounded-xl pl-4 pr-10 py-3 focus:outline-none focus:bg-white/10 transition-colors resize-none h-[44px] max-h-[100px]"
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={!message.trim() || sendMessageMutation.isPending}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-best-primary rounded-lg text-white disabled:opacity-50 disabled:bg-transparent disabled:text-white/30 transition-all hover:scale-110 active:scale-95"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}