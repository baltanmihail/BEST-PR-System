import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

interface ModelConfig {
  path: string
  position: [number, number, number]
  scale: number
  rotation: [number, number, number]
  floatSpeed: number
  floatAmplitude: number
}

export default function Background3DModels() {
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const modelsRef = useRef<THREE.Group[]>([])
  const animationFrameRef = useRef<number>()
  const wheelEffectRef = useRef(0)
  const wheelDirectionRef = useRef(0) // Направление вращения: 1 = вниз, -1 = вверх
  const wheelTimeoutRef = useRef<number>()
  const modelsConfigRef = useRef<ModelConfig[]>([])
  const modelTimeOffsetsRef = useRef<number[]>([]) // Разные задержки для каждой модели
  const modelScrollSpeedsRef = useRef<number[]>([]) // Разные скорости скролла для каждой модели
  const modelScrollOffsetsRef = useRef<number[]>([]) // Накопленное смещение для каждой модели (не сбрасывается)
  const [isMobile, setIsMobile] = useState(false)

  // Конфигурация для 2 моделей (слева и справа) - с разными параметрами для разнообразия
  const getModelsConfig = (): ModelConfig[] => [
    {
      path: '/BEST.glb',
      position: [-600, 0, -500], // Слева, дальше от центра
      scale: 2000.0,
      rotation: [1, 0, 0], // Наклон К зрителю
      floatSpeed: 0.0008,
      floatAmplitude: 40,
    },
    {
      path: '/BEST.glb',
      position: [600, 0, -500], // Справа, дальше от центра
      scale: 2000.0,
      rotation: [1, Math.PI, 0], // Наклон К зрителю, развёрнут в другую сторону
      floatSpeed: 0.0012, // Разная скорость
      floatAmplitude: 50, // Разная амплитуда
    },
  ]

  // Проверка на мобильное устройство
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768 || /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent))
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    
    // На мобильных устройствах также показываем модели, но с оптимизированными настройками
    if (isMobile) {
      console.log('Мобильное устройство обнаружено - используем оптимизированную версию с летающим блейдом')
    }

    // Создаём сцену
    const scene = new THREE.Scene()
    sceneRef.current = scene

    // Камера
    const camera = new THREE.PerspectiveCamera(
      50,
      window.innerWidth / window.innerHeight,
      0.1,
      2000
    )
    camera.position.z = 500
    cameraRef.current = camera

    // Рендерер с тенями - оптимизирован для производительности
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: !isMobile, // Отключаем антиалиасинг на мобильных для производительности
      powerPreference: 'high-performance', // Предпочитаем производительность
    })
    renderer.setSize(window.innerWidth, window.innerHeight)
    // Ограничиваем pixel ratio для лучшей производительности
    renderer.setPixelRatio(isMobile ? Math.min(window.devicePixelRatio, 1.5) : Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = !isMobile // Отключаем тени на мобильных для производительности
    renderer.shadowMap.type = THREE.PCFSoftShadowMap // Мягкие тени
    container.appendChild(renderer.domElement)
    rendererRef.current = renderer

    // Освещение - ЯРКОЕ И ФРОНТАЛЬНОЕ для правильного отображения цветов
    // Главный ключ: свет должен падать СПЕРЕДИ на модели (z > 0)
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.5) // Увеличено для видимости
    scene.add(ambientLight)

    // Основной свет СПЕРЕДИ-сверху (белый) - главный источник
    const frontLight = new THREE.DirectionalLight(0xffffff, 2.0) // Яркий белый спереди
    frontLight.position.set(0, 200, 800) // Спереди-сверху (z=800)
    frontLight.castShadow = !isMobile // Тени только на десктопе
    if (!isMobile) {
      frontLight.shadow.mapSize.width = 2048
      frontLight.shadow.mapSize.height = 2048
    }
    scene.add(frontLight)

    // Голубой свет спереди-слева
    const blueLight = new THREE.DirectionalLight(0x1e88e5, 1.3)
    blueLight.position.set(-300, 300, 600) // Спереди-слева
    blueLight.castShadow = true
    scene.add(blueLight)

    // Зелёный свет спереди-слева-снизу
    const greenLight = new THREE.DirectionalLight(0x43a047, 1.3)
    greenLight.position.set(-400, -100, 500) // Спереди-слева-снизу
    greenLight.castShadow = true
    scene.add(greenLight)

    // Жёлтый свет спереди-справа
    const yellowLight = new THREE.DirectionalLight(0xffb300, 1.3)
    yellowLight.position.set(400, 100, 600) // Спереди-справа
    yellowLight.castShadow = true
    scene.add(yellowLight)

    // Точечный свет спереди (для бликов)
    const pointLight = new THREE.PointLight(0xffffff, 1.5)
    pointLight.position.set(0, 0, 700) // Спереди
    pointLight.castShadow = true
    scene.add(pointLight)
    
    // Заполняющий свет снизу-спереди
    const fillLight = new THREE.DirectionalLight(0xffffff, 1.0)
    fillLight.position.set(0, -300, 500)
    scene.add(fillLight)

    // Свет сверху-спереди
    const topLight = new THREE.DirectionalLight(0xffffff, 0.9)
    topLight.position.set(0, 500, 400)
    scene.add(topLight)

    // Боковые света для объёма
    const sideLight1 = new THREE.DirectionalLight(0xffffff, 0.7)
    sideLight1.position.set(-600, 0, 400)
    scene.add(sideLight1)
    
    const sideLight2 = new THREE.DirectionalLight(0xffffff, 0.7)
    sideLight2.position.set(600, 0, 400)
    scene.add(sideLight2)

    // Функция для создания fallback геометрии (если модель не загрузилась)
    const createFallbackModel = (config: ModelConfig, index: number): THREE.Group => {
      const group = new THREE.Group()
      
      // Создаём треугольную форму (как логотип BEST) - увеличенный размер
      const geometry = new THREE.ConeGeometry(100, 200, 3) // Увеличено с 50, 100
      const material = new THREE.MeshStandardMaterial({
        color: 0x1e88e5, // Голубой цвет BEST
        metalness: 0.4,
        roughness: 0.3,
        emissive: 0x1e88e5,
        emissiveIntensity: 0.4,
      })
      
      const mesh = new THREE.Mesh(geometry, material)
      mesh.rotation.z = Math.PI / 2
      group.add(mesh)
      
      group.position.set(...config.position)
      group.scale.set(config.scale, config.scale, config.scale)
      group.rotation.set(...config.rotation)
      
      console.log(`✅ Создан fallback для модели ${index + 1}`)
      return group
    }

    // Загружаем модели (динамический импорт для GLTFLoader)
    modelsConfigRef.current = getModelsConfig()
    // Инициализируем разные задержки и скорости для каждой модели
    modelTimeOffsetsRef.current = modelsConfigRef.current.map((_, i) => i * Math.PI * 0.5) // Разные фазы
    modelScrollSpeedsRef.current = modelsConfigRef.current.map((_, i) => 0.8 + i * 0.4) // Разные скорости: 0.8 и 1.2
    modelScrollOffsetsRef.current = modelsConfigRef.current.map(() => 0) // Начальное смещение = 0
    
    import('three/examples/jsm/loaders/GLTFLoader.js')
      .then(({ GLTFLoader }) => {
        const loader = new GLTFLoader()
        const loadPromises = modelsConfigRef.current.map((config, index) => {
          return new Promise<THREE.Group>((resolve) => {
            loader.load(
              config.path,
              (gltf) => {
                try {
                  console.log(`✅ Загружена модель ${index + 1}:`, config.path)
                  // Клонируем сцену для каждой модели (важно!)
                  const model = gltf.scene.clone()
                  model.position.set(...config.position)
                  // Увеличиваем масштаб дополнительно (модель очень маленькая)
                  const additionalScale = 1.0 // Убрал дополнительный масштаб, так как scale уже увеличен в 20 раз
                  model.scale.set(
                    config.scale * additionalScale, 
                    config.scale * additionalScale, 
                    config.scale * additionalScale
                  )
                  // Исправляем ориентацию - наклон К зрителю (положительный X)
                  model.rotation.set(
                    config.rotation[0] || 0.2, // Наклон К зрителю (положительный X)
                    config.rotation[1] || 0, // Y вращение
                    config.rotation[2] || 0
                  )
                  
                  console.log(`📏 Модель ${index + 1} масштаб: ${config.scale * additionalScale}, позиция: [${config.position.join(', ')}], rotation: [${model.rotation.x}, ${model.rotation.y}, ${model.rotation.z}]`)
                  
                  // Настройка материалов для лучшего вида - ЯРКИЕ цвета + объёмность
                  model.traverse((child) => {
                    if (child instanceof THREE.Mesh) {
                      const originalMaterial = child.material
                      
                      // Используем MeshPhysicalMaterial для лучшего 3D-эффекта
                      // На мобильных используем более простой материал для производительности
                      if (originalMaterial instanceof THREE.MeshStandardMaterial || originalMaterial instanceof THREE.MeshBasicMaterial) {
                        const originalColor = originalMaterial.color?.clone() || new THREE.Color(0x1e88e5)
                        
                        if (isMobile) {
                          // Упрощённый материал для мобильных
                          const simpleMaterial = new THREE.MeshStandardMaterial({
                            color: originalColor,
                            metalness: 0.5,
                            roughness: 0.3,
                            emissive: originalColor.clone().multiplyScalar(0.2),
                            emissiveIntensity: 0.3,
                            side: THREE.DoubleSide,
                          })
                          child.material = simpleMaterial
                        } else {
                          // Полный физический материал для десктопа
                          const physicalMaterial = new THREE.MeshPhysicalMaterial({
                            color: originalColor,
                            metalness: 0.7, // Увеличено для блеска
                            roughness: 0.15, // Уменьшено для гладкости
                            clearcoat: 0.5, // Увеличено для глянца
                            clearcoatRoughness: 0.1,
                            reflectivity: 1.0, // Максимальная отражаемость
                            envMapIntensity: 4.0, // Увеличено для яркости
                            emissive: originalColor.clone().multiplyScalar(0.4), // Усилено свечение
                            emissiveIntensity: 0.5,
                            side: THREE.DoubleSide,
                            // Добавляем толщину для объёма
                            thickness: 1.0,
                            transmission: 0.1, // Лёгкая прозрачность для стеклянного эффекта
                          })
                          child.material = physicalMaterial
                        }
                      }
                      
                      // Тени только на десктопе
                      child.castShadow = !isMobile
                      child.receiveShadow = !isMobile
                    }
                  })

                  scene.add(model)
                  modelsRef.current[index] = model
                  console.log(`✅ Модель ${index + 1} добавлена в сцену`)
                  resolve(model)
                } catch (err) {
                  console.error(`❌ Ошибка обработки модели ${index + 1}:`, err)
                  // Создаём fallback геометрию
                  const fallbackModel = createFallbackModel(config, index)
                  scene.add(fallbackModel)
                  modelsRef.current[index] = fallbackModel
                  resolve(fallbackModel)
                }
              },
              (progress) => {
                if (progress.lengthComputable) {
                  console.log(`Загрузка модели ${index + 1}: ${(progress.loaded / progress.total * 100).toFixed(0)}%`)
                }
              },
              (error) => {
                console.warn(`⚠️ Модель ${index + 1} не загрузилась (${config.path}), используем fallback:`, error)
                // Создаём fallback геометрию вместо ошибки
                const fallbackModel = createFallbackModel(config, index)
                scene.add(fallbackModel)
                modelsRef.current[index] = fallbackModel
                resolve(fallbackModel)
              }
            )
          })
        })
        
        Promise.all(loadPromises)
          .then(() => {
            console.log('✅ Все модели загружены (или использованы fallback)')
          })
          .catch((err) => {
            console.error('❌ Критическая ошибка загрузки моделей:', err)
            // Создаём все fallback модели
            modelsConfigRef.current.forEach((config, index) => {
              if (!modelsRef.current[index]) {
                const fallbackModel = createFallbackModel(config, index)
                scene.add(fallbackModel)
                modelsRef.current[index] = fallbackModel
              }
            })
          })
      })
      .catch((err) => {
        console.error('❌ Failed to load GLTFLoader:', err)
      })

    // Анимация парения - оптимизирована для производительности
    let time = 0
    let lastFrameTime = performance.now()
    const targetFPS = isMobile ? 30 : 60 // Снижаем FPS на мобильных
    const frameInterval = 1000 / targetFPS
    
    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate)
      
      const currentTime = performance.now()
      const elapsed = currentTime - lastFrameTime
      
      // Пропускаем кадры для достижения целевого FPS
      if (elapsed < frameInterval) {
        return
      }
      
      lastFrameTime = currentTime - (elapsed % frameInterval)
      time += elapsed / 1000 // Используем реальное время вместо фиксированного шага

      modelsRef.current.forEach((model, index) => {
        if (!model) return
        const config = modelsConfigRef.current[index]
        if (!config) return
        
        // Разные задержки для каждой модели (разнообразие)
        const timeOffset = modelTimeOffsetsRef.current[index] || 0
        const adjustedTime = time + timeOffset
        
        // Плавное парение вверх-вниз с разными фазами
        const floatOffset = Math.sin(adjustedTime * config.floatSpeed * 1000) * config.floatAmplitude
        const baseY = config.position[1]
        
        // Эффект при вращении колёсика - НАКОПЛЕНИЕ смещения (быстрее реагирует)
        // При скролле вниз (deltaY > 0) модели должны двигаться ВНИЗ
        if (wheelEffectRef.current > 0.01) {
          const intensity = Math.min(wheelEffectRef.current, 3.0) // Увеличено с 2.0
          const scrollSpeed = modelScrollSpeedsRef.current[index] || 1.0
          // Более быстрое накопление смещения
          const deltaOffset = -wheelDirectionRef.current * intensity * 2.0 * scrollSpeed // Увеличено с 0.5 до 2.0
          modelScrollOffsetsRef.current[index] = (modelScrollOffsetsRef.current[index] || 0) + deltaOffset
          // Более быстрое затухание (чтобы не было слишком долго)
          wheelEffectRef.current *= 0.95 // Было 0.985, теперь быстрее затухает
        }
        
        // Получаем накопленное смещение
        const accumulatedOffset = modelScrollOffsetsRef.current[index] || 0
        let newY = baseY + floatOffset + accumulatedOffset
        
        // Респаун: мягкий переход - модель плавно появляется с другой стороны
        const screenHeight = window.innerHeight
        const halfScreen = screenHeight / 2
        const spawnMargin = 300 // Зона появления/исчезновения
        
        // Если вышла за нижний край
        if (newY > halfScreen + spawnMargin) {
          // Телепортируем наверх (с небольшим случайным смещением для разнообразия)
          const newPosition = -halfScreen - spawnMargin + Math.random() * 100
          modelScrollOffsetsRef.current[index] = newPosition - baseY - floatOffset
          newY = newPosition
        } 
        // Если вышла за верхний край
        else if (newY < -halfScreen - spawnMargin) {
          // Телепортируем вниз
          const newPosition = halfScreen + spawnMargin - Math.random() * 100
          modelScrollOffsetsRef.current[index] = newPosition - baseY - floatOffset
          newY = newPosition
        }
        
        model.position.y = newY

        // Разное вращение для каждой модели (разнообразие)
        const rotationSpeed = 0.0003 + index * 0.0002 // Разная скорость вращения
        model.rotation.y += rotationSpeed
        // Сохраняем наклон К зрителю (положительный X), не сбрасываем его
        // rotation.x должен оставаться положительным для наклона к зрителю
      })

      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current)
      }
    }
    animate()

    // Обработка вращения колёсика - быстрая реакция
    const handleWheel = (e: WheelEvent) => {
      const delta = Math.abs(e.deltaY)
      if (delta > 3) {
        // Определяем направление: положительный deltaY = вниз, отрицательный = вверх
        wheelDirectionRef.current = e.deltaY > 0 ? 1 : -1
        // Быстрое накопление эффекта
        wheelEffectRef.current = Math.min(wheelEffectRef.current + 0.3, 3.0) // Быстрее накапливается
        
        clearTimeout(wheelTimeoutRef.current)
        // Быстрое затухание после остановки
        wheelTimeoutRef.current = setTimeout(() => {
          wheelEffectRef.current = 0
          wheelDirectionRef.current = 0
        }, 150) // Быстрее сбрасывается
      }
    }

    window.addEventListener('wheel', handleWheel, { passive: true })

    // Обработка изменения размера окна
    const handleResize = () => {
      if (!cameraRef.current || !rendererRef.current) return
      cameraRef.current.aspect = window.innerWidth / window.innerHeight
      cameraRef.current.updateProjectionMatrix()
      rendererRef.current.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('wheel', handleWheel)
      window.removeEventListener('resize', handleResize)
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      if (wheelTimeoutRef.current) {
        clearTimeout(wheelTimeoutRef.current)
      }
      if (rendererRef.current?.domElement.parentNode) {
        rendererRef.current.domElement.parentNode.removeChild(rendererRef.current.domElement)
      }
      rendererRef.current?.dispose()
    }
  }, [isMobile]) // Добавляем isMobile в зависимости

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ 
        opacity: isMobile ? 0.7 : 0.9, // Немного прозрачнее на мобильных
        mixBlendMode: 'normal', // Для правильного наложения
      }}
    />
  )
}
