import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Loader2, Bell, ChevronDown, ArrowLeft, User as UserIcon } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { supportApi, SupportTicket } from '../services/support'
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
      text: 'Привет! Если у тебя есть вопрос или предложение, напиши его здесь, и мы передадим его команде.',
      isBot: true,
      timestamp: new Date(),
    },
  ])
  const [replyingTo, setReplyingTo] = useState<SupportTicket | null>(null)
  const [replyText, setReplyText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()

  const isAdmin = user?.role === 'vp4pr' ||
    user?.role === 'coordinator_smm' ||
    user?.role === 'coordinator_design' ||
    user?.role === 'coordinator_channel' ||
    user?.role === 'coordinator_prfr'

  const { data: notificationsData } = useQuery({
    queryKey: ['notifications', 'widget'],
    queryFn: () => notificationsApi.getNotifications({ limit: 20 }),
    enabled: isOpen && activeTab === 'notifications' && !!user,
    refetchInterval: isOpen ? 10000 : false,
  })

  const { data: ticketsData, refetch: refetchTickets } = useQuery({
    queryKey: ['support-tickets'],
    queryFn: () => supportApi.getTickets(30),
    enabled: isOpen && activeTab === 'chat' && isAdmin && !!user,
    refetchInterval: isOpen && activeTab === 'chat' && isAdmin ? 15000 : false,
  })

  const notifications = notificationsData?.items || []
  const unreadCount = notifications.filter((n: any) => !n.is_read).length
  const tickets = ticketsData?.items || []

  useEffect(() => {
    if (activeTab === 'chat' && isOpen && !isAdmin) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, activeTab, isOpen, isAdmin])

  useEffect(() => {
    if (activeTab === 'chat' && isOpen && !isAdmin) {
      textareaRef.current?.focus()
    }
  }, [activeTab, isOpen, isAdmin])

  const markAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const sendMessageMutation = useMutation({
    mutationFn: supportApi.createRequest,
    onSuccess: () => {
      setMessages(prev => [
        ...prev,
        { id: Date.now().toString(), text: 'Сообщение отправлено! Мы ответим вам в ближайшее время.', isBot: true, timestamp: new Date() },
      ])
      setMessage('')
    },
    onError: () => {
      setMessages(prev => [
        ...prev,
        { id: Date.now().toString(), text: 'Ошибка отправки. Попробуйте позже.', isBot: true, timestamp: new Date() },
      ])
    },
  })

  const replyMutation = useMutation({
    mutationFn: supportApi.reply,
    onSuccess: () => {
      setReplyText('')
      setReplyingTo(null)
      refetchTickets()
    },
  })

  const handleSendMessage = () => {
    if (!message.trim() || sendMessageMutation.isPending) return
    setMessages(prev => [...prev, { id: Date.now().toString(), text: message.trim(), isBot: false, timestamp: new Date() }])
    sendMessageMutation.mutate({
      message: message.trim(),
      category: 'question',
      contact: user?.telegram_username || user?.email,
    })
  }

  const handleReply = () => {
    if (!replyText.trim() || !replyingTo?.user_telegram_id || replyMutation.isPending) return
    replyMutation.mutate({
      user_telegram_id: replyingTo.user_telegram_id,
      user_name: replyingTo.user_name,
      message: replyText.trim(),
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (isAdmin && replyingTo) handleReply()
      else handleSendMessage()
    }
  }

  if (!user) return null

  const formatTime = (iso: string | null) => {
    if (!iso) return ''
    const d = new Date(iso)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    if (isToday) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString('ru', { day: '2-digit', month: '2-digit' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <>
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

      {isOpen && (
        <div
          className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-[10000] w-[calc(100vw-2rem)] md:w-[400px] h-[500px] max-h-[80vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden border border-white/10 backdrop-blur-xl bg-[#1a1a2e]/95 animate-in slide-in-from-bottom-10 fade-in duration-300 isolate"
          style={{ cursor: 'auto', isolation: 'isolate', pointerEvents: 'auto' }}
          onWheel={(e) => e.stopPropagation()}
          onTouchMove={(e) => e.stopPropagation()}
          onScroll={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/10">
            <div className="flex items-center gap-2">
              {replyingTo && (
                <button onClick={() => setReplyingTo(null)} className="p-0.5 hover:bg-white/10 rounded-full">
                  <ArrowLeft className="w-4 h-4 text-white/70" />
                </button>
              )}
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="font-bold text-white text-sm">
                {replyingTo ? `Ответ: ${replyingTo.user_name}` : 'BEST Assistant'}
              </span>
            </div>
            <button onClick={() => { setIsOpen(false); setReplyingTo(null) }} className="p-1 hover:bg-white/10 rounded-full transition-colors">
              <ChevronDown className="w-5 h-5 text-white/70" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex p-1 bg-black/20 m-2 rounded-lg">
            <button
              onClick={() => { setActiveTab('notifications'); setReplyingTo(null) }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-bold rounded-md transition-all ${
                activeTab === 'notifications' ? 'bg-white/10 text-white shadow-sm' : 'text-white/50 hover:text-white/70'
              }`}
            >
              <Bell className="w-3 h-3" />
              Уведомления
              {unreadCount > 0 && <span className="bg-red-500 text-white text-[9px] px-1.5 rounded-full">{unreadCount}</span>}
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-bold rounded-md transition-all ${
                activeTab === 'chat' ? 'bg-white/10 text-white shadow-sm' : 'text-white/50 hover:text-white/70'
              }`}
            >
              <MessageSquare className="w-3 h-3" />
              {isAdmin ? 'Запросы' : 'Чат поддержки'}
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-hidden relative">

            {/* Notifications */}
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
                      <button onClick={() => markAsReadMutation.mutate()} className="text-[10px] text-best-primary hover:underline">
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
                          {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}

            {/* Chat — Admin: Support Tickets */}
            {activeTab === 'chat' && isAdmin && !replyingTo && (
              <div className="absolute inset-0 overflow-y-auto p-2 space-y-2 animate-in fade-in slide-in-from-right-4 duration-300">
                {tickets.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-white/30 gap-2">
                    <MessageSquare className="w-8 h-8" />
                    <span className="text-sm">Нет запросов в поддержку</span>
                  </div>
                ) : (
                  tickets.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => { if (t.user_telegram_id) setReplyingTo(t) }}
                      className={`w-full text-left p-3 rounded-xl border transition-all hover:scale-[1.01] ${
                        t.is_read ? 'bg-white/5 border-white/5' : 'bg-best-primary/10 border-best-primary/30'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1.5">
                          <UserIcon className="w-3 h-3 text-white/50" />
                          <span className="text-white text-xs font-bold">{t.user_name}</span>
                        </div>
                        <span className="text-white/30 text-[10px]">{formatTime(t.created_at)}</span>
                      </div>
                      {t.category && <span className="text-best-primary text-[10px] mb-1 block">{t.category}</span>}
                      <p className="text-white/70 text-xs leading-relaxed line-clamp-2">{t.message}</p>
                      {t.user_telegram_id && (
                        <span className="text-best-primary text-[10px] mt-1 block">Нажмите для ответа</span>
                      )}
                    </button>
                  ))
                )}
              </div>
            )}

            {/* Chat — Admin: Reply */}
            {activeTab === 'chat' && isAdmin && replyingTo && (
              <div className="absolute inset-0 flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  <div className="bg-white/5 p-3 rounded-xl border border-white/10">
                    <div className="flex items-center gap-1.5 mb-1">
                      <UserIcon className="w-3 h-3 text-white/50" />
                      <span className="text-white text-xs font-bold">{replyingTo.user_name}</span>
                      <span className="text-white/30 text-[10px] ml-auto">{formatTime(replyingTo.created_at)}</span>
                    </div>
                    <p className="text-white/70 text-xs">{replyingTo.contact}</p>
                    <p className="text-white text-sm mt-2 whitespace-pre-wrap">{replyingTo.message}</p>
                  </div>
                  {replyMutation.isSuccess && (
                    <div className="bg-green-500/20 border border-green-500/30 p-2 rounded-lg text-green-300 text-xs text-center">
                      Ответ отправлен в Telegram
                    </div>
                  )}
                  {replyMutation.isError && (
                    <div className="bg-red-500/20 border border-red-500/30 p-2 rounded-lg text-red-300 text-xs text-center">
                      Ошибка отправки
                    </div>
                  )}
                </div>
                <div className="p-3 bg-black/20 border-t border-white/10">
                  <div className="relative">
                    <textarea
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Написать ответ..."
                      className="w-full bg-white/5 text-white text-sm rounded-xl pl-4 pr-10 py-3 focus:outline-none focus:bg-white/10 transition-colors resize-none h-[44px] max-h-[100px]"
                      autoFocus
                    />
                    <button
                      onClick={handleReply}
                      disabled={!replyText.trim() || replyMutation.isPending}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-best-primary rounded-lg text-white disabled:opacity-50 disabled:bg-transparent disabled:text-white/30 transition-all hover:scale-110 active:scale-95"
                    >
                      {replyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Chat — Regular user */}
            {activeTab === 'chat' && !isAdmin && (
              <div className="absolute inset-0 flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.isBot ? 'justify-start' : 'justify-end'} animate-in zoom-in-95 duration-200`}>
                      <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed ${
                        msg.isBot ? 'bg-white/10 text-white rounded-tl-sm' : 'bg-best-primary text-white rounded-tr-sm'
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
