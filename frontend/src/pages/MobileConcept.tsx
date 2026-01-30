import { useState } from 'react'
import { Bell, Search } from 'lucide-react'
import BottomNav from '../components/mobile/BottomNav'
import MobileTaskCard from '../components/mobile/MobileTaskCard'

export default function MobileConceptPage() {
  const [activeTab, setActiveTab] = useState('home')

  // Mock data for prototype
  const tasks = [
    {
      id: '1',
      title: 'Пост про День Рождения BEST',
      type: 'smm' as const,
      status: 'wip',
      dueDate: '2026-02-15T18:00:00',
      priority: 'critical' as const,
      image: 'https://images.unsplash.com/photo-1496337589254-7e19d01cec44?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60'
    },
    {
      id: '2',
      title: 'Дизайн афиши EBEC',
      type: 'design' as const,
      status: 'pending',
      dueDate: '2026-02-20T12:00:00',
      priority: 'high' as const,
    },
    {
      id: '3',
      title: 'Монтаж видео с хакатона',
      type: 'channel' as const,
      status: 'ready',
      dueDate: '2026-02-10T10:00:00',
      priority: 'medium' as const,
      image: 'https://images.unsplash.com/photo-1536240478700-b869070f9279?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60'
    },
    {
      id: '4',
      title: 'Подготовка мерча',
      type: 'prfr' as const,
      status: 'wip',
      dueDate: '2026-03-01T09:00:00',
      priority: 'low' as const,
    }
  ]

  return (
    <div className="min-h-screen bg-[#0f0f1a] text-white pb-24 font-sans">
      {/* Top Bar */}
      <div className="sticky top-0 z-40 px-6 py-6 bg-[#0f0f1a]/80 backdrop-blur-md flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-white">Привет, Михаил 👋</h1>
          <p className="text-white/50 text-sm">Сегодня 4 активных задачи</p>
        </div>
        <div className="flex gap-4">
          <button className="p-2 rounded-full bg-white/5 hover:bg-white/10 active:bg-white/20 transition-colors">
            <Search className="h-5 w-5 text-white" />
          </button>
          <button className="relative p-2 rounded-full bg-white/5 hover:bg-white/10 active:bg-white/20 transition-colors">
            <Bell className="h-5 w-5 text-white" />
            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border border-[#0f0f1a]" />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="px-6 space-y-8">
        
        {/* Urgent / Stories Style ? */}
        <section>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold text-white">Горящие задачи 🔥</h2>
            <button className="text-best-primary text-sm font-medium">Все</button>
          </div>
          {/* Horizontal Scroll for Urgent */}
          <div className="flex gap-4 overflow-x-auto pb-4 -mx-6 px-6 hide-scrollbar snap-x snap-mandatory">
            {tasks.filter(t => t.priority === 'critical' || t.priority === 'high').map(task => (
              <div key={task.id} className="min-w-[85vw] snap-center">
                <MobileTaskCard task={task} />
              </div>
            ))}
          </div>
        </section>

        {/* Agenda / Feed */}
        <section>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold text-white">План на неделю</h2>
          </div>
          
          <div className="space-y-4">
            {tasks.map(task => (
              <div key={task.id} className="flex gap-4">
                <div className="flex flex-col items-center pt-2 gap-1 min-w-[3rem]">
                  <span className="text-white/40 text-xs font-medium">ПН</span>
                  <span className="text-white font-bold text-lg">15</span>
                </div>
                {/* Mini Card for list view */}
                <div className="flex-1 bg-[#1a1a2e] rounded-2xl p-4 border border-white/5 active:scale-[0.98] transition-transform">
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-[10px] uppercase font-bold tracking-wider ${
                      task.type === 'smm' ? 'text-emerald-400' : 
                      task.type === 'design' ? 'text-blue-400' : 'text-purple-400'
                    }`}>{task.type}</span>
                    <span className={`w-2 h-2 rounded-full ${
                      task.status === 'ready' ? 'bg-green-500' : 'bg-yellow-500'
                    }`} />
                  </div>
                  <h3 className="font-bold text-white mb-1 line-clamp-2">{task.title}</h3>
                  <p className="text-white/40 text-xs">До 18:00</p>
                </div>
              </div>
            ))}
          </div>
        </section>

      </div>

      <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  )
}