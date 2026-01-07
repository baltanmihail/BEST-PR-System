import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import * as THREE from 'three'

/**
 * Статичная 3D модель курсора, которая "тыкает" на панель
 * Использует GLB модель из public/3d_mouse_cursor.glb
 * Показывается только на главной странице и на десктопах
 */
export default function StaticCursor3D() {
  const location = useLocation()
  const [isVisible, setIsVisible] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const modelRef = useRef<THREE.Object3D | null>(null) // Object3D поддерживает и Group, и Mesh
  const animationFrameRef = useRef<number>()

  // Позиция контейнера — привязываем к панели "Топ" на Home
  const [anchorPos, setAnchorPos] = useState<{ left: number; top: number } | null>(null)
  const anchorSelector = useMemo(() => '[data-static-cursor-anchor="top"]', [])

  // Проверяем, нужно ли показывать курсор (только на главной странице)
  useEffect(() => {
    setIsVisible(location.pathname === '/')
  }, [location.pathname])

  // Проверяем размер экрана (скрываем на мобильных)
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768) // Мобильные устройства
    }
    
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Обновляем позицию привязки (scroll/resize), чтобы курсор не "улетал"
  useEffect(() => {
    if (!isVisible || isMobile) return

    const update = () => {
      const el = document.querySelector(anchorSelector) as HTMLElement | null
      if (!el) {
        setAnchorPos(null)
        return
      }
      const r = el.getBoundingClientRect()
      // Позиционируем курсор относительно ЦЕНТРА панели "Топ"
      // Курсор должен быть выше и правее центра панели
      const buttonCenterX = r.left + r.width / 2
      const buttonCenterY = r.top + r.height / 2
      
      // Смещение от центра панели (чуть ниже и правее)
      const offsetX = r.width * 0.05 // Вправо от центра
      const offsetY = r.height * -0.25 // Чуть ниже центра
      
      const left = Math.min(window.innerWidth - 200, Math.max(10, buttonCenterX + offsetX))
      const top = Math.min(window.innerHeight - 200, Math.max(10, buttonCenterY + offsetY))
      setAnchorPos({ left, top })
    }

    update()
    window.addEventListener('resize', update, { passive: true })
    window.addEventListener('scroll', update, { passive: true })
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update)
    }
  }, [anchorSelector, isMobile, isVisible])

  useEffect(() => {
    const container = containerRef.current
    // Не инициализируем, если не на главной странице или на мобильном
    if (!container || !isVisible || isMobile) return

    // Создаём мини-сцену для курсора
    const scene = new THREE.Scene()
    sceneRef.current = scene

    // Камера
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000)
    camera.position.set(0, 0, 5)
    cameraRef.current = camera

    // Рендерер (маленький размер, но большой контейнер для границ)
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      preserveDrawingBuffer: false,
    })
    // Адаптивный размер рендерера
    const getRendererSize = () => {
      const width = window.innerWidth
      if (width >= 1920) return 200
      if (width >= 1440) return 180
      if (width >= 1024) return 150
      return 120
    }
    const rendererSize = getRendererSize()
    renderer.setSize(rendererSize, rendererSize)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Освещение - яркое и сбалансированное со всех сторон
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.0)
    scene.add(ambientLight)

    // Основной свет спереди-сверху (белый)
    const directionalLight1 = new THREE.DirectionalLight(0xffffff, 1.2)
    directionalLight1.position.set(3, 5, 5)
    scene.add(directionalLight1)

    // Дополнительный свет слева (белый)
    const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.7)
    directionalLight2.position.set(-4, 3, 4)
    scene.add(directionalLight2)

    // Дополнительный свет справа (жёлтый)
    const directionalLight3 = new THREE.DirectionalLight(0xffb300, 0.7)
    directionalLight3.position.set(4, 3, 4)
    scene.add(directionalLight3)

    // Заполняющий свет снизу (белый)
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.6)
    fillLight.position.set(0, -3, 3)
    scene.add(fillLight)

    // Функция для создания fallback курсора (определяем ДО использования)
    const createFallbackCursor = () => {
      try {
        // Fallback: простая геометрия если модель не найдена - курсор-стрелка
        const geometry = new THREE.ConeGeometry(0.12, 0.35, 8)
        const material = new THREE.MeshStandardMaterial({
          color: 0x1e88e5, // Голубой
          metalness: 0.2,
          roughness: 0.3,
          emissive: 0x1e88e5,
          emissiveIntensity: 0.4,
        })
        const cone = new THREE.Mesh(geometry, material)
        cone.rotation.set(-0.4, 0, 0) // Наклон как у курсора
        scene.add(cone)
        modelRef.current = cone
        console.log('✅ Fallback курсор создан')
      } catch (err) {
        console.error('❌ Ошибка создания fallback курсора:', err)
      }
    }

    // Загружаем модель курсора
    import('three/examples/jsm/loaders/GLTFLoader.js')
      .then(({ GLTFLoader }) => {
        const loader = new GLTFLoader()
        loader.load(
          '/3d_mouse_cursor.glb',
          (gltf) => {
            try {
              const model = gltf.scene
              model.scale.set(0.5, 0.5, 0.5) // Ещё уменьшил размер модели
              model.rotation.set(0, 5.4, 0)
              model.position.set(0, 0, 0) // Статичная позиция, без смещения

              // Настройка материалов - сохраняем оригинальные цвета, только улучшаем свойства
              model.traverse((child) => {
                if (child instanceof THREE.Mesh) {
                  const originalMaterial = child.material
                  if (originalMaterial instanceof THREE.MeshStandardMaterial) {
                    // Сохраняем оригинальный цвет
                    const originalColor = originalMaterial.color.clone()
                    // Улучшаем свойства для лучшего отображения
                    originalMaterial.metalness = Math.max(originalMaterial.metalness || 0.4, 0.4)
                    originalMaterial.roughness = Math.min(originalMaterial.roughness || 0.4, 0.3)
                    originalMaterial.envMapIntensity = 2.0
                    // Лёгкое свечение того же цвета
                    if (!originalMaterial.emissive || originalMaterial.emissive.getHex() === 0x000000) {
                      originalMaterial.emissive = originalColor.clone().multiplyScalar(0.2)
                      originalMaterial.emissiveIntensity = 0.2
                    }
                    // Убеждаемся, что цвет не перезаписан
                    originalMaterial.color = originalColor
                  } else {
                    // Если не MeshStandardMaterial, создаём новый с голубым цветом
                    child.material = new THREE.MeshStandardMaterial({
                      color: 0x1e88e5,
                      metalness: 0.4,
                      roughness: 0.3,
                      emissive: 0x1e88e5,
                      emissiveIntensity: 0.2,
                    })
                  }
                }
              })

              scene.add(model)
              modelRef.current = model
            } catch (err) {
              console.error('❌ Ошибка обработки модели курсора:', err)
              // Создаём fallback
              createFallbackCursor()
            }
          },
          (progress) => {
            // Прогресс загрузки (опционально)
            if (progress.lengthComputable) {
              console.log(`Загрузка курсора: ${(progress.loaded / progress.total * 100).toFixed(0)}%`)
            }
          },
          (error) => {
            console.warn('⚠️ Cursor model not found, using fallback:', error)
            createFallbackCursor()
          }
        )
      })
      .catch((err) => {
        console.error('Failed to load GLTFLoader:', err)
      })

    // Анимация - парение и выразительное "нажатие"
    let time = 0
    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate)
      time += 0.016 // ~60fps

      if (modelRef.current) {
        // Плавное парение вверх-вниз (лёгкое)
        const floatY = Math.sin(time * 0.6) * 0.05
        
        // Анимация "нажатия" - более выразительная с эффектом на окне
        // Используем два синуса для более сложной анимации
        const pressCycle1 = Math.sin(time * 1.5) // Быстрый цикл
        const pressCycle2 = Math.sin(time * 0.8) // Медленный цикл
        const pressIntensity = (pressCycle1 * 0.3 + pressCycle2 * 0.2) + 0.3 // От 0.1 до 0.8
        
        // Движение вперёд (к экрану) - более заметное
        const pressZ = -pressIntensity * 0.5
        
        // Наклон вперёд - более выраженный
        const pressRotX = -pressIntensity * 0.3
        
        // Лёгкое покачивание влево-вправо при нажатии
        const pressRotZ = Math.sin(time * 2.0) * pressIntensity * 0.1
        
        // Применяем анимацию
        modelRef.current.position.y = floatY
        modelRef.current.position.z = pressZ
        // Базовый rotation.y уже установлен (5.4), не меняем его
        modelRef.current.rotation.x = pressRotX
        modelRef.current.rotation.z = pressRotZ
        
        // Эффект на окне при нажатии (когда курсор максимально нажат)
        // Используем requestAnimationFrame для оптимизации
        if (pressIntensity > 0.75 && container && Math.floor(time * 10) % 10 === 0) {
          // Находим ближайшее окно (glass-enhanced элемент) к курсору
          const windows = document.querySelectorAll('.glass-enhanced') as NodeListOf<HTMLElement>
          if (windows.length > 0) {
            const containerRect = container.getBoundingClientRect()
            const cursorCenterX = containerRect.left + containerRect.width / 2
            const cursorCenterY = containerRect.top + containerRect.height / 2
            
            // Находим ближайшее окно по расстоянию
            let nearestWindow: HTMLElement | null = null
            let minDistance = Infinity
            
            const windowsArray = Array.from(windows)
            windowsArray.forEach((window: HTMLElement) => {
              const windowRect = window.getBoundingClientRect()
              const windowCenterX = windowRect.left + windowRect.width / 2
              const windowCenterY = windowRect.top + windowRect.height / 2
              
              const distance = Math.sqrt(
                Math.pow(windowCenterX - cursorCenterX, 2) + 
                Math.pow(windowCenterY - cursorCenterY, 2)
              )
              
              if (distance < minDistance) {
                minDistance = distance
                nearestWindow = window
              }
            })
            
            // Добавляем эффект только если окно достаточно близко (в пределах 300px)
            if (nearestWindow !== null && minDistance < 300) {
              const targetWindow: HTMLElement = nearestWindow
              if (!targetWindow.classList.contains('cursor-hint-press')) {
                targetWindow.classList.add('cursor-hint-press')
                const windowElement = targetWindow
                setTimeout(() => {
                  windowElement.classList.remove('cursor-hint-press')
                }, 600)
              }
            }
          }
        }
      }

      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current)
      }
    }
    animate()

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      if (rendererRef.current?.domElement.parentNode) {
        rendererRef.current.domElement.parentNode.removeChild(rendererRef.current.domElement)
      }
      rendererRef.current?.dispose()
    }
  }, [isVisible, isMobile])

  // Не рендерим, если не на главной странице или на мобильном
  if (!isVisible || isMobile) {
    return null
  }

  // Адаптивные размеры для разных экранов
  const getResponsiveSize = () => {
    const width = window.innerWidth
    if (width >= 1920) {
      // Большие экраны (Full HD+)
      return { renderer: 200, container: 200, bottom: '120px', right: '50px' }
    } else if (width >= 1440) {
      // Средние экраны (HD+)
      return { renderer: 180, container: 180, bottom: '100px', right: '40px' }
    } else if (width >= 1024) {
      // Планшеты в альбомной ориентации
      return { renderer: 150, container: 150, bottom: '80px', right: '30px' }
    } else {
      // Планшеты в портретной ориентации
      return { renderer: 120, container: 120, bottom: '60px', right: '20px' }
    }
  }

  const responsiveSize = getResponsiveSize()

  return (
    <div
      ref={containerRef}
      className="fixed pointer-events-none z-50 cursor-hint hidden md:flex"
      style={{
        left: anchorPos ? `${anchorPos.left}px` : responsiveSize.right,
        top: anchorPos ? `${anchorPos.top}px` : undefined,
        bottom: anchorPos ? undefined : responsiveSize.bottom,
        right: anchorPos ? undefined : responsiveSize.right,
        width: `${responsiveSize.container}px`,
        height: `${responsiveSize.container}px`,
        overflow: 'visible',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    />
  )
}
