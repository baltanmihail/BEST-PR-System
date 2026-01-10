import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserPlus, AlertCircle, CheckCircle2, Loader2, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { registrationApi, RegistrationRequest } from '../services/registration'

type RegistrationMode = 'telegram'

export default function Register() {
  const { theme } = useThemeStore()
  const { login, user } = useAuthStore()
  const navigate = useNavigate()
  const [agreementAccepted, setAgreementAccepted] = useState(false)
  const [consentAccepted, setConsentAccepted] = useState(false)
  const [agreementContent, setAgreementContent] = useState<string>('')
  const [showAgreement, setShowAgreement] = useState(false)
  const [registrationMode, setRegistrationMode] = useState<RegistrationMode>('telegram')
  const [fullName, setFullName] = useState<string>('')
  
  // Проверяем параметры из URL (если пользователь перешёл через бота или QR-код)
  const urlParams = new URLSearchParams(window.location.search)
  const fromBot = urlParams.get('from') === 'bot'
  const qrToken = urlParams.get('qr_token')
  const telegramId = urlParams.get('telegram_id')
  const username = urlParams.get('username')
  const firstName = urlParams.get('first_name')
  
  // Регистрация через Telegram WebApp или через QR-код (упрощённая)

  // Инициализируем ФИО из Telegram данных, если доступны
  useEffect(() => {
    if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
      const tgUser = window.Telegram.WebApp.initDataUnsafe.user
      const tgFullName = tgUser.last_name 
        ? `${tgUser.first_name || ''} ${tgUser.last_name || ''}`.trim()
        : (tgUser.first_name || '')
      if (tgFullName && !fullName) {
        setFullName(tgFullName)
      }
    } else if (firstName && !fullName) {
      // Если есть firstName из URL параметров
      const urlFullName = firstName
      setFullName(urlFullName)
    }
  }, [firstName])

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

  // Регистрация доступна через Telegram WebApp или через QR-код (упрощённая)
  useEffect(() => {
    if (qrToken && fromBot && telegramId) {
      // Регистрация через QR-код - упрощённая, не требует WebApp
      setRegistrationMode('telegram')
    } else if (!window.Telegram?.WebApp) {
      // Если не в Telegram и нет QR-токена, перенаправляем на страницу входа
      navigate('/login')
    } else {
      setRegistrationMode('telegram')
    }
  }, [navigate, qrToken, fromBot, telegramId])

  const handleTelegramAuth = () => {
    // Если есть QR-токен, используем упрощённую регистрацию
    // ВАЖНО: telegram_id может быть пустым в URL, но QR-сессия содержит его
    if (qrToken) {
      // Упрощённая регистрация через QR-код
      // Данные пользователя уже подтверждены через бота, hash не нужен
      // telegram_auth опционален для QR-регистрации - если есть данные, используем их
      // ВАЖНО: ФИО должно быть указано пользователем вручную, не используем данные из Telegram!
      if (!fullName.trim()) {
        alert('Пожалуйста, укажите ваше ФИО')
        return
      }
      
      const registrationData: RegistrationRequest = {
        personal_data_consent: {
          consent: consentAccepted,
          consent_date: new Date().toISOString(),
        },
        user_agreement: {
          accepted: agreementAccepted,
          version: agreementData?.version || '1.0',
        },
        qr_token: qrToken,
        full_name: fullName.trim(),  // ОБЯЗАТЕЛЬНО - введено пользователем вручную
      }
      
      // Если есть данные пользователя в URL (fromBot=true и telegramId есть) - добавляем их
      if (fromBot && telegramId) {
        const telegramAuth: RegistrationRequest['telegram_auth'] = {
          id: parseInt(telegramId),
          first_name: firstName || 'Пользователь',
          auth_date: Math.floor(Date.now() / 1000),
          hash: '', // Для QR-регистрации hash не проверяется на бэкенде
        }
        
        if (username) {
          telegramAuth.username = username
        }
        
        registrationData.telegram_auth = telegramAuth
        
        console.log('Sending QR registration request with auth data', { 
          telegram_id: telegramAuth.id, 
          qr_token: qrToken 
        })
      } else {
        // QR-регистрация без данных в URL - бэкенд использует данные из QR-сессии
        console.log('Sending QR registration request without auth data (will use QR session data)', { 
          qr_token: qrToken 
        })
      }
      
      registrationMutation.mutate(registrationData)
      return
    }
    
    // Обычная регистрация через Telegram WebApp
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

        // ВАЖНО: ФИО должно быть указано пользователем вручную, не используем данные из Telegram!
        if (!fullName.trim()) {
          alert('Пожалуйста, укажите ваше ФИО')
          return
        }
        
        const registrationData: RegistrationRequest = {
          telegram_auth: telegramAuth,
          personal_data_consent: {
            consent: consentAccepted,
            consent_date: new Date().toISOString(),
          },
          user_agreement: {
            accepted: agreementAccepted,
            version: agreementData?.version || '1.0',
          },
          full_name: fullName.trim(),  // ОБЯЗАТЕЛЬНО - введено пользователем вручную
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
      <div className="flex flex-col md:flex-row md:items-center md:space-x-4 mb-6 md:mb-8 gap-4">
        <div className="flex items-center space-x-3 md:space-x-4">
          <Link
            to="/"
            className="p-2 rounded-lg hover:bg-white/10 transition-colors touch-manipulation"
            aria-label="На главную"
          >
            <ArrowLeft className="h-5 w-5 md:h-6 md:w-6 text-white" />
          </Link>
          <div className="flex items-center space-x-2 md:space-x-3">
            <UserPlus className="h-6 w-6 md:h-8 md:w-8 text-best-primary" />
            <h1 className={`text-2xl md:text-3xl lg:text-4xl font-bold text-readable ${theme}`}>Регистрация</h1>
          </div>
        </div>
      </div>

      {/* Форма регистрации */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8 space-y-6`}>
        <div>
          <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
            Присоединяйся к команде PR-отдела!
          </h2>
          <p className={`text-white/80 text-readable ${theme}`}>
            {window.Telegram?.WebApp ? (
              <>
                Заполни форму ниже - все данные уже подтянуты из Telegram! После регистрации твоя заявка будет рассмотрена модераторами. После одобрения ты сможешь брать задачи и зарабатывать баллы!
              </>
            ) : (
              <>
                После регистрации твоя заявка будет рассмотрена модераторами. После одобрения ты сможешь брать задачи и зарабатывать баллы!
              </>
            )}
          </p>
        </div>

        {/* Поле для ввода ФИО */}
        <div>
          <label className={`block text-white mb-2 text-readable ${theme}`}>
            ФИО (обязательно) *
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Введите ваше полное имя (Фамилия Имя Отчество)"
            required
            className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border ${
              fullName.trim() ? 'border-best-primary' : 'border-white/20'
            } focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40`}
          />
          <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
            ⚠️ Укажите ваше <strong>правильное</strong> полное имя (Фамилия Имя Отчество). Данные из Telegram не используются.
          </p>
        </div>

        {/* Согласия (компактно) */}
        <div className={`p-3 bg-white/10 rounded-lg border ${(consentAccepted && agreementAccepted) ? 'border-best-primary' : 'border-white/20'}`}>
          <label className="flex items-start space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={consentAccepted && agreementAccepted}
              onChange={(e) => {
                setConsentAccepted(e.target.checked)
                setAgreementAccepted(e.target.checked)
              }}
              className="mt-1 w-4 h-4 rounded border-white/30 text-best-primary focus:ring-best-primary"
            />
            <div className="flex-1 text-sm">
              <span className={`text-white text-readable ${theme}`}>
                Я принимаю{' '}
                <button
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setShowAgreement(true)
                  }}
                  className="text-best-primary hover:text-best-primary/80 underline"
                >
                  пользовательское соглашение
                </button>
                {' '}и даю согласие на обработку персональных данных
              </span>
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

        {/* Информация о регистрации */}
        {!window.Telegram?.WebApp && (
          <div className={`p-4 bg-blue-500/20 border border-blue-500/50 rounded-lg`}>
            <div className="flex items-start space-x-2">
              <AlertCircle className="h-5 w-5 text-blue-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-white text-sm font-medium mb-2">
                  Регистрация доступна только через Telegram
                </p>
                <p className="text-white/80 text-sm mb-3">
                  Для регистрации откройте эту страницу через Telegram бота{' '}
                  <a 
                    href="https://t.me/BESTPRSystemBot" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-best-primary hover:underline"
                  >
                    @BESTPRSystemBot
                  </a>
                </p>
                <Link
                  to="/login"
                  className="inline-block text-best-primary hover:text-best-primary/80 text-sm underline"
                >
                  Или войдите через QR-код →
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Кнопка регистрации через Telegram WebApp */}
        {registrationMode === 'telegram' && (
          <>
            <button
              onClick={handleTelegramAuth}
              disabled={!agreementAccepted || !consentAccepted || !fullName.trim() || registrationMutation.isPending}
              className={`w-full bg-best-primary text-white py-3 px-6 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 card-3d touch-manipulation`}
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
              {window.Telegram?.WebApp ? (
                <>Нажмите кнопку выше для завершения регистрации. Все данные уже подтянуты из Telegram!</>
              ) : qrToken ? (
                <>Нажмите кнопку выше для завершения регистрации через QR-код</>
              ) : (
                <>Для регистрации откройте эту страницу через Telegram бота</>
              )}
            </p>
          </>
        )}
      </div>

      {/* Модальное окно для пользовательского соглашения */}
      {showAgreement && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowAgreement(false)}
        >
          <div 
            className={`glass-enhanced ${theme} rounded-xl p-6 max-w-2xl max-h-[80vh] overflow-y-auto w-full`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-2xl font-bold text-white text-readable ${theme}`}>
                Пользовательское соглашение
              </h2>
              <button
                onClick={() => setShowAgreement(false)}
                className="text-white/70 hover:text-white text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <div className={`text-white/80 text-sm whitespace-pre-wrap text-readable ${theme}`}>
              {agreementContent || 'Загрузка...'}
            </div>
            <button
              onClick={() => setShowAgreement(false)}
              className="mt-4 w-full bg-best-primary text-white py-2 px-4 rounded-lg hover:bg-best-primary/80 transition-all"
            >
              Закрыть
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
