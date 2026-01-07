import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { UserPlus, AlertCircle, CheckCircle2, Loader2, ArrowLeft, MessageSquare, Key } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { registrationApi, RegistrationRequest } from '../services/registration'

type RegistrationMode = 'telegram' | 'code'

export default function Register() {
  const { theme } = useThemeStore()
  const { login, user } = useAuthStore()
  const navigate = useNavigate()
  const [agreementAccepted, setAgreementAccepted] = useState(false)
  const [consentAccepted, setConsentAccepted] = useState(false)
  const [agreementContent, setAgreementContent] = useState<string>('')
  const [showAgreement, setShowAgreement] = useState(false)
  const [registrationMode, setRegistrationMode] = useState<RegistrationMode>('telegram')
  
  // Для регистрации через код
  const [telegramInput, setTelegramInput] = useState<string>('') // Единое поле для ID или username
  const [verificationCode, setVerificationCode] = useState<string>('')
  const [codeRequested, setCodeRequested] = useState(false)

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

  const codeRequestMutation = useMutation({
    mutationFn: (data: { telegram_id?: number; telegram_username?: string }) => 
      registrationApi.requestCode(data),
    onSuccess: () => {
      setCodeRequested(true)
    },
  })

  const codeRegistrationMutation = useMutation({
    mutationFn: (data: { code: string; personal_data_consent: any; user_agreement: any }) =>
      registrationApi.registerWithCode(data),
    onSuccess: (data) => {
      if (data.access_token) {
        login(data.access_token)
        navigate('/')
      }
    },
  })

  // Автоматически определяем режим регистрации
  useEffect(() => {
    if (!window.Telegram?.WebApp) {
      setRegistrationMode('code')
    }
  }, [])

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

        {/* Переключатель режима регистрации */}
        {window.Telegram?.WebApp && (
          <div className={`p-4 bg-white/5 rounded-lg border border-white/10`}>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setRegistrationMode('telegram')}
                className={`flex-1 py-2 px-4 rounded-lg transition-all ${
                  registrationMode === 'telegram'
                    ? 'bg-best-primary text-white'
                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                }`}
              >
                <div className="flex items-center justify-center space-x-2">
                  <MessageSquare className="h-4 w-4" />
                  <span>Через Telegram</span>
                </div>
              </button>
              <button
                onClick={() => setRegistrationMode('code')}
                className={`flex-1 py-2 px-4 rounded-lg transition-all ${
                  registrationMode === 'code'
                    ? 'bg-best-primary text-white'
                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                }`}
              >
                <div className="flex items-center justify-center space-x-2">
                  <Key className="h-4 w-4" />
                  <span>Через код</span>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* Форма регистрации через код */}
        {registrationMode === 'code' && (
          <div className="space-y-4">
            {!codeRequested ? (
              <>
                <div>
                  <label className={`block text-white text-sm font-medium mb-2 text-readable ${theme}`}>
                    Telegram ID или Username
                  </label>
                  <input
                    type="text"
                    placeholder="Введите ID (123456789) или username (@username)"
                    value={telegramInput}
                    onChange={(e) => setTelegramInput(e.target.value)}
                    className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary"
                  />
                  <p className="text-white/60 text-xs mt-2">
                    💡 Бот автоматически определит, что вы ввели. Начните диалог с{' '}
                    <a 
                      href="https://t.me/BESTPRSystemBot" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-best-primary hover:underline"
                    >
                      @BESTPRSystemBot
                    </a>
                  </p>
                  <details className="mt-2">
                    <summary className="text-white/70 text-xs cursor-pointer hover:text-white">
                      Как узнать свой Telegram ID?
                    </summary>
                    <div className="mt-2 p-3 bg-white/5 rounded-lg text-white/80 text-xs space-y-2">
                      <p>• Начните диалог с ботом <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer" className="text-best-primary hover:underline">@userinfobot</a> - он покажет ваш ID</p>
                      <p>• Или начните диалог с <a href="https://t.me/BESTPRSystemBot" target="_blank" rel="noopener noreferrer" className="text-best-primary hover:underline">@BESTPRSystemBot</a></p>
                    </div>
                  </details>
                </div>

                <button
                  onClick={() => {
                    if (!telegramInput.trim()) {
                      alert('Введите Telegram ID или username')
                      return
                    }
                    
                    // Определяем, что введено: ID (только цифры) или username (начинается с @ или без)
                    const input = telegramInput.trim()
                    const isNumeric = /^\d+$/.test(input)
                    
                    if (isNumeric) {
                      codeRequestMutation.mutate({
                        telegram_id: parseInt(input),
                        telegram_username: undefined,
                      })
                    } else {
                      codeRequestMutation.mutate({
                        telegram_id: undefined,
                        telegram_username: input.replace('@', ''),
                      })
                    }
                  }}
                  disabled={codeRequestMutation.isPending || !telegramInput.trim()}
                  className="w-full bg-best-primary text-white py-3 px-6 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {codeRequestMutation.isPending ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      <span>Отправка кода...</span>
                    </>
                  ) : (
                    <>
                      <Key className="h-5 w-5" />
                      <span>Получить код в боте</span>
                    </>
                  )}
                </button>

                {codeRequestMutation.error && (
                  <div className={`p-4 bg-red-500/20 border border-red-500/50 rounded-lg`}>
                    <div className="flex items-center space-x-2">
                      <AlertCircle className="h-5 w-5 text-red-400" />
                      <p className="text-white text-sm">
                        {(codeRequestMutation.error as any)?.response?.data?.detail || 
                         'Ошибка при запросе кода. Проверьте Telegram ID или username.'}
                      </p>
                    </div>
                  </div>
                )}

                {codeRequestMutation.isSuccess && (
                  <div className={`p-4 bg-green-500/20 border border-green-500/50 rounded-lg`}>
                    <div className="flex items-center space-x-2">
                      <CheckCircle2 className="h-5 w-5 text-green-400" />
                      <p className="text-white text-sm">
                        Код отправлен в Telegram бот! Проверьте сообщения от @BESTPRSystemBot
                      </p>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <>
                <div>
                  <label className={`block text-white text-sm font-medium mb-2 text-readable ${theme}`}>
                    Код из Telegram бота
                  </label>
                  <input
                    type="text"
                    placeholder="Введите 6-значный код"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary text-center text-2xl tracking-widest"
                    maxLength={6}
                  />
                  <p className="text-white/60 text-xs mt-2 text-center">
                    Код действителен в течение 10 минут
                  </p>
                </div>

                <button
                  onClick={() => {
                    if (verificationCode.length !== 6) {
                      alert('Введите 6-значный код')
                      return
                    }
                    
                    codeRegistrationMutation.mutate({
                      code: verificationCode,
                      personal_data_consent: {
                        consent: consentAccepted,
                        date: new Date().toISOString(),
                      },
                      user_agreement: {
                        accepted: agreementAccepted,
                        version: agreementData?.version || '1.0',
                      },
                    })
                  }}
                  disabled={codeRegistrationMutation.isPending || verificationCode.length !== 6 || !agreementAccepted || !consentAccepted}
                  className="w-full bg-best-primary text-white py-3 px-6 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {codeRegistrationMutation.isPending ? (
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

                <button
                  onClick={() => {
                    setCodeRequested(false)
                    setVerificationCode('')
                    setTelegramInput('')
                  }}
                  className="w-full text-white/70 hover:text-white text-sm underline"
                >
                  Запросить новый код
                </button>

                {codeRegistrationMutation.error && (
                  <div className={`p-4 bg-red-500/20 border border-red-500/50 rounded-lg`}>
                    <div className="flex items-start space-x-2">
                      <AlertCircle className="h-5 w-5 text-red-400 mt-0.5" />
                      <div className="flex-1">
                        <p className="text-white text-sm font-medium mb-1">
                          Ошибка при регистрации
                        </p>
                        <p className="text-white/80 text-sm">
                          {(codeRegistrationMutation.error as any)?.response?.data?.detail || 
                           'Неверный или истёкший код. Запросите новый код.'}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {codeRegistrationMutation.isSuccess && (
                  <div className={`p-4 bg-green-500/20 border border-green-500/50 rounded-lg`}>
                    <div className="flex items-center space-x-2">
                      <CheckCircle2 className="h-5 w-5 text-green-400" />
                      <p className="text-white text-sm">
                        Регистрация успешна! Ваша заявка отправлена на модерацию.
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Предупреждение если не в Telegram и режим через код */}
        {!window.Telegram?.WebApp && registrationMode === 'code' && (
          <div className={`p-4 bg-blue-500/20 border border-blue-500/50 rounded-lg`}>
            <div className="flex items-start space-x-2">
              <AlertCircle className="h-5 w-5 text-blue-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-white text-sm font-medium mb-2">
                  Регистрация через код подтверждения
                </p>
                <p className="text-white/80 text-sm">
                  Введите ваш Telegram ID или username, и мы отправим код подтверждения в бот @BESTPRSystemBot
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Кнопка регистрации через Telegram WebApp */}
        {registrationMode === 'telegram' && (
          <>
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
              Нажмите кнопку выше для завершения регистрации через Telegram WebApp
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
