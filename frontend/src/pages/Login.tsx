import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, AlertCircle, X, QrCode, Send, ChevronDown, ChevronUp } from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { qrAuthApi, QRStatusResponse, QRGenerateResponse } from '../services/qrAuth'
import { authApi } from '../services/auth'
import { registrationApi } from '../services/registration'

type LoginTab = 'qr' | 'code'

export default function Login() {
  const { theme } = useThemeStore()
  const { login, user } = useAuthStore()
  const navigate = useNavigate()
  const [tab, setTab] = useState<LoginTab>('code')
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [showAgreement, setShowAgreement] = useState(false)
  const [agreementContent, setAgreementContent] = useState<string>('')
  const [loginCode, setLoginCode] = useState('')
  const [codeError, setCodeError] = useState('')
  const [showCodeInput, setShowCodeInput] = useState(false)
  const [tgLinkClicked, setTgLinkClicked] = useState(false)

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

  // Авто-вход: Telegram WebApp или ?from=bot&telegram_id=...
  useEffect(() => {
    if (user) return

    let tgId: number | null = null

    // WebApp initData
    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user
    if (tgUser?.id) tgId = tgUser.id

    // URL param from bot (fallback on mobile in-app browser)
    if (!tgId) {
      const params = new URLSearchParams(window.location.search)
      const idParam = params.get('telegram_id')
      if (params.get('from') === 'bot' && idParam) {
        tgId = Number(idParam)
      }
    }

    if (tgId) {
      import('../services/auth').then(({ authApi }) => {
        authApi.botLogin(tgId!)
          .then((response) => {
            login(response.access_token)
            navigate('/')
          })
          .catch(() => {
            console.log('Auto-login failed, showing QR')
          })
      })
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
        let urlParams = ''
        if (fromBot && telegramId) {
          const params = new URLSearchParams({
            from: 'bot',
            telegram_id: telegramId,
          })
          if (username) params.append('username', username)
          if (firstName) params.append('first_name', firstName)
          urlParams = '?' + params.toString()
        }
        
        const data = await qrAuthApi.generate(urlParams)
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
      // Polling каждые 2 секунды для быстрой реакции на изменения
      return 2000
    },
    // Повторные попытки при ошибках
    retry: 2,
    retryDelay: 1000,
  })

  // Вычисляем статусы после получения данных
  const isExpired = statusData?.status === 'expired'
  const isConfirmed = statusData?.status === 'confirmed'
  const isPending = (statusData?.status === 'pending' || !statusData) && !isExpired && !isConfirmed

  // Автообновление QR-кода каждые 60 секунд или при истечении
  useEffect(() => {
    if (!sessionToken || isConfirmed) return
    
    // Если QR-код истёк, сразу обновляем
    if (isExpired) {
      console.log('QR code expired, auto-refreshing...')
      // Небольшая задержка для показа сообщения об истечении
      const timeoutId = setTimeout(() => {
        setSessionToken(null)
        refetchQR()
      }, 2000) // 2 секунды задержки
      return () => clearTimeout(timeoutId)
    }
    
    // Обновляем QR-код каждые 60 секунд для предотвращения истечения
    const intervalId = setInterval(() => {
      if (statusData?.status === 'pending') {
        console.log('Auto-refreshing QR code (60s interval to prevent expiration)...')
        setSessionToken(null)
        refetchQR()
      }
    }, 60000) // 60 секунд (QR-код действителен 5 минут, обновляем каждую минуту)

    return () => clearInterval(intervalId)
  }, [sessionToken, isConfirmed, isExpired, statusData?.status, refetchQR])

  // Обработка подтверждения
  useEffect(() => {
    if (statusData?.status === 'confirmed') {
      // Если есть access_token и user - это вход зарегистрированного пользователя
      if (statusData.access_token && statusData.user) {
        // Сохраняем токен
        localStorage.setItem('access_token', statusData.access_token)
        // Обновляем состояние авторизации
        login(statusData.access_token)
        
        // Редирект на главную
        navigate('/')
      } else {
        // Если нет access_token и user - это незарегистрированный пользователь
        // Редиректим на страницу регистрации с qr_token
        const qrToken = sessionToken
        if (qrToken) {
          navigate(`/register?from=bot&telegram_id=${telegramId || ''}&qr_token=${qrToken}`)
        } else {
          navigate('/register?from=bot')
        }
      }
    }
  }, [statusData, login, navigate, sessionToken, telegramId])

  const handleRefreshQR = () => {
    setSessionToken(null)
    refetchQR()
  }

  const codeLoginMutation = useMutation({
    mutationFn: (code: string) => authApi.codeLogin(code),
    onSuccess: (data) => {
      login(data.access_token)
      navigate('/')
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || 'Неверный код или код истёк'
      setCodeError(typeof msg === 'string' ? msg : 'Ошибка входа')
    },
  })

  const handleCodeSubmit = () => {
    const trimmed = loginCode.trim()
    if (trimmed.length < 4) return
    setCodeError('')
    codeLoginMutation.mutate(trimmed)
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <div className={`max-w-md w-full glass-enhanced ${theme} rounded-xl shadow-2xl p-6 md:p-8 border border-white/20 backdrop-blur-xl`}>
        <div className="flex items-center justify-between mb-5">
          <h1 className={`text-2xl font-bold text-white text-readable ${theme}`}>
            Вход в систему
          </h1>
          <button onClick={() => navigate('/')} className="p-2 rounded-lg hover:bg-white/10 transition-colors">
            <X className="w-5 h-5 text-white" />
          </button>
        </div>

        {/* Вкладки: Telegram / QR */}
        <div className="flex bg-white/10 rounded-lg p-1 mb-6">
          <button
            onClick={() => setTab('code')}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-medium transition-all ${
              tab === 'code' ? 'bg-best-primary text-white' : 'text-white/60 hover:text-white'
            }`}
          >
            <Send className="w-4 h-4" />
            Telegram
          </button>
          <button
            onClick={() => setTab('qr')}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-medium transition-all ${
              tab === 'qr' ? 'bg-best-primary text-white' : 'text-white/60 hover:text-white'
            }`}
          >
            <QrCode className="w-4 h-4" />
            QR-код
          </button>
        </div>

        {/* === Вкладка: Telegram (авто + код) === */}
        {tab === 'code' && (
          <div className="space-y-5">
            {/* Основной способ: кнопка автовхода через Telegram */}
            {!isConfirmed ? (
              <>
                <p className="text-white/60 text-sm text-center">
                  Нажмите кнопку — откроется Telegram-бот, и вы автоматически войдёте на сайт
                </p>

                <a
                  href={sessionToken
                    ? `https://t.me/BESTPRSystemBot?start=qr_${sessionToken}`
                    : 'https://t.me/BESTPRSystemBot?start=code'}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => setTgLinkClicked(true)}
                  className="w-full flex items-center justify-center gap-3 bg-[#2AABEE] hover:bg-[#229ED9] text-white py-3.5 rounded-xl font-medium transition-all text-base shadow-lg shadow-[#2AABEE]/20"
                >
                  <Send className="w-5 h-5" />
                  Войти через Telegram
                </a>

                {/* Индикатор ожидания после клика */}
                {tgLinkClicked && isPending && (
                  <div className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                    <p className="text-blue-300 text-sm">Ожидаю подтверждение из Telegram...</p>
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center gap-3 py-6">
                <CheckCircle2 className="w-12 h-12 text-green-400" />
                <p className="text-green-400 font-medium">Вход подтверждён! Перенаправление...</p>
              </div>
            )}

            {/* Разделитель */}
            {!isConfirmed && (
              <>
                <div className="relative flex items-center">
                  <div className="flex-1 border-t border-white/10" />
                  <span className="px-3 text-white/30 text-xs">или</span>
                  <div className="flex-1 border-t border-white/10" />
                </div>

                {/* Сворачиваемый блок: ввод кода вручную */}
                <button
                  onClick={() => setShowCodeInput(!showCodeInput)}
                  className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white/60 text-sm hover:bg-white/10 transition-colors"
                >
                  <span>Ввести код вручную</span>
                  {showCodeInput ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {showCodeInput && (
                  <div className="space-y-4 animate-in fade-in duration-200">
                    <div className="rounded-lg p-3 bg-white/5 border border-white/10">
                      <ol className="list-decimal list-inside space-y-1 text-xs text-white/50">
                        <li>Откройте бота <a href="https://t.me/BESTPRSystemBot?start=code" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">@BESTPRSystemBot</a></li>
                        <li>Отправьте <code className="bg-white/10 px-1 py-0.5 rounded text-white/70">/code</code></li>
                        <li>Введите код ниже</li>
                      </ol>
                    </div>

                    <input
                      type="text"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      value={loginCode}
                      onChange={e => { setLoginCode(e.target.value.replace(/\D/g, '')); setCodeError('') }}
                      onKeyDown={e => { if (e.key === 'Enter') handleCodeSubmit() }}
                      placeholder="000000"
                      className="w-full bg-white/10 text-white text-center text-3xl tracking-[0.5em] rounded-xl px-4 py-4 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary placeholder-white/20 font-mono"
                    />
                    {codeError && (
                      <p className="text-red-400 text-sm flex items-center gap-1">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" /> {codeError}
                      </p>
                    )}

                    <button
                      onClick={handleCodeSubmit}
                      disabled={loginCode.length < 6 || codeLoginMutation.isPending}
                      className="w-full bg-best-primary text-white py-3 rounded-xl font-medium hover:bg-best-primary/80 transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                    >
                      {codeLoginMutation.isPending ? (
                        <><Loader2 className="w-5 h-5 animate-spin" /> Проверяю...</>
                      ) : (
                        'Войти по коду'
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* === Вкладка: QR-код === */}
        {tab === 'qr' && (
          <div className="space-y-5">
            <div className="flex flex-col items-center">
              {qrLoading ? (
                <div className="w-56 h-56 flex items-center justify-center border-2 border-dashed rounded-lg border-white/20">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
              ) : qrData?.qr_code ? (
                <div className="relative">
                  <img src={qrData.qr_code} alt="QR Code" className="w-56 h-56 border-2 border-white/20 rounded-lg" />
                  {isExpired && (
                    <div className="absolute inset-0 bg-black/60 rounded-lg flex items-center justify-center">
                      <div className="text-center text-white">
                        <AlertCircle className="w-10 h-10 mx-auto mb-1" />
                        <p className="text-sm font-semibold">QR-код истёк</p>
                      </div>
                    </div>
                  )}
                  {isConfirmed && (
                    <div className="absolute inset-0 bg-green-500/60 rounded-lg flex items-center justify-center">
                      <div className="text-center text-white">
                        <CheckCircle2 className="w-10 h-10 mx-auto mb-1" />
                        <p className="text-sm font-semibold">Вход подтверждён!</p>
                      </div>
                    </div>
                  )}
                </div>
              ) : qrError ? (
                <div className="w-56 h-56 flex flex-col items-center justify-center border-2 border-dashed border-red-500/50 rounded-lg p-4">
                  <AlertCircle className="w-8 h-8 text-red-500 mb-2" />
                  <p className="text-sm text-center text-red-400">Ошибка QR</p>
                  <button onClick={handleRefreshQR} className="mt-2 text-xs px-3 py-1 rounded bg-white/10 text-white hover:bg-white/20">Обновить</button>
                </div>
              ) : (
                <div className="w-56 h-56 flex items-center justify-center border-2 border-dashed rounded-lg border-white/20">
                  <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                </div>
              )}
            </div>

            <div className="text-center text-sm">
              {isPending && !qrLoading && (
                <p className="text-white/60 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-blue-400" /> Ожидание...
                </p>
              )}
              {isConfirmed && <p className="text-green-400">Перенаправление...</p>}
            </div>

            <div className="rounded-lg p-4 bg-white/5 border border-white/10">
              <ol className="list-decimal list-inside space-y-1 text-sm text-white/70">
                <li>Отсканируйте QR камерой</li>
                <li>Подтвердите в Telegram боте</li>
                <li>Вы войдёте автоматически</li>
              </ol>
            </div>

            {isExpired && (
              <button onClick={handleRefreshQR} disabled={qrLoading}
                className="w-full py-2.5 rounded-lg font-medium bg-white/10 text-white hover:bg-white/20 disabled:opacity-50 border border-white/20">
                {qrLoading ? <><Loader2 className="w-4 h-4 inline mr-2 animate-spin" />Генерация...</> : 'Обновить QR-код'}
              </button>
            )}
          </div>
        )}

        {/* Соглашение */}
        <div className="mt-5 pt-4 border-t border-white/10">
          <p className="text-xs text-white/40 text-center">
            Входя в систему, вы соглашаетесь с{' '}
            <button onClick={() => setShowAgreement(true)} className="text-blue-400 hover:underline">
              пользовательским соглашением
            </button>
          </p>
        </div>
      </div>

      {/* Модальное окно для пользовательского соглашения */}
      {showAgreement && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowAgreement(false)}
        >
          <div 
            className="glass-enhanced ${theme} rounded-xl p-6 max-w-2xl max-h-[80vh] overflow-y-auto w-full shadow-xl border border-white/30"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white text-readable ${theme}">
                Пользовательское соглашение
              </h2>
              <button
                onClick={() => setShowAgreement(false)}
                className="text-white/70 hover:text-white text-2xl leading-none transition-colors"
              >
                ×
              </button>
            </div>
            <div className="text-white/80 text-sm whitespace-pre-wrap text-readable ${theme}">
              {agreementContent || 'Загрузка...'}
            </div>
            <button
              onClick={() => setShowAgreement(false)}
              className="mt-4 w-full bg-best-primary hover:bg-best-primary/80 text-white py-2 px-4 rounded-lg transition-all"
            >
              Закрыть
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
