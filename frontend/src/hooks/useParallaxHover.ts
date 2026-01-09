import { useEffect, useRef, useState, RefObject } from 'react'

/**
 * Хук для создания эффекта параллакса при наведении (как на hyper3d.ai)
 * Элемент слегка двигается против движения курсора, создавая эффект 3D
 * Оптимизирован для производительности: отключен на мобильных, использует requestAnimationFrame
 */
export function useParallaxHover(intensity: number = 15) {
  const ref = useRef<HTMLDivElement>(null)
  const [transform, setTransform] = useState('')
  const rafId = useRef<number | null>(null)
  const lastUpdateTime = useRef<number>(0)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    // Отключаем параллакс на мобильных устройствах для производительности
    const isMobile = window.innerWidth < 768 || 'ontouchstart' in window
    if (isMobile) {
      return
    }

    let pendingUpdate = false
    let lastX = 0
    let lastY = 0

    const updateTransform = () => {
      const rect = element.getBoundingClientRect()
      const x = lastX - rect.left - rect.width / 2
      const y = lastY - rect.top - rect.height / 2

      // Параллакс: двигаем против движения курсора
      const rotateX = (y / rect.height) * intensity
      const rotateY = -(x / rect.width) * intensity
      const translateZ = Math.abs(x / rect.width) * 5 + Math.abs(y / rect.height) * 5

      setTransform(
        `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(${translateZ}px)`
      )
      
      pendingUpdate = false
      rafId.current = null
    }

    const handleMouseMove = (e: MouseEvent) => {
      lastX = e.clientX
      lastY = e.clientY

      // Используем requestAnimationFrame для оптимизации обновлений
      if (!pendingUpdate) {
        pendingUpdate = true
        rafId.current = requestAnimationFrame(updateTransform)
      }
    }

    const handleMouseLeave = () => {
      // Отменяем pending обновление
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current)
        rafId.current = null
      }
      pendingUpdate = false
      setTransform('perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)')
    }

    element.addEventListener('mousemove', handleMouseMove, { passive: true })
    element.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      element.removeEventListener('mousemove', handleMouseMove)
      element.removeEventListener('mouseleave', handleMouseLeave)
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current)
      }
    }
  }, [intensity])

  return { ref: ref as RefObject<HTMLDivElement>, transform }
}
