import { useQuery } from '@tanstack/react-query'
import { Image, Loader2, Film, FileText } from 'lucide-react'
import { galleryApi } from '../services/gallery'
import { useThemeStore } from '../store/themeStore'

export default function Gallery() {
  const { theme } = useThemeStore()

  const { data, isLoading } = useQuery({
    queryKey: ['gallery'],
    queryFn: () => galleryApi.getGallery({ limit: 20 }),
  })

  const items = data?.items || []

  return (
    <div className="max-w-7xl mx-auto">
      <div className={`glass-enhanced ${theme} rounded-2xl p-8 mb-8 text-white`}>
        <div className="flex items-center space-x-3 mb-6">
          <Image className="h-8 w-8 text-best-primary" />
          <h1 className={`text-3xl font-bold text-white text-readable ${theme}`}>Галерея результатов</h1>
        </div>
        <p className={`text-white/80 mb-6 text-readable ${theme}`}>
          Выполненные работы команды PR-отдела
        </p>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-white/60">
            <Image className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Пока нет выполненных работ</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {items.map((item) => (
              <div
                key={item.id}
                className={`p-4 rounded-lg bg-white/10 border border-white/20 hover:bg-white/15 transition-all cursor-pointer`}
              >
                <div className="flex items-center space-x-2 mb-3">
                  {item.type === 'channel' && <Film className="h-5 w-5 text-best-secondary" />}
                  {item.type === 'smm' && <FileText className="h-5 w-5 text-best-primary" />}
                  <h3 className={`font-semibold text-white text-readable ${theme}`}>{item.title}</h3>
                </div>
                <p className={`text-white/60 text-sm mb-3 text-readable ${theme}`}>
                  {item.files_count} файл(ов)
                </p>
                <p className={`text-white/40 text-xs text-readable ${theme}`}>
                  Завершено: {new Date(item.completed_at).toLocaleDateString('ru-RU')}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
