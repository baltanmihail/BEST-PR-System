import axios from 'axios'

// Для локальной разработки используем localhost, для production - Railway
const API_BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? 'http://localhost:8000/api/v1' : 'https://best-pr-api.up.railway.app/api/v1')

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Добавляем токен к каждому запросу
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Обработка ошибок
api.interceptors.response.use(
  (response) => {
    // Логируем успешные ответы для отладки (только в development)
    if (import.meta.env.DEV) {
      console.log('API Response:', response.config.method?.toUpperCase(), response.config.url, response.status, response.data)
    }
    return response
  },
  (error) => {
    // Логируем ошибки для отладки
    console.error('API Error:', error.config?.method?.toUpperCase(), error.config?.url, error.response?.status, error.response?.data)
    
    if (error.response?.status === 401) {
      // Токен истёк или невалиден
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
