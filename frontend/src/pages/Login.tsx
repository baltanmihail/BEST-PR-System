import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { QrCode, Loader2, CheckCircle2, AlertCircle, Smartphone, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { qrAuthApi, QRStatusResponse } from '../services/qrAuth'

export default function Login() {
  const { theme } = useThemeStore()
  const { login, user } = useAuthStore()
  const navigate = useNavigate()
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)
  const pollingRef = useRef(false)

  // Проверяем, не авторизован ли уже пользователь
  useEffect(() => {
    if (user && user.is_active) {
      navigate('/')
    }
  }, [user, navigate])

  // Генерация QR-кода
  const { data: qrData, isLoading: qrLoading, refetch: refetchQR } = useQuery({
    queryKey: ['qr-generate'],
    queryFn: () => qrAuthApi.generate(),
    enabled: !sessionToken,
    onSuccess: (data) => {
      setSessionToken(data.session_token)
    },
  })

  // Polling статуса QR-кода
  const { data: statusData, refetch: refetchStatus } = useQuery({
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
    onSuccess: (data) => {
      if (data.status === 'confirmed' && data.access_token && data.user) {
        // Сохраняем токен
        localStorage.setItem('access_token', data.access_token)
        // Обновляем состояние авторизации
        login(data.access_token)
        // Редирект на главную
        navigate('/')
      }
    },
  })

  // Очистка polling при размонтировании
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

  const handleRefreshQR = () => {
    setSessionToken(null)
    refetchQR()
  }

  const isExpired = statusData?.status === 'expired'
  const isConfirmed = statusData?.status === 'confirmed'
  const isPending = statusData?.status === 'pending' || !statusData

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
            <li>Откройте Telegram бота @BESTPRSystemBot</li>
            <li>Нажмите /scan или отправьте QR-код боту</li>
            <li>Подтвердите вход в боте</li>
            <li>Вы автоматически войдёте на сайт</li>
          </ol>
        </div>

        {/* Кнопки */}
        <div className="flex gap-3">
          <button
            onClick={handleRefreshQR}
            disabled={qrLoading}
            className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
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
          <Link
            to="/register"
            className={`flex-1 py-2 px-4 rounded-lg font-medium text-center transition-colors ${
              theme === 'dark'
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-blue-500 text-white hover:bg-blue-600'
            }`}
          >
            Регистрация
          </Link>
        </div>

        {/* Альтернативный способ */}
        <div className="mt-6 text-center">
          <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>
            Нет Telegram бота?{' '}
            <Link to="/register" className="text-blue-500 hover:underline">
              Зарегистрируйтесь
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
