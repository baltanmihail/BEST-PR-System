import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import * as THREE from 'three'

type Point = { x: number; y: number }

/**
 * Cursor2 - кастомный 3D курсор пользователя (заменяет системный на Home)
 * - Использует 3d_mouse_cursor.glb
 * - Плавное следование + лёгкий трейл
 * - Idle-анимация на окне "Быстрые действия" при наведении
 */
export default function Cursor2() {
  const location = useLocation()
  const [enabled, setEnabled] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const modelRef = useRef<THREE.Object3D | null>(null)
  
  const trailRefs = useRef<HTMLDivElement[]>([])
  const mousePos = useRef<Point>({ x: 0, y: 0 })
  const currentPos = useRef<Point>({ x: 0, y: 0 })
  const trailPositions = useRef<Point[]>([])
  const animationFrameRef = useRef<number>()
  
  const hoverActionRef = useRef<HTMLElement | null>(null)
  const hoverSinceRef = useRef<number>(0)
  const lastPressRef = useRef<number>(0)

  const trailLength = 8

  useEffect(() => {
    setEnabled(location.pathname === '/')
  }, [location.pathname])

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Скрываем системный курсор
  useEffect(() => {
    if (!enabled || isMobile) {
      document.body.style.cursor = 'auto'
      const style = document.getElementById('cursor2-hide-pointer')
      if (style) style.remove()
      return
    }

    document.body.style.cursor = 'none'
    const style = document.createElement('style')
    style.id = 'cursor2-hide-pointer'
    style.textContent = `body * { cursor: none !important; }`
    document.head.appendChild(style)

    return () => {
      document.body.style.cursor = 'auto'
      const s = document.getElementById('cursor2-hide-pointer')
      if (s) s.remove()
    }
  }, [enabled, isMobile])

  // Инициализация 3D-сцены для курсора
  useEffect(() => {
    if (!enabled || isMobile || !containerRef.current) return

    const container = containerRef.current

    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000)
    camera.position.set(0, 0, 3)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setSize(40, 40)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Яркое освещение для курсора (чтобы не был тёмным)
    const ambientLight = new THREE.AmbientLight(0xffffff, 2.0) // Увеличено с 1.0
    scene.add(ambientLight)

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.8) // Увеличено с 1.0
    directionalLight.position.set(2, 3, 3)
    scene.add(directionalLight)
    
    // Дополнительный свет для равномерности
    const fillLight = new THREE.DirectionalLight(0xffffff, 1.2)
    fillLight.position.set(-2, -1, 3)
    scene.add(fillLight)

    // Загружаем модель курсора
    import('three/examples/jsm/loaders/GLTFLoader.js')
      .then(({ GLTFLoader }) => {
        const loader = new GLTFLoader()
        loader.load(
          '/3d_mouse_cursor.glb',
          (gltf) => {
            const model = gltf.scene
            model.scale.set(0.35, 0.35, 0.35)
            model.rotation.set(0, 5.4, 0)

            model.traverse((child) => {
              if (child instanceof THREE.Mesh) {
                const mat = child.material
                if (mat instanceof THREE.MeshStandardMaterial) {
                  const originalColor = mat.color.clone()
                  mat.metalness = 0.4
                  mat.roughness = 0.3
                  mat.envMapIntensity = 2.0
                  mat.color = originalColor
                }
              }
            })

            scene.add(model)
            modelRef.current = model
          },
          undefined,
          () => {
            // Fallback
            const geometry = new THREE.ConeGeometry(0.08, 0.25, 8)
            const material = new THREE.MeshStandardMaterial({ color: 0x1e88e5, metalness: 0.3, roughness: 0.3 })
            const cone = new THREE.Mesh(geometry, material)
            cone.rotation.set(-0.3, 0, 0)
            scene.add(cone)
            modelRef.current = cone
          }
        )
      })
      .catch(() => {})

    // Рендер-луп
    const renderLoop = () => {
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current)
      }
      animationFrameRef.current = requestAnimationFrame(renderLoop)
    }
    renderLoop()

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
      if (rendererRef.current?.domElement.parentNode) {
        rendererRef.current.domElement.parentNode.removeChild(rendererRef.current.domElement)
      }
      rendererRef.current?.dispose()
    }
  }, [enabled, isMobile])

  // Отслеживание движения мыши + трейл + idle-анимация
  useEffect(() => {
    if (!enabled || isMobile) return

    trailPositions.current = Array.from({ length: trailLength }, () => ({ x: window.innerWidth / 2, y: window.innerHeight / 2 }))
    currentPos.current = { x: window.innerWidth / 2, y: window.innerHeight / 2 }
    mousePos.current = { x: window.innerWidth / 2, y: window.innerHeight / 2 }

    const handleMouseMove = (e: MouseEvent) => {
      mousePos.current = { x: e.clientX, y: e.clientY }

      // Проверяем наведение на action-элемент (окно "Быстрые действия")
      const target = e.target as HTMLElement
      const actionElement = target.closest('[data-cursor-action]')

      if (actionElement !== hoverActionRef.current) {
        hoverActionRef.current = actionElement as HTMLElement | null
        hoverSinceRef.current = actionElement ? performance.now() : 0
      }
    }

    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate)

      // Плавное следование (lerp) - точное центрирование
      const lerpFactor = 0.18
      currentPos.current.x += (mousePos.current.x - currentPos.current.x) * lerpFactor
      currentPos.current.y += (mousePos.current.y - currentPos.current.y) * lerpFactor

      // Обновляем позицию 3D-курсора (центрируем точно)
      if (containerRef.current) {
        containerRef.current.style.left = `${currentPos.current.x}px`
        containerRef.current.style.top = `${currentPos.current.y}px`
      }

      // Обновляем трейл
      trailPositions.current.unshift({ x: currentPos.current.x, y: currentPos.current.y })
      if (trailPositions.current.length > trailLength) {
        trailPositions.current.pop()
      }

      trailRefs.current.forEach((trail, index) => {
        if (trail && trailPositions.current[index]) {
          const pos = trailPositions.current[index]
          trail.style.left = `${pos.x}px`
          trail.style.top = `${pos.y}px`
        }
      })

      // Idle-анимация: если долго наводимся на action-элемент (реже, слабее)
      const actionEl = hoverActionRef.current
      if (actionEl) {
        const now = performance.now()
        const hoveredFor = now - hoverSinceRef.current
        const canPress = now - lastPressRef.current > 4000 // Реже: было 1200, теперь 4000ms
        if (hoveredFor > 2000 && canPress) { // Дольше ждать: было 800, теперь 2000ms
          lastPressRef.current = now
          // Анимируем окно "Быстрые действия", а не отдельные кнопки
          const quickActionsWindow = document.querySelector('[data-quick-actions]')
          if (quickActionsWindow instanceof HTMLElement && !quickActionsWindow.classList.contains('cursor-hint-press-light')) {
            quickActionsWindow.classList.add('cursor-hint-press-light') // Используем лёгкий эффект
            setTimeout(() => {
              quickActionsWindow.classList.remove('cursor-hint-press-light')
            }, 500)
          }
        }
      }
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    animate()

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [enabled, isMobile])

  if (!enabled || isMobile) return null

  return (
    <>
      {/* Основной 3D курсор */}
      <div
        ref={containerRef}
        className="fixed pointer-events-none z-[9999]"
        style={{
          width: '40px',
          height: '40px',
          transform: 'translate(-50%, -50%)', // Центрируем точно на позиции мыши
        }}
      />

      {/* Трейл (очень лёгкий след - почти невидимый) */}
      {[...Array(trailLength)].map((_, i) => (
        <div
          key={i}
          ref={(el) => {
            if (el) trailRefs.current[i] = el
          }}
          className="fixed pointer-events-none z-[9998]"
          style={{
            width: `${8 - i * 0.6}px`, // Меньше размер
            height: `${8 - i * 0.6}px`,
            opacity: 0.15 - i * 0.015, // Гораздо прозрачнее
            transform: 'translate(-50%, -50%)',
          }}
        >
          <div
            className="w-full h-full rounded-full bg-white/20" // Белый вместо синего
            style={{
              boxShadow: '0 0 3px rgba(255, 255, 255, 0.1)', // Очень лёгкое свечение
            }}
          />
        </div>
      ))}
    </>
  )
}

