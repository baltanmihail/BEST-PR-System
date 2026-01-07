import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Send, CheckCircle2, AlertCircle } from 'lucide-react'
import { supportApi } from '../services/support'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'

export default function Support() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const [message, setMessage] = useState('')
  const [contact, setContact] = useState('')
  const [category, setCategory] = useState('')

  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: supportApi.createRequest,
    onSuccess: () => {
      setMessage('')
      setContact('')
      setCategory('')
      queryClient.invalidateQueries({ queryKey: ['support'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim()) return

    mutation.mutate({
      message: message.trim(),
      contact: contact.trim() || undefined,
      category: category || undefined,
    })
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className={`glass-enhanced ${theme} rounded-2xl p-8 mb-8 text-white`}>
        <div className="flex items-center space-x-3 mb-6">
          <MessageSquare className="h-8 w-8 text-best-primary" />
          <h1 className={`text-3xl font-bold text-white text-readable ${theme}`}>Поддержка</h1>
        </div>
        <p className={`text-white/80 text-readable ${theme} mb-6`}>
          Есть вопросы? Напишите нам, и мы поможем!
        </p>

        {mutation.isSuccess && (
          <div className={`mb-6 p-4 bg-green-500/20 border border-green-500/50 rounded-lg flex items-center space-x-3`}>
            <CheckCircle2 className="h-5 w-5 text-green-400" />
            <p className="text-white">Ваш запрос отправлен! Мы свяжемся с вами в ближайшее время.</p>
          </div>
        )}

        {mutation.isError && (
          <div className={`mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-lg flex items-center space-x-3`}>
            <AlertCircle className="h-5 w-5 text-red-400" />
            <p className="text-white">Ошибка при отправке запроса. Попробуйте позже.</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={`block text-white mb-2 text-readable ${theme}`}>
              Ваше сообщение *
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              rows={6}
              className={`w-full bg-white/10 border border-white/30 rounded-lg p-4 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              placeholder="Опишите ваш вопрос или проблему..."
            />
          </div>

          {!user && (
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Контакт (Telegram username или email)
              </label>
              <input
                type="text"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                className={`w-full bg-white/10 border border-white/30 rounded-lg p-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                placeholder="@username или email@example.com"
              />
            </div>
          )}

          <div>
            <label className={`block text-white mb-2 text-readable ${theme}`}>
              Категория (опционально)
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={`w-full bg-white/10 border border-white/30 rounded-lg p-3 text-white focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
            >
              <option value="">Выберите категорию</option>
              <option value="technical">Техническая проблема</option>
              <option value="task">Вопрос по задаче</option>
              <option value="registration">Регистрация</option>
              <option value="other">Другое</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={mutation.isPending || !message.trim()}
            className="w-full bg-best-primary text-white px-6 py-3 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          >
            {mutation.isPending ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                <span>Отправка...</span>
              </>
            ) : (
              <>
                <Send className="h-5 w-5" />
                <span>Отправить</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
