import { useEffect, useRef, useState, RefObject } from 'react'

/**
 * Хук для создания эффекта параллакса при наведении (как на hyper3d.ai)
 * Элемент слегка двигается против движения курсора, создавая эффект 3D
 */
export function useParallaxHover(intensity: number = 15) {
  const ref = useRef<HTMLDivElement>(null)
  const [transform, setTransform] = useState('')

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const handleMouseMove = (e: MouseEvent) => {
      const rect = element.getBoundingClientRect()
      const x = e.clientX - rect.left - rect.width / 2
      const y = e.clientY - rect.top - rect.height / 2

      // Параллакс: двигаем против движения курсора
      const rotateX = (y / rect.height) * intensity
      const rotateY = -(x / rect.width) * intensity
      const translateZ = Math.abs(x / rect.width) * 5 + Math.abs(y / rect.height) * 5

      setTransform(
        `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(${translateZ}px)`
      )
    }

    const handleMouseLeave = () => {
      setTransform('perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)')
    }

    element.addEventListener('mousemove', handleMouseMove, { passive: true })
    element.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      element.removeEventListener('mousemove', handleMouseMove)
      element.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [intensity])

  return { ref: ref as RefObject<HTMLDivElement>, transform }
}
