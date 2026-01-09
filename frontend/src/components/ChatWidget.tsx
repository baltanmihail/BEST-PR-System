import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Loader2 } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { supportApi } from '../services/support'
import { useMutation } from '@tanstack/react-query'

interface Message {
  id: string
  text: string
  isBot: boolean
  timestamp: Date
}

export default function ChatWidget() {
  const { user } = useAuthStore()
  const { theme } = useThemeStore()
  const [isOpen, setIsOpen] = useState(false)
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (isOpen) {
      scrollToBottom()
      inputRef.current?.focus()
    }
  }, [isOpen, messages])

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

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 w-14 h-14 bg-best-primary rounded-full shadow-lg hover:bg-best-primary/80 transition-all flex items-center justify-center z-50`}
        aria-label="Открыть чат"
      >
        <MessageSquare className="h-6 w-6 text-white" />
      </button>
    )
  }

  return (
    <>
      {/* Backdrop overlay - как на hyper3d.ai */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-md z-[9998] transition-opacity duration-300"
        onClick={() => setIsOpen(false)}
        style={{ 
          pointerEvents: isOpen ? 'auto' : 'none', 
          opacity: isOpen ? 1 : 0,
          visibility: isOpen ? 'visible' : 'hidden'
        }}
      />
      {/* Чат виджет - поверх всего, правильно центрирован */}
      <div
        className={`fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100vw-2rem)] md:w-96 max-w-md h-[calc(100vh-8rem)] md:h-[600px] max-h-[90vh] flex flex-col glass-enhanced ${theme} rounded-2xl shadow-2xl z-[9999] border border-white/30 transition-all duration-300`}
        style={{ 
          pointerEvents: isOpen ? 'auto' : 'none', 
          opacity: isOpen ? 1 : 0, 
          transform: isOpen ? 'translate(-50%, -50%) scale(1)' : 'translate(-50%, -50%) scale(0.95)',
          visibility: isOpen ? 'visible' : 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
      {/* Заголовок */}
      <div className="flex items-center justify-between p-4 border-b border-white/20">
        <div className="flex items-center space-x-2">
          <MessageSquare className="h-5 w-5 text-best-primary" />
          <h3 className={`text-white font-semibold text-readable ${theme}`}>Чат поддержки</h3>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 hover:bg-white/20 rounded-lg transition-all"
          aria-label="Закрыть чат"
        >
          <X className="h-4 w-4 text-white" />
        </button>
      </div>

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
    </div>
    </>
  )
}
