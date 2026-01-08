import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, AlertCircle, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { qrAuthApi, QRStatusResponse, QRGenerateResponse } from '../services/qrAuth'
import { registrationApi } from '../services/registration'

export default function Login() {
  const { theme } = useThemeStore()
  const { login, user } = useAuthStore()
  const navigate = useNavigate()
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [showAgreement, setShowAgreement] = useState(false)
  const [agreementContent, setAgreementContent] = useState<string>('')

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

  // Проверяем, не авторизован ли уже пользователь
  useEffect(() => {
    if (user && user.is_active) {
      navigate('/')
    }
  }, [user, navigate])

  // Проверяем, открыт ли сайт через Telegram WebApp (для зарегистрированных пользователей)
  useEffect(() => {
    const isTelegramWebApp = window.Telegram?.WebApp
    
    // Если открыт через Telegram WebApp и пользователь не авторизован
    if (isTelegramWebApp && !user && window.Telegram) {
      const tg = window.Telegram.WebApp
      const initDataUnsafe = tg.initDataUnsafe
      
      // Если есть данные пользователя из Telegram WebApp
      if (initDataUnsafe?.user?.id) {
        const telegramId = initDataUnsafe.user.id
        
        // Пытаемся автоматически войти через бота (для зарегистрированных пользователей)
        import('../services/auth').then(({ authApi }) => {
          authApi.botLogin(telegramId)
            .then((response) => {
              // Успешный вход - автоматически авторизуем
              login(response.access_token)
              navigate('/')
            })
            .catch((error) => {
              // Пользователь не зарегистрирован или неактивен
              // Показываем QR-код для входа/регистрации
              console.log('Bot login failed, showing QR code:', error)
            })
        })
      }
    }
  }, [user, login, navigate])

  // Проверяем параметры из URL (если пользователь перешёл через бота)
  const urlParams = new URLSearchParams(window.location.search)
  const fromBot = urlParams.get('from') === 'bot'
  const telegramId = urlParams.get('telegram_id')
  const username = urlParams.get('username')
  const firstName = urlParams.get('first_name')

  // Генерация QR-кода с параметрами, если пользователь перешёл через бота
  const { data: qrData, isLoading: qrLoading, error: qrError, refetch: refetchQR } = useQuery<QRGenerateResponse>({
    queryKey: ['qr-generate', fromBot, telegramId],
    queryFn: async () => {
      try {
        // Если пользователь перешёл через бота, передаём параметры в URL
        let generateUrl = '/auth/qr/generate'
        if (fromBot && telegramId) {
          const params = new URLSearchParams({
            from: 'bot',
            telegram_id: telegramId,
          })
          if (username) params.append('username', username)
          if (firstName) params.append('first_name', firstName)
          generateUrl += '?' + params.toString()
        }
        
        const data = await qrAuthApi.generate(generateUrl)
        console.log('QR data received:', data)
        return data
      } catch (error) {
        console.error('QR generation failed:', error)
        throw error
      }
    },
    enabled: !sessionToken,
    retry: 2,
    retryDelay: 1000,
  })

  // Устанавливаем токен когда QR-код сгенерирован
  useEffect(() => {
    if (qrData?.session_token) {
      setSessionToken(qrData.session_token)
    }
  }, [qrData])

  // Polling статуса QR-кода
  const { data: statusData } = useQuery<QRStatusResponse>({
    queryKey: ['qr-status', sessionToken],
    queryFn: () => {
      if (!sessionToken) throw new Error('No session token')
      return qrAuthApi.getStatus(sessionToken)
    },
    enabled: !!sessionToken,
    refetchInterval: (query) => {
      const data = query.state.data as QRStatusResponse | undefined
      // Останавливаем polling если сессия подтверждена или истекла
      if (data?.status === 'confirmed' || data?.status === 'expired' || data?.status === 'cancelled') {
        return false
      }
      // Polling каждые 2 секунды
      return 2000
    },
  })

  // Обработка подтверждения
  useEffect(() => {
    if (statusData?.status === 'confirmed' && statusData.access_token && statusData.user) {
      // Сохраняем токен
      localStorage.setItem('access_token', statusData.access_token)
      // Обновляем состояние авторизации
      login(statusData.access_token)
      // Редирект на главную
      navigate('/')
    }
  }, [statusData, login, navigate])

  const handleRefreshQR = () => {
    setSessionToken(null)
    refetchQR()
  }

  const isExpired = statusData?.status === 'expired'
  const isConfirmed = statusData?.status === 'confirmed'
  const isPending = (statusData?.status === 'pending' || !statusData) && !isExpired && !isConfirmed

  return (
    <div className={`min-h-screen flex items-center justify-center p-4 ${theme === 'dark' ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <div className={`max-w-md w-full ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-8`}>
        <div className="flex items-center justify-between mb-6">
          <h1 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
            Вход в систему
          </h1>
          <Link
            to="/"
            className={`p-2 rounded-lg hover:bg-opacity-10 ${theme === 'dark' ? 'hover:bg-white' : 'hover:bg-gray-900'}`}
          >
            <ArrowLeft className={`w-5 h-5 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`} />
          </Link>
        </div>

        <div className="text-center mb-6">
          <p className={`${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'} mb-4`}>
            Отсканируйте QR-код через Telegram бота для входа
          </p>
        </div>

        {/* QR-код */}
        <div className="flex flex-col items-center mb-6">
          {qrLoading ? (
            <div className="w-64 h-64 flex items-center justify-center border-2 border-dashed rounded-lg">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : qrData?.qr_code ? (
            <div className="relative">
              <img
                src={qrData.qr_code}
                alt="QR Code"
                className="w-64 h-64 border-2 rounded-lg"
              />
              {isExpired && (
                <div className="absolute inset-0 bg-black bg-opacity-50 rounded-lg flex items-center justify-center">
                  <div className="text-center text-white">
                    <AlertCircle className="w-12 h-12 mx-auto mb-2" />
                    <p className="font-semibold">QR-код истёк</p>
                  </div>
                </div>
              )}
              {isConfirmed && (
                <div className="absolute inset-0 bg-green-500 bg-opacity-50 rounded-lg flex items-center justify-center">
                  <div className="text-center text-white">
                    <CheckCircle2 className="w-12 h-12 mx-auto mb-2" />
                    <p className="font-semibold">Вход подтверждён!</p>
                  </div>
                </div>
              )}
            </div>
          ) : qrError ? (
            <div className="w-64 h-64 flex flex-col items-center justify-center border-2 border-dashed border-red-500/50 rounded-lg p-4">
              <AlertCircle className="w-8 h-8 text-red-500 mb-2" />
              <p className={`text-sm text-center ${theme === 'dark' ? 'text-red-400' : 'text-red-600'}`}>
                Ошибка генерации QR-кода
              </p>
              <p className={`text-xs text-center mt-1 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
                {qrError instanceof Error ? qrError.message : 'Попробуйте обновить страницу'}
              </p>
              <button
                onClick={handleRefreshQR}
                className={`mt-2 text-xs px-3 py-1 rounded ${theme === 'dark' ? 'bg-gray-700 text-white' : 'bg-gray-200 text-gray-900'}`}
              >
                Обновить
              </button>
            </div>
          ) : (
            <div className="w-64 h-64 flex items-center justify-center border-2 border-dashed rounded-lg">
              <AlertCircle className="w-8 h-8 text-gray-400" />
            </div>
          )}
        </div>

        {/* Статус */}
        <div className="text-center mb-6">
          {isPending && !qrLoading && (
            <div className="flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
              <p className={`${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>
                Ожидание подтверждения...
              </p>
            </div>
          )}
          {isExpired && (
            <div className="flex items-center justify-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <p className="text-red-500">QR-код истёк. Обновите страницу.</p>
            </div>
          )}
          {isConfirmed && (
            <div className="flex items-center justify-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <p className="text-green-500">Вход подтверждён! Перенаправление...</p>
            </div>
          )}
        </div>

        {/* Инструкции */}
        <div className={`rounded-lg p-4 mb-6 ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
          <h3 className={`font-semibold mb-2 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
            Как войти:
          </h3>
          <ol className={`list-decimal list-inside space-y-1 text-sm ${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>
            <li>
              Откройте Telegram бота{' '}
              <a
                href="https://t.me/BESTPRSystemBot"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline font-medium"
              >
                @BESTPRSystemBot
              </a>
            </li>
            <li>Нажмите /scan или отправьте QR-код боту</li>
            <li>Подтвердите вход в боте</li>
            <li>Вы автоматически войдёте на сайт</li>
          </ol>
        </div>

        {/* Пользовательское соглашение и обработка данных */}
        <div className={`rounded-lg p-4 mb-6 ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
          <p className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
            Входя в систему, вы соглашаетесь с{' '}
            <button
              onClick={() => setShowAgreement(true)}
              className="text-blue-500 hover:underline font-medium"
            >
              пользовательским соглашением
            </button>
            {' '}и{' '}
            <button
              onClick={() => {
                const consentWindow = window.open('', '_blank', 'width=800,height=600')
                if (consentWindow) {
                  consentWindow.document.write(`
                    <html>
                      <head>
                        <title>Согласие на обработку персональных данных</title>
                        <style>
                          body { font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; max-width: 800px; margin: 0 auto; }
                          h1 { color: #333; }
                          p { margin-bottom: 1em; }
                        </style>
                      </head>
                      <body>
                        <h1>Согласие на обработку персональных данных</h1>
                        <p>Настоящим я даю согласие на обработку моих персональных данных (Telegram ID, имя, username) в целях использования системы управления PR-отделом BEST Москва.</p>
                        <p>Обработка персональных данных осуществляется в соответствии с Федеральным законом № 152-ФЗ "О персональных данных".</p>
                        <p>Я понимаю, что могу отозвать согласие в любое время, обратившись к администратору системы.</p>
                      </body>
                    </html>
                  `)
                }
              }}
              className="text-blue-500 hover:underline font-medium"
            >
              обработкой персональных данных
            </button>
          </p>
        </div>

        {/* Кнопка обновления */}
        <div className="flex justify-center">
          <button
            onClick={handleRefreshQR}
            disabled={qrLoading}
            className={`w-full py-2 px-4 rounded-lg font-medium transition-colors ${
              theme === 'dark'
                ? 'bg-gray-700 text-white hover:bg-gray-600 disabled:opacity-50'
                : 'bg-gray-200 text-gray-900 hover:bg-gray-300 disabled:opacity-50'
            }`}
          >
            {qrLoading ? (
              <>
                <Loader2 className="w-4 h-4 inline mr-2 animate-spin" />
                Генерация...
              </>
            ) : (
              'Обновить QR-код'
            )}
          </button>
        </div>
      </div>

      {/* Модальное окно для пользовательского соглашения */}
      {showAgreement && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowAgreement(false)}
        >
          <div 
            className={`${theme === 'dark' ? 'bg-gray-800' : 'bg-white'} rounded-xl p-6 max-w-2xl max-h-[80vh] overflow-y-auto w-full shadow-xl`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Пользовательское соглашение
              </h2>
              <button
                onClick={() => setShowAgreement(false)}
                className={`${theme === 'dark' ? 'text-white/70 hover:text-white' : 'text-gray-600 hover:text-gray-900'} text-2xl leading-none`}
              >
                ×
              </button>
            </div>
            <div className={`${theme === 'dark' ? 'text-white/80' : 'text-gray-700'} text-sm whitespace-pre-wrap`}>
              {agreementContent || 'Загрузка...'}
            </div>
            <button
              onClick={() => setShowAgreement(false)}
              className={`mt-4 w-full ${theme === 'dark' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-500 hover:bg-blue-600'} text-white py-2 px-4 rounded-lg transition-all`}
            >
              Закрыть
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
