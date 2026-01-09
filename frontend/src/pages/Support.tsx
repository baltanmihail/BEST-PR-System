import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { MessageSquare, Send, CheckCircle2, AlertCircle, HelpCircle, Lightbulb, Paperclip, Link as LinkIcon, X, MapPin } from 'lucide-react'
import { supportApi } from '../services/support'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { useTour } from '../hooks/useTour'

type SupportType = 'question' | 'suggestion' | null

export default function Support() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const { startTour } = useTour()
  const location = useLocation()
  
  // Определяем тип тура на основе текущей страницы
  const getTourType = () => {
    const path = location.pathname
    if (path === '/') return 'home'
    if (path === '/tasks') return 'tasks'
    if (path === '/calendar') return 'calendar'
    if (path === '/gallery') return 'gallery'
    if (path === '/equipment') return 'equipment'
    if (path === '/settings') return 'settings'
    if (path === '/users') return 'users'
    if (path === '/support') return 'support'
    return 'home'
  }
  const [supportType, setSupportType] = useState<SupportType>(null)
  const [message, setMessage] = useState('')
  const [link, setLink] = useState('')
  const [attachedFile, setAttachedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: supportApi.createRequest,
    onSuccess: () => {
      setMessage('')
      setLink('')
      setAttachedFile(null)
      setSupportType(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      queryClient.invalidateQueries({ queryKey: ['support'] })
    },
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim() || !supportType) return

    mutation.mutate({
      message: message.trim(),
      category: supportType === 'question' ? 'question' : 'suggestion',
      contact: user?.telegram_username || user?.username || user?.email || undefined,
      link: link.trim() || undefined,
      file: attachedFile || undefined,
    })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.size > 10 * 1024 * 1024) { // 10MB
        alert('Файл слишком большой. Максимальный размер: 10MB')
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
        return
      }
      setAttachedFile(file)
    }
  }

  if (!supportType) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className={`glass-enhanced ${theme} rounded-2xl p-8 text-white`} data-tour="support-header">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <MessageSquare className="h-8 w-8 text-best-primary" />
              <h1 className={`text-3xl font-bold text-white text-readable ${theme}`}>Поддержка</h1>
            </div>
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                const tourType = getTourType()
                console.log('Starting tour with type:', tourType)
                startTour(tourType)
              }}
              className="flex items-center space-x-2 px-4 py-2 bg-best-primary/20 hover:bg-best-primary/30 text-white rounded-lg transition-all border border-best-primary/50"
              title="Запустить интерактивный гайд по сайту"
            >
              <MapPin className="h-4 w-4" />
              <span className="text-sm">Гайд по сайту</span>
            </button>
          </div>
          <p className={`text-white/80 text-readable ${theme} mb-8`}>
            Выберите цель обращения
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              onClick={() => setSupportType('question')}
              className={`glass-enhanced ${theme} rounded-xl p-6 hover:bg-white/10 transition-all border border-white/20 hover:border-best-primary text-left`}
            >
              <HelpCircle className="h-8 w-8 text-best-primary mb-4" />
              <h3 className={`text-xl font-semibold text-white mb-2 text-readable ${theme}`}>
                Есть вопросы?
              </h3>
              <p className={`text-white/70 text-sm text-readable ${theme}`}>
                Напишите нам, и мы поможем! Задайте любой вопрос о системе, задачах или оборудовании.
              </p>
            </button>

            <button
              onClick={() => setSupportType('suggestion')}
              className={`glass-enhanced ${theme} rounded-xl p-6 hover:bg-white/10 transition-all border border-white/20 hover:border-best-primary text-left`}
            >
              <Lightbulb className="h-8 w-8 text-best-accent mb-4" />
              <h3 className={`text-xl font-semibold text-white mb-2 text-readable ${theme}`}>
                Предложение, идея или сценарий
              </h3>
              <p className={`text-white/70 text-sm text-readable ${theme}`}>
                Поделитесь своими идеями! Можно прикрепить ссылку или файл с подробным описанием.
              </p>
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className={`glass-enhanced ${theme} rounded-2xl p-6 md:p-8 text-white`}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            {supportType === 'question' ? (
              <HelpCircle className="h-8 w-8 text-best-primary" />
            ) : (
              <Lightbulb className="h-8 w-8 text-best-accent" />
            )}
            <h1 className={`text-2xl md:text-3xl font-bold text-white text-readable ${theme}`}>
              {supportType === 'question' ? 'Задать вопрос' : 'Отправить предложение'}
            </h1>
          </div>
          <button
            onClick={() => {
              setSupportType(null)
              setMessage('')
              setLink('')
              setAttachedFile(null)
            }}
            className="p-2 hover:bg-white/20 rounded-lg transition-all"
          >
            <X className="h-5 w-5 text-white" />
          </button>
        </div>

        {mutation.isSuccess && (
          <div className={`mb-6 p-4 bg-green-500/20 border border-green-500/50 rounded-lg flex items-center space-x-3`}>
            <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0" />
            <p className="text-white">Ваше сообщение отправлено! Мы свяжемся с вами в ближайшее время.</p>
          </div>
        )}

        {mutation.isError && (
          <div className={`mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-lg flex items-center space-x-3`}>
            <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
            <p className="text-white">Ошибка при отправке сообщения. Попробуйте позже.</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" encType="multipart/form-data">
          <div>
            <label className={`block text-white mb-2 text-readable ${theme}`}>
              Ваше сообщение *
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              rows={6}
              className={`w-full bg-white/10 border border-white/30 rounded-lg p-4 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} resize-none`}
              placeholder={
                supportType === 'question'
                  ? 'Опишите ваш вопрос...'
                  : 'Опишите вашу идею, предложение или сценарий...'
              }
            />
          </div>

          {supportType === 'suggestion' && (
            <>
              <div>
                <label className={`block text-white mb-2 text-readable ${theme}`}>
                  <LinkIcon className="h-4 w-4 inline mr-2" />
                  Ссылка (опционально)
                </label>
                <input
                  type="url"
                  value={link}
                  onChange={(e) => setLink(e.target.value)}
                  className={`w-full bg-white/10 border border-white/30 rounded-lg p-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  placeholder="https://example.com"
                />
              </div>

              <div>
                <label className={`block text-white mb-2 text-readable ${theme}`}>
                  <Paperclip className="h-4 w-4 inline mr-2" />
                  Прикрепить файл (опционально)
                </label>
                <div className="flex items-center space-x-4">
                  <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                    accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.zip,.rar"
                  />
                  <label
                    htmlFor="file-upload"
                    className={`flex-1 bg-white/10 border border-white/30 rounded-lg p-3 text-white cursor-pointer hover:bg-white/20 transition-all text-readable ${theme} text-center text-sm md:text-base`}
                  >
                    {attachedFile ? (
                      <span className="truncate block max-w-xs mx-auto">{attachedFile.name}</span>
                    ) : (
                      'Выберите файл (макс. 10MB)'
                    )}
                  </label>
                  {attachedFile && (
                    <button
                      type="button"
                      onClick={() => {
                        setAttachedFile(null)
                        if (fileInputRef.current) {
                          fileInputRef.current.value = ''
                        }
                      }}
                      className="p-2 hover:bg-white/20 rounded-lg transition-all flex-shrink-0"
                      aria-label="Удалить файл"
                    >
                      <X className="h-5 w-5 text-white" />
                    </button>
                  )}
                </div>
                {attachedFile && (
                  <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
                    Размер: {(attachedFile.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                )}
              </div>
            </>
          )}

          <div className="flex space-x-4">
            <button
              type="button"
              onClick={() => {
                setSupportType(null)
                setMessage('')
                setLink('')
                setAttachedFile(null)
              }}
              className="flex-1 bg-white/10 text-white px-6 py-3 rounded-lg font-semibold hover:bg-white/20 transition-all"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !message.trim()}
              className="flex-1 bg-best-primary text-white px-6 py-3 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
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
          </div>
        </form>
      </div>
    </div>
  )
}
