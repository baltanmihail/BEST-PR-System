import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserPlus, AlertCircle, CheckCircle2, Loader2, ArrowLeft, FileText, Shield } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { registrationApi, RegistrationRequest } from '../services/registration'

export default function Register() {
  const { theme } = useThemeStore()
  const { login, user } = useAuthStore()
  const navigate = useNavigate()
  const [agreementAccepted, setAgreementAccepted] = useState(false)
  const [consentAccepted, setConsentAccepted] = useState(false)
  const [agreementContent, setAgreementContent] = useState<string>('')
  const [showAgreement, setShowAgreement] = useState(false)

  // Проверяем, не зарегистрирован ли уже пользователь
  useEffect(() => {
    if (user && user.is_active) {
      navigate('/')
    }
  }, [user, navigate])

  // Получаем пользовательское соглашение
  const { data: agreementData } = useQuery({
    queryKey: ['agreement'],
    queryFn: () => registrationApi.getAgreement(),
  })

  useEffect(() => {
    if (agreementData?.content) {
      setAgreementContent(agreementData.content)
    }
  }, [agreementData])

  const registrationMutation = useMutation({
    mutationFn: (data: RegistrationRequest) => registrationApi.register(data),
    onSuccess: (data) => {
      if (data.access_token) {
        login(data.access_token)
        navigate('/')
      }
    },
  })

  const handleTelegramAuth = () => {
    // Telegram WebApp доступен только в Telegram
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp
      const initDataUnsafe = tg.initDataUnsafe
      const initDataString = tg.initData || ''

      if (initDataUnsafe && initDataUnsafe.user) {
        // Парсим initData строку для получения hash и auth_date
        let hash = ''
        let authDate = Math.floor(Date.now() / 1000) // Fallback на текущее время
        
        if (initDataString) {
          // Парсим URL-encoded строку initData
          const params = new URLSearchParams(initDataString)
          hash = params.get('hash') || ''
          
          const authDateStr = params.get('auth_date')
          if (authDateStr) {
            authDate = parseInt(authDateStr, 10)
          }
        }

        // Если auth_date не найден, пробуем взять из initDataUnsafe
        if (initDataUnsafe.auth_date !== undefined) {
          authDate = initDataUnsafe.auth_date
        }

        // Формируем данные для регистрации
        const telegramAuth: RegistrationRequest['telegram_auth'] = {
          id: initDataUnsafe.user.id,
          first_name: initDataUnsafe.user.first_name || '',
          auth_date: authDate,
          hash: hash,
        }

        // Добавляем опциональные поля только если они есть
        if (initDataUnsafe.user.last_name) {
          telegramAuth.last_name = initDataUnsafe.user.last_name
        }
        if (initDataUnsafe.user.username) {
          telegramAuth.username = initDataUnsafe.user.username
        }
        if (initDataUnsafe.user.photo_url) {
          telegramAuth.photo_url = initDataUnsafe.user.photo_url
        }

        // Проверяем наличие обязательных данных
        if (!hash) {
          console.error('Hash is missing from Telegram initData', { initDataString, initDataUnsafe })
          alert('Ошибка: не удалось получить данные авторизации из Telegram. Убедитесь, что страница открыта через Telegram бота.')
          return
        }

        if (!authDate || authDate === 0) {
          console.error('Auth date is missing or invalid', { authDate, initDataUnsafe })
          alert('Ошибка: не удалось получить дату авторизации из Telegram.')
          return
        }

        const registrationData: RegistrationRequest = {
          telegram_auth: telegramAuth,
          personal_data_consent: {
            consent: consentAccepted,
            date: new Date().toISOString(),
          },
          user_agreement: {
            accepted: agreementAccepted,
            version: agreementData?.version || '1.0',
          },
        }

        console.log('Sending registration request', { 
          telegram_id: telegramAuth.id, 
          has_hash: !!hash, 
          auth_date: authDate 
        })

        registrationMutation.mutate(registrationData)
      } else {
        alert('Не удалось получить данные из Telegram. Откройте эту страницу через Telegram бота.')
      }
    } else {
      // Fallback для браузера - показываем предупреждение с ссылкой на бота
      const botUsername = '@BESTPRSystemBot' // Можно сделать динамическим из конфига
      const botLink = `https://t.me/${botUsername.replace('@', '')}?start=register`
      alert(
        `Для регистрации через Telegram бота:\n\n` +
        `1. Откройте бота: ${botUsername}\n` +
        `2. Нажмите /register или кнопку "Зарегистрироваться"\n\n` +
        `Или откройте эту страницу через Telegram WebApp.\n\n` +
        `Ссылка на бота: ${botLink}`
      )
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center space-x-4 mb-8">
        <Link
          to="/"
          className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        >
          <ArrowLeft className="h-6 w-6 text-white" />
        </Link>
        <div className="flex items-center space-x-3">
          <UserPlus className="h-8 w-8 text-best-primary" />
          <h1 className={`text-3xl md:text-4xl font-bold text-readable ${theme}`}>Регистрация</h1>
        </div>
      </div>

      {/* Форма регистрации */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8 space-y-6`}>
        <div>
          <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
            Присоединяйся к команде PR-отдела!
          </h2>
          <p className={`text-white/80 text-readable ${theme}`}>
            После регистрации твоя заявка будет рассмотрена модераторами. После одобрения ты сможешь брать задачи и зарабатывать баллы!
          </p>
        </div>

        {/* Согласие на обработку персональных данных */}
        <div className={`p-4 bg-white/10 rounded-lg border ${consentAccepted ? 'border-best-primary' : 'border-white/20'}`}>
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={consentAccepted}
              onChange={(e) => setConsentAccepted(e.target.checked)}
              className="mt-1 w-5 h-5 rounded border-white/30 text-best-primary focus:ring-best-primary"
            />
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-1">
                <Shield className="h-5 w-5 text-best-primary" />
                <span className={`text-white font-medium text-readable ${theme}`}>
                  Согласие на обработку персональных данных
                </span>
              </div>
              <p className={`text-white/70 text-sm text-readable ${theme}`}>
                Я даю согласие на обработку моих персональных данных для целей управления задачами и связи со мной.
              </p>
            </div>
          </label>
        </div>

        {/* Пользовательское соглашение */}
        <div className={`p-4 bg-white/10 rounded-lg border ${agreementAccepted ? 'border-best-primary' : 'border-white/20'}`}>
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={agreementAccepted}
              onChange={(e) => setAgreementAccepted(e.target.checked)}
              className="mt-1 w-5 h-5 rounded border-white/30 text-best-primary focus:ring-best-primary"
            />
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-1">
                <FileText className="h-5 w-5 text-best-primary" />
                <span className={`text-white font-medium text-readable ${theme}`}>
                  Пользовательское соглашение
                </span>
              </div>
              <p className={`text-white/70 text-sm text-readable ${theme} mb-2`}>
                Я принимаю условия пользовательского соглашения BEST PR System.
              </p>
              <button
                onClick={() => setShowAgreement(!showAgreement)}
                className="text-best-primary hover:text-best-primary/80 text-sm underline"
              >
                {showAgreement ? 'Скрыть' : 'Прочитать соглашение'}
              </button>
              {showAgreement && (
                <div className={`mt-3 p-3 bg-black/20 rounded-lg max-h-60 overflow-y-auto text-readable ${theme}`}>
                  <pre className="text-white/80 text-xs whitespace-pre-wrap font-sans">
                    {agreementContent || 'Загрузка...'}
                  </pre>
                </div>
              )}
            </div>
          </label>
        </div>

        {/* Ошибки */}
        {registrationMutation.error && (
          <div className={`p-4 bg-red-500/20 border border-red-500/50 rounded-lg`}>
            <div className="flex items-start space-x-2">
              <AlertCircle className="h-5 w-5 text-red-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-white text-sm font-medium mb-1">
                  Ошибка при регистрации
                </p>
                <p className="text-white/80 text-sm">
                  {registrationMutation.error instanceof Error
                    ? registrationMutation.error.message
                    : (registrationMutation.error as any)?.response?.data?.detail || 
                      (registrationMutation.error as any)?.message ||
                      'Произошла ошибка при регистрации. Убедитесь, что страница открыта через Telegram бота.'}
                </p>
                {!(registrationMutation.error as any)?.response?.data?.detail?.includes('Telegram') && (
                  <p className="text-white/60 text-xs mt-2">
                    💡 Попробуйте зарегистрироваться через бота: /register
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Успех */}
        {registrationMutation.isSuccess && (
          <div className={`p-4 bg-green-500/20 border border-green-500/50 rounded-lg`}>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-5 w-5 text-green-400" />
              <p className="text-white text-sm">
                Регистрация успешна! Ваша заявка отправлена на модерацию.
              </p>
            </div>
          </div>
        )}

        {/* Предупреждение если не в Telegram */}
        {!window.Telegram?.WebApp && (
          <div className={`p-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg`}>
            <div className="flex items-start space-x-2">
              <AlertCircle className="h-5 w-5 text-yellow-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-white text-sm font-medium mb-2">
                  Для регистрации на сайте необходимо открыть эту страницу через Telegram бота
                </p>
                <p className="text-white/80 text-sm mb-3">
                  Или зарегистрируйтесь прямо в боте:
                </p>
                <a
                  href="https://t.me/BESTPRSystemBot?start=register"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center space-x-2 text-best-primary hover:text-best-primary/80 text-sm font-medium underline"
                >
                  <span>Открыть бота</span>
                  <span>→</span>
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Кнопка регистрации */}
        <button
          onClick={handleTelegramAuth}
          disabled={!agreementAccepted || !consentAccepted || registrationMutation.isPending}
          className={`w-full bg-best-primary text-white py-3 px-6 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2`}
        >
          {registrationMutation.isPending ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Регистрация...</span>
            </>
          ) : (
            <>
              <UserPlus className="h-5 w-5" />
              <span>Зарегистрироваться</span>
            </>
          )}
        </button>

        <p className={`text-white/60 text-sm text-center text-readable ${theme}`}>
          {window.Telegram?.WebApp 
            ? "Нажмите кнопку выше для завершения регистрации"
            : "Откройте эту страницу через Telegram бота или зарегистрируйтесь прямо в боте"}
        </p>
      </div>
    </div>
  )
}
